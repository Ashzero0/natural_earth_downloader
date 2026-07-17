# -*- coding: utf-8 -*-
import os
import re
import shutil
import zipfile

from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.core import (
    QgsApplication,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsNetworkAccessManager,
    QgsProject,
    QgsSingleSymbolRenderer,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)


class BatchDownloadController(QObject):
    """Sequential, cancellable batch download and conversion controller."""

    batch_started = pyqtSignal(int)
    item_started = pyqtSignal(str, str, int, int)
    item_progress = pyqtSignal(str, int, int, int)
    item_finished = pyqtSignal(str, bool, str)
    overall_progress = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    batch_finished = pyqtSignal(int, int, bool, list)

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.queue = []
        self.config = {}
        self.index = 0
        self.success_count = 0
        self.failure_count = 0
        self.failures = []
        self.cancelled = False
        self.reply = None
        self.part_file = None
        self.part_path = None
        self._prepared_gpkg_path = None

        self.cache_root = os.path.join(
            QgsApplication.qgisSettingsDirPath(),
            "cache",
            "natural_earth_downloader",
        )
        self.archive_dir = os.path.join(self.cache_root, "archives")
        self.extract_root = os.path.join(self.cache_root, "extracted")

    def start(self, datasets, config):
        if self.reply is not None:
            return
        self.queue = list(datasets)
        self.config = dict(config)
        self.index = 0
        self.success_count = 0
        self.failure_count = 0
        self.failures = []
        self.cancelled = False
        self._prepared_gpkg_path = None
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.extract_root, exist_ok=True)
        self._prepare_batch_output()
        self.batch_started.emit(len(self.queue))
        self._process_next()

    def cancel(self):
        self.cancelled = True
        self.status_changed.emit("Cancelling…")
        if self.reply is not None:
            self.reply.abort()

    def _prepare_batch_output(self):
        if self.config.get("format") != "GPKG":
            return
        requested = self.config["output_path"]
        os.makedirs(os.path.dirname(requested), exist_ok=True)
        if os.path.exists(requested):
            if self.config.get("overwrite", True):
                self._remove_gpkg(requested)
                self._prepared_gpkg_path = requested
            else:
                self._prepared_gpkg_path = self._unique_path(requested)
        else:
            self._prepared_gpkg_path = requested
        self.config["resolved_output_path"] = self._prepared_gpkg_path

    @staticmethod
    def _remove_gpkg(path):
        for suffix in ("", "-wal", "-shm"):
            candidate = path + suffix
            if os.path.exists(candidate):
                os.remove(candidate)

    def _process_next(self):
        if self.cancelled or self.index >= len(self.queue):
            self._finish_batch()
            return

        dataset = self.queue[self.index]
        self.item_started.emit(
            dataset["id"], dataset["name"], self.index + 1, len(self.queue)
        )
        archive_path = os.path.join(self.archive_dir, dataset["archive"])

        if os.path.exists(archive_path) and os.path.getsize(archive_path) > 0:
            self.status_changed.emit(f"Using cached archive: {dataset['name']}")
            self.item_progress.emit(dataset["id"], 100, os.path.getsize(archive_path), os.path.getsize(archive_path))
            self._process_archive(dataset, archive_path)
            return

        self.status_changed.emit(f"Downloading {dataset['name']} ({dataset['scale_label']})")
        self.part_path = archive_path + ".part"
        try:
            if os.path.exists(self.part_path):
                os.remove(self.part_path)
            self.part_file = open(self.part_path, "wb")
        except OSError as exc:
            self._record_failure(dataset, f"Cannot create cache file: {exc}")
            return

        request = QNetworkRequest(QUrl(dataset["url"]))
        request.setRawHeader(b"User-Agent", b"QGIS Natural Earth Downloader/0.1.2")
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
        self.reply = QgsNetworkAccessManager.instance().get(request)
        self.reply.readyRead.connect(self._on_ready_read)
        self.reply.downloadProgress.connect(
            lambda received, total, dataset_id=dataset["id"]: self._on_download_progress(
                dataset_id, received, total
            )
        )
        self.reply.finished.connect(lambda dataset=dataset, path=archive_path: self._on_reply_finished(dataset, path))

    def _on_ready_read(self):
        if self.reply is not None and self.part_file is not None:
            self.part_file.write(bytes(self.reply.readAll()))

    def _on_download_progress(self, dataset_id, received, total):
        percent = int(received * 100 / total) if total and total > 0 else 0
        self.item_progress.emit(dataset_id, percent, int(received), int(total))

    def _on_reply_finished(self, dataset, archive_path):
        reply = self.reply
        self.reply = None
        if self.part_file is not None:
            try:
                if reply is not None:
                    remaining = bytes(reply.readAll())
                    if remaining:
                        self.part_file.write(remaining)
            finally:
                self.part_file.close()
                self.part_file = None

        if self.cancelled:
            self._safe_remove(self.part_path)
            if reply is not None:
                reply.deleteLater()
            self._finish_batch()
            return

        if reply is None or reply.error() != QNetworkReply.NoError:
            message = reply.errorString() if reply is not None else "Unknown network error"
            self._safe_remove(self.part_path)
            if reply is not None:
                reply.deleteLater()
            self._record_failure(dataset, f"Download failed: {message}")
            return

        try:
            os.replace(self.part_path, archive_path)
        except OSError as exc:
            self._safe_remove(self.part_path)
            reply.deleteLater()
            self._record_failure(dataset, f"Cannot save downloaded archive: {exc}")
            return

        reply.deleteLater()
        self._process_archive(dataset, archive_path)

    def _process_archive(self, dataset, archive_path):
        if self.cancelled:
            self._finish_batch()
            return
        self.status_changed.emit(f"Preparing {dataset['name']}…")
        try:
            extract_dir = self._extract_archive(dataset, archive_path)
            source_path = self._find_source_layer(dataset, extract_dir)
            source_layer = QgsVectorLayer(source_path, dataset["name"], "ogr")
            if not source_layer.isValid():
                raise RuntimeError("QGIS could not open the extracted vector layer.")

            output_layer, message = self._create_output(dataset, source_layer)
            if output_layer is not None and self.config.get("apply_style", True):
                self._apply_basic_style(output_layer, dataset)
            if output_layer is not None and self.config.get("add_to_project", True):
                QgsProject.instance().addMapLayer(output_layer)

            self.success_count += 1
            self.item_finished.emit(dataset["id"], True, message)
        except Exception as exc:  # show a useful per-layer error and continue the batch
            self.failure_count += 1
            message = str(exc)
            self.failures.append(f"{dataset['name']} ({dataset['scale_label']}): {message}")
            self.item_finished.emit(dataset["id"], False, message)

        self.index += 1
        self.overall_progress.emit(int(self.index * 100 / max(1, len(self.queue))))
        self._process_next()

    def _record_failure(self, dataset, message):
        self.failure_count += 1
        self.failures.append(f"{dataset['name']} ({dataset['scale_label']}): {message}")
        self.item_finished.emit(dataset["id"], False, message)
        self.index += 1
        self.overall_progress.emit(int(self.index * 100 / max(1, len(self.queue))))
        self._process_next()

    def _extract_archive(self, dataset, archive_path):
        extract_dir = os.path.join(self.extract_root, dataset["id"])
        marker = os.path.join(extract_dir, ".complete")
        if os.path.exists(marker):
            return extract_dir

        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)
        root = os.path.realpath(extract_dir)

        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                for member in archive.infolist():
                    target = os.path.realpath(os.path.join(extract_dir, member.filename))
                    if target != root and not target.startswith(root + os.sep):
                        raise RuntimeError("Unsafe path found in downloaded ZIP archive.")
                archive.extractall(extract_dir)
        except zipfile.BadZipFile as exc:
            self._safe_remove(archive_path)
            raise RuntimeError("The downloaded file is not a valid ZIP archive.") from exc

        with open(marker, "w", encoding="utf-8") as stream:
            stream.write(dataset["url"])
        return extract_dir

    @staticmethod
    def _find_source_layer(dataset, extract_dir):
        exact_name = dataset["id"] + ".shp"
        candidates = []
        for root, _, files in os.walk(extract_dir):
            for filename in files:
                if filename.lower().endswith(".shp"):
                    path = os.path.join(root, filename)
                    if filename.lower() == exact_name.lower():
                        return path
                    candidates.append(path)
        if not candidates:
            raise RuntimeError("No Shapefile was found in the downloaded archive.")
        return candidates[0]

    def _create_output(self, dataset, source_layer):
        fmt = self.config["format"]
        if fmt == "TEMP":
            memory_layer = self._to_memory_layer(source_layer, self._display_layer_name(dataset))
            return memory_layer, "Loaded as a temporary layer"

        if fmt == "GPKG":
            output_path = self.config["resolved_output_path"]
            layer_name = self._safe_layer_name(dataset["id"].replace("ne_", "", 1))
            self._write_layer(source_layer, output_path, "GPKG", layer_name)
            uri = f"{output_path}|layername={layer_name}"
            layer = QgsVectorLayer(uri, self._display_layer_name(dataset), "ogr")
            if not layer.isValid():
                raise RuntimeError("The GeoPackage layer was written but could not be reopened.")
            return layer, f"Saved to {os.path.basename(output_path)} / {layer_name}"

        output_dir = self.config["output_path"]
        os.makedirs(output_dir, exist_ok=True)
        stem = dataset["id"]
        if fmt == "GeoJSON":
            output_path = os.path.join(output_dir, stem + ".geojson")
            output_path = self._resolve_individual_path(output_path)
            self._write_layer(source_layer, output_path, "GeoJSON", stem)
        elif fmt == "ESRI Shapefile":
            output_path = os.path.join(output_dir, stem + ".shp")
            output_path = self._resolve_individual_path(output_path)
            self._write_layer(source_layer, output_path, "ESRI Shapefile", stem)
        else:
            raise RuntimeError(f"Unsupported output format: {fmt}")

        layer = QgsVectorLayer(output_path, self._display_layer_name(dataset), "ogr")
        if not layer.isValid():
            raise RuntimeError("The output was written but could not be reopened in QGIS.")
        return layer, f"Saved to {os.path.basename(output_path)}"

    def _resolve_individual_path(self, path):
        if not os.path.exists(path):
            return path
        if self.config.get("overwrite", True):
            if path.lower().endswith(".shp"):
                self._remove_shapefile(path)
            else:
                os.remove(path)
            return path
        return self._unique_path(path)

    @staticmethod
    def _remove_shapefile(path):
        base, _ = os.path.splitext(path)
        for extension in (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qpj", ".sbn", ".sbx"):
            candidate = base + extension
            if os.path.exists(candidate):
                os.remove(candidate)

    @staticmethod
    def _unique_path(path):
        base, extension = os.path.splitext(path)
        counter = 2
        candidate = path
        while os.path.exists(candidate):
            candidate = f"{base}_{counter}{extension}"
            counter += 1
        return candidate

    @staticmethod
    def _safe_layer_name(value):
        value = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_")
        return value[:63] or "natural_earth_layer"

    @staticmethod
    def _display_layer_name(dataset):
        return f"{dataset['name']} — {dataset['scale_label']}"

    @staticmethod
    def _write_layer(layer, output_path, driver_name, layer_name):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver_name
        options.fileEncoding = "UTF-8"
        options.layerName = layer_name
        if driver_name == "GPKG" and os.path.exists(output_path):
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        else:
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        if driver_name == "GeoJSON":
            options.layerOptions = ["RFC7946=YES", "WRITE_BBOX=YES"]

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            output_path,
            QgsProject.instance().transformContext(),
            options,
        )
        error_code = result[0]
        error_message = result[-1] if len(result) >= 4 else ""
        if error_code != QgsVectorFileWriter.NoError:
            raise RuntimeError(error_message or f"Vector writer error code {int(error_code)}")

    @staticmethod
    def _to_memory_layer(source, name):
        crs = source.crs().authid() or source.crs().toWkt()
        geometry = QgsWkbTypes.displayString(source.wkbType())
        memory = QgsVectorLayer(f"{geometry}?crs={crs}", name, "memory")
        if not memory.isValid():
            raise RuntimeError("Could not create the temporary memory layer.")
        provider = memory.dataProvider()
        provider.addAttributes(list(source.fields()))
        memory.updateFields()
        provider.addFeatures(list(source.getFeatures()))
        memory.updateExtents()
        return memory

    @staticmethod
    def _apply_basic_style(layer, dataset):
        geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
        slug = dataset["slug"]
        category = dataset["category"]

        if geometry_type == QgsWkbTypes.PolygonGeometry:
            fill = "#e9e5d8" if category == "Cultural" else "#dfe8d5"
            outline = "#737b78"
            if slug == "ocean":
                fill, outline = "#d6eaf2", "#8cb7c8"
            elif "lake" in slug:
                fill, outline = "#c9e3ee", "#6aa6bc"
            elif "ice" in slug or "glaciat" in slug:
                fill, outline = "#eef8fb", "#9ec9d8"
            symbol = QgsFillSymbol.createSimple({
                "color": fill,
                "outline_color": outline,
                "outline_width": "0.25",
            })
        elif geometry_type == QgsWkbTypes.LineGeometry:
            color = "#6f7774"
            width = "0.35"
            if "river" in slug or "coastline" in slug:
                color = "#5798b3"
            elif "road" in slug:
                color, width = "#c18f59", "0.45"
            elif "rail" in slug:
                color = "#555555"
            symbol = QgsLineSymbol.createSimple({"color": color, "width": width})
        elif geometry_type == QgsWkbTypes.PointGeometry:
            color = "#2e6f82" if category == "Physical" else "#8a4f3d"
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle",
                "color": color,
                "outline_color": "#ffffff",
                "size": "2.2",
            })
        else:
            return
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.triggerRepaint()

    @staticmethod
    def _safe_remove(path):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    def _finish_batch(self):
        was_cancelled = self.cancelled
        self.reply = None
        self.part_file = None
        self.part_path = None
        self.batch_finished.emit(
            self.success_count,
            self.failure_count,
            was_cancelled,
            list(self.failures),
        )
