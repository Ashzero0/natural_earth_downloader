# -*- coding: utf-8 -*-
import os
import shutil

from qgis.PyQt.QtCore import QSettings, QStandardPaths, Qt
from qgis.PyQt.QtGui import QColor, QFont, QPalette
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .catalog import CATALOGUE
from .download_controller import BatchDownloadController


class NaturalEarthDownloaderDialog(QDialog):
    """Main user interface for the Natural Earth Downloader."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.settings = QSettings()
        self.catalogue = list(CATALOGUE)
        self.by_id = {item["id"]: item for item in self.catalogue}
        self.row_by_id = {}
        self.is_running = False
        self.closing_after_cancel = False

        self.setWindowTitle("Natural Earth Downloader")
        self.setMinimumSize(980, 660)
        self.resize(1120, 740)
        self.setModal(False)

        self.controller = BatchDownloadController(iface, self)
        self._build_ui()
        self._connect_signals()
        self._populate_table()
        self._restore_settings()
        self._apply_filter()
        self._update_selection_count()
        self._update_output_controls()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #f4f6f7; }
            QLabel#title { font-size: 22px; font-weight: 700; color: #20363f; }
            QLabel#subtitle { color: #64747b; font-size: 12px; }
            QFrame#card { background: white; border: 1px solid #dfe5e7; border-radius: 9px; }
            QLineEdit, QComboBox {
                min-height: 31px; padding: 2px 8px; background: white;
                color: #20363f;
                border: 1px solid #cfd8dc; border-radius: 5px;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid #2e758a; }
            QComboBox QAbstractItemView {
                background: white;
                color: #20363f;
                selection-background-color: #dcecf1;
                selection-color: #20363f;
                border: 1px solid #cfd8dc;
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 8px;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #dcecf1;
                color: #20363f;
            }
            QTableWidget {
                background: white; border: 1px solid #dfe5e7; border-radius: 6px;
                gridline-color: #edf0f1; selection-background-color: #dcecf1;
                selection-color: #20363f;
            }
            QHeaderView::section {
                background: #eef3f4; color: #40545c; padding: 7px;
                border: none; border-bottom: 1px solid #d8e0e3; font-weight: 600;
            }
            QPushButton { min-height: 31px; padding: 2px 13px; border-radius: 5px; }
            QPushButton#primary {
                background: #236c80; color: white; border: 1px solid #236c80;
                font-weight: 600; min-width: 150px;
            }
            QPushButton#primary:hover { background: #1c5c6e; }
            QPushButton#primary:disabled { background: #9eafb4; border-color: #9eafb4; }
            QPushButton#secondary { background: white; border: 1px solid #cbd5d8; color: #34484f; }
            QPushButton#danger { background: white; border: 1px solid #c97b72; color: #8a3c34; }
            QProgressBar { border: 1px solid #cfd8dc; border-radius: 4px; text-align: center; background: white; }
            QProgressBar::chunk { background: #3a8295; border-radius: 3px; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(11)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Natural Earth Downloader")
        title.setObjectName("title")
        subtitle = QLabel("Select several vector datasets and add them to QGIS in one operation.")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.about_button = QPushButton("About & licence")
        self.about_button.setObjectName("secondary")
        header.addWidget(self.about_button)
        root.addLayout(header)

        filter_card = QFrame()
        filter_card.setObjectName("card")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search countries, rivers, roads, airports…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["All scales", "1:10m", "1:50m", "1:110m"])
        self.category_combo = QComboBox()
        self.category_combo.addItems(["All categories", "Cultural", "Physical"])
        self.geometry_combo = QComboBox()
        self.geometry_combo.addItems(["All geometries", "Point", "Line", "Polygon"])
        filter_layout.addWidget(self.search_edit, 1)
        filter_layout.addWidget(self.scale_combo)
        filter_layout.addWidget(self.category_combo)
        filter_layout.addWidget(self.geometry_combo)
        root.addWidget(filter_card)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(7)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "Dataset", "Scale", "Category", "Geometry", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            header_view.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        left_layout.addWidget(self.table, 1)

        selection_bar = QHBoxLayout()
        self.selection_label = QLabel("0 datasets selected")
        self.select_visible_button = QPushButton("Select visible")
        self.select_visible_button.setObjectName("secondary")
        self.clear_selection_button = QPushButton("Clear selection")
        self.clear_selection_button.setObjectName("secondary")
        selection_bar.addWidget(self.selection_label)
        selection_bar.addStretch()
        selection_bar.addWidget(self.select_visible_button)
        selection_bar.addWidget(self.clear_selection_button)
        left_layout.addLayout(selection_bar)

        detail_card = QFrame()
        detail_card.setObjectName("card")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(16, 14, 16, 14)
        detail_title = QLabel("Dataset details")
        detail_title.setFont(QFont(detail_title.font().family(), 11, QFont.Bold))
        self.detail_browser = QTextBrowser()
        self.detail_browser.setFrameShape(QFrame.NoFrame)
        self.detail_browser.setOpenExternalLinks(True)
        self.detail_browser.setHtml(self._empty_detail_html())
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_browser, 1)

        splitter.addWidget(left)
        splitter.addWidget(detail_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([680, 360])
        root.addWidget(splitter, 1)

        output_card = QFrame()
        output_card.setObjectName("card")
        output_layout = QGridLayout(output_card)
        output_layout.setContentsMargins(14, 12, 14, 12)
        output_layout.setHorizontalSpacing(9)
        output_layout.setVerticalSpacing(8)

        output_title = QLabel("Output")
        output_title.setFont(QFont(output_title.font().family(), 10, QFont.Bold))
        self.format_combo = QComboBox()
        self.format_combo.addItem("GeoPackage — one file, several layers", "GPKG")
        self.format_combo.addItem("GeoJSON — one file per dataset", "GeoJSON")
        self.format_combo.addItem("ESRI Shapefile — one file set per dataset", "ESRI Shapefile")
        self.format_combo.addItem("Temporary QGIS layers — no permanent output", "TEMP")

        # QGIS/Qt themes on Windows can provide a white highlighted-text color
        # while the plugin uses a light selection background. Apply an explicit
        # palette to every combo box and its popup view so the selected option
        # remains readable in both the closed control and the open list.
        for combo in (
            self.scale_combo,
            self.category_combo,
            self.geometry_combo,
            self.format_combo,
        ):
            self._configure_combo_palette(combo)

        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose an output location")
        self.browse_button = QPushButton("Browse…")
        self.browse_button.setObjectName("secondary")
        self.add_to_project_check = QCheckBox("Add completed layers to the current project")
        self.add_to_project_check.setChecked(True)
        self.style_check = QCheckBox("Apply a simple Natural Earth style")
        self.style_check.setChecked(True)
        self.overwrite_check = QCheckBox("Replace outputs with the same name")
        self.overwrite_check.setChecked(True)

        output_layout.addWidget(output_title, 0, 0)
        output_layout.addWidget(self.format_combo, 0, 1, 1, 2)
        output_layout.addWidget(QLabel("Location"), 1, 0)
        output_layout.addWidget(self.output_edit, 1, 1)
        output_layout.addWidget(self.browse_button, 1, 2)
        option_box = QHBoxLayout()
        option_box.addWidget(self.add_to_project_check)
        option_box.addWidget(self.style_check)
        option_box.addWidget(self.overwrite_check)
        option_box.addStretch()
        output_layout.addLayout(option_box, 2, 0, 1, 3)
        root.addWidget(output_card)

        progress_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("subtitle")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setVisible(False)
        self.clear_cache_button = QPushButton("Clear cache")
        self.clear_cache_button.setObjectName("secondary")
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("secondary")
        self.download_button = QPushButton("Download selected")
        self.download_button.setObjectName("primary")
        progress_row.addWidget(self.status_label)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.cancel_button)
        progress_row.addWidget(self.clear_cache_button)
        progress_row.addWidget(self.close_button)
        progress_row.addWidget(self.download_button)
        root.addLayout(progress_row)

    @staticmethod
    def _configure_combo_palette(combo):
        """Keep combo-box text readable regardless of the active QGIS theme."""
        text_color = QColor("#20363f")
        base_color = QColor("#ffffff")
        highlight_color = QColor("#dcecf1")

        combo_palette = combo.palette()
        combo_palette.setColor(QPalette.Text, text_color)
        combo_palette.setColor(QPalette.ButtonText, text_color)
        combo_palette.setColor(QPalette.Base, base_color)
        combo_palette.setColor(QPalette.Button, base_color)
        combo.setPalette(combo_palette)

        view = combo.view()
        view_palette = view.palette()
        view_palette.setColor(QPalette.Base, base_color)
        view_palette.setColor(QPalette.AlternateBase, base_color)
        view_palette.setColor(QPalette.Text, text_color)
        view_palette.setColor(QPalette.Highlight, highlight_color)
        view_palette.setColor(QPalette.HighlightedText, text_color)
        view.setPalette(view_palette)
        view.setStyleSheet("""
            QAbstractItemView {
                background-color: #ffffff;
                color: #20363f;
                selection-background-color: #dcecf1;
                selection-color: #20363f;
                outline: 0;
            }
            QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 8px;
            }
            QAbstractItemView::item:selected {
                background-color: #dcecf1;
                color: #20363f;
            }
        """)

    def _connect_signals(self):
        self.search_edit.textChanged.connect(self._apply_filter)
        self.scale_combo.currentIndexChanged.connect(self._apply_filter)
        self.category_combo.currentIndexChanged.connect(self._apply_filter)
        self.geometry_combo.currentIndexChanged.connect(self._apply_filter)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._show_selected_details)
        self.select_visible_button.clicked.connect(self._select_visible)
        self.clear_selection_button.clicked.connect(self._clear_selection)
        self.format_combo.currentIndexChanged.connect(self._update_output_controls)
        self.browse_button.clicked.connect(self._browse_output)
        self.download_button.clicked.connect(self._start_download)
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.close_button.clicked.connect(self.close)
        self.clear_cache_button.clicked.connect(self._clear_cache)
        self.about_button.clicked.connect(self._show_about)

        self.controller.item_started.connect(self._on_item_started)
        self.controller.item_progress.connect(self._on_item_progress)
        self.controller.item_finished.connect(self._on_item_finished)
        self.controller.overall_progress.connect(self.progress_bar.setValue)
        self.controller.status_changed.connect(self.status_label.setText)
        self.controller.batch_finished.connect(self._on_batch_finished)

    def _populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.catalogue))
        for row, dataset in enumerate(self.catalogue):
            self.row_by_id[dataset["id"]] = row
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            check_item.setCheckState(Qt.Unchecked)
            check_item.setTextAlignment(Qt.AlignCenter)

            name_item = QTableWidgetItem(dataset["name"])
            name_item.setData(Qt.UserRole, dataset["id"])
            name_item.setToolTip(dataset["description"])
            scale_item = QTableWidgetItem(dataset["scale_label"])
            category_item = QTableWidgetItem(dataset["category"])
            geometry_item = QTableWidgetItem(dataset["geometry"])
            status_item = QTableWidgetItem("Ready")
            status_item.setForeground(QColor("#7a898e"))

            self.table.setItem(row, 0, check_item)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, scale_item)
            self.table.setItem(row, 3, category_item)
            self.table.setItem(row, 4, geometry_item)
            self.table.setItem(row, 5, status_item)
        self.table.blockSignals(False)
        if self.catalogue:
            self.table.selectRow(0)

    def _restore_settings(self):
        stored_format = self.settings.value("natural_earth_downloader/format", "GPKG")
        for index in range(self.format_combo.count()):
            if self.format_combo.itemData(index) == stored_format:
                self.format_combo.setCurrentIndex(index)
                break
        documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        default_gpkg = os.path.join(documents, "natural_earth.gpkg")
        default_folder = os.path.join(documents, "Natural Earth")
        if stored_format == "GPKG":
            value = self.settings.value("natural_earth_downloader/gpkg_path", default_gpkg)
        else:
            value = self.settings.value("natural_earth_downloader/output_folder", default_folder)
        self.output_edit.setText(value)

    def _apply_filter(self):
        search = self.search_edit.text().strip().lower()
        scale = self.scale_combo.currentText()
        category = self.category_combo.currentText()
        geometry = self.geometry_combo.currentText()

        visible_count = 0
        for dataset in self.catalogue:
            haystack = " ".join([
                dataset["name"], dataset["description"], dataset["tags"], dataset["id"]
            ]).lower()
            visible = not search or search in haystack
            if scale != "All scales":
                visible = visible and dataset["scale_label"] == scale
            if category != "All categories":
                visible = visible and dataset["category"] == category
            if geometry != "All geometries":
                visible = visible and dataset["geometry"] == geometry
            row = self.row_by_id[dataset["id"]]
            self.table.setRowHidden(row, not visible)
            if visible:
                visible_count += 1
        self.status_label.setText(f"{visible_count} datasets shown")

    def _on_item_changed(self, item):
        if item.column() == 0:
            self._update_selection_count()

    def _selected_datasets(self):
        selected = []
        for dataset in self.catalogue:
            row = self.row_by_id[dataset["id"]]
            if self.table.item(row, 0).checkState() == Qt.Checked:
                selected.append(dataset)
        return selected

    def _update_selection_count(self):
        count = len(self._selected_datasets())
        self.selection_label.setText(f"{count} dataset{'s' if count != 1 else ''} selected")
        self.download_button.setText(f"Download {count} dataset{'s' if count != 1 else ''}" if count else "Download selected")
        self.download_button.setEnabled(count > 0 and not self.is_running)

    def _select_visible(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(Qt.Checked)
        self.table.blockSignals(False)
        self._update_selection_count()

    def _clear_selection(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_selection_count()

    def _show_selected_details(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail_browser.setHtml(self._empty_detail_html())
            return
        dataset_id = self.table.item(rows[0].row(), 1).data(Qt.UserRole)
        dataset = self.by_id[dataset_id]
        self.detail_browser.setHtml(f"""
            <h2 style='margin:0 0 5px 0;color:#263f48'>{dataset['name']}</h2>
            <p style='margin:0 0 14px 0;color:#6a7b81'><code>{dataset['id']}</code></p>
            <p style='font-size:13px;line-height:1.45'>{dataset['description']}</p>
            <table cellspacing='0' cellpadding='5' style='font-size:12px'>
              <tr><td><b>Scale</b></td><td>{dataset['scale_label']}</td></tr>
              <tr><td><b>Category</b></td><td>{dataset['category']}</td></tr>
              <tr><td><b>Geometry</b></td><td>{dataset['geometry']}</td></tr>
              <tr><td><b>Source format</b></td><td>Natural Earth Shapefile archive</td></tr>
              <tr><td><b>Licence</b></td><td>Public domain</td></tr>
            </table>
            <p style='margin-top:16px'><a href='{dataset['url']}'>Open direct archive URL</a></p>
        """)

    @staticmethod
    def _empty_detail_html():
        return """
            <div style='color:#718187;padding-top:18px'>
              <h3 style='color:#445b63'>Choose a dataset</h3>
              <p>Select a row to see its description, scale, geometry and source information.</p>
            </div>
        """

    def _format_code(self):
        return self.format_combo.currentData()

    def _update_output_controls(self):
        fmt = self._format_code()
        is_temp = fmt == "TEMP"
        self.output_edit.setEnabled(not is_temp)
        self.browse_button.setEnabled(not is_temp)
        self.overwrite_check.setEnabled(not is_temp)
        if is_temp:
            self.output_edit.setPlaceholderText("No permanent file will be created")
            self.add_to_project_check.setChecked(True)
            self.add_to_project_check.setEnabled(False)
        else:
            self.output_edit.setPlaceholderText("Choose an output location")
            self.add_to_project_check.setEnabled(True)
            documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            if fmt == "GPKG" and not self.output_edit.text().lower().endswith(".gpkg"):
                self.output_edit.setText(self.settings.value(
                    "natural_earth_downloader/gpkg_path",
                    os.path.join(documents, "natural_earth.gpkg"),
                ))
            elif fmt != "GPKG" and self.output_edit.text().lower().endswith(".gpkg"):
                self.output_edit.setText(self.settings.value(
                    "natural_earth_downloader/output_folder",
                    os.path.join(documents, "Natural Earth"),
                ))

    def _browse_output(self):
        fmt = self._format_code()
        current = self.output_edit.text().strip()
        if fmt == "GPKG":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Choose the GeoPackage",
                current,
                "GeoPackage (*.gpkg)",
            )
            if path:
                if not path.lower().endswith(".gpkg"):
                    path += ".gpkg"
                self.output_edit.setText(path)
        else:
            folder = QFileDialog.getExistingDirectory(
                self,
                "Choose the output folder",
                current or QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation),
            )
            if folder:
                self.output_edit.setText(folder)

    def _validate_output(self):
        fmt = self._format_code()
        if fmt == "TEMP":
            return True
        path = self.output_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Output required", "Choose an output location before downloading.")
            return False
        if fmt == "GPKG":
            if not path.lower().endswith(".gpkg"):
                path += ".gpkg"
                self.output_edit.setText(path)
            parent = os.path.dirname(path)
            if not parent:
                QMessageBox.warning(self, "Invalid output", "Choose a complete path for the GeoPackage.")
                return False
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "Output error", f"The output folder cannot be created:\n{exc}")
                return False
        else:
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as exc:
                QMessageBox.critical(self, "Output error", f"The output folder cannot be created:\n{exc}")
                return False
        return True

    def _start_download(self):
        datasets = self._selected_datasets()
        if not datasets:
            return
        if not self._validate_output():
            return

        fmt = self._format_code()
        output_path = self.output_edit.text().strip()
        self.settings.setValue("natural_earth_downloader/format", fmt)
        if fmt == "GPKG":
            self.settings.setValue("natural_earth_downloader/gpkg_path", output_path)
        elif fmt != "TEMP":
            self.settings.setValue("natural_earth_downloader/output_folder", output_path)

        config = {
            "format": fmt,
            "output_path": output_path,
            "add_to_project": self.add_to_project_check.isChecked(),
            "apply_style": self.style_check.isChecked(),
            "overwrite": self.overwrite_check.isChecked(),
        }
        self._set_running(True)
        for dataset in datasets:
            self._set_row_status(dataset["id"], "Queued", "#6b7c82")
        self.progress_bar.setValue(0)
        self.controller.start(datasets, config)

    def _set_running(self, running):
        self.is_running = running
        self.progress_bar.setVisible(running)
        self.cancel_button.setVisible(running)
        self.download_button.setEnabled(not running and bool(self._selected_datasets()))
        for widget in (
            self.search_edit, self.scale_combo, self.category_combo, self.geometry_combo,
            self.select_visible_button, self.clear_selection_button, self.format_combo,
            self.output_edit, self.browse_button, self.add_to_project_check,
            self.style_check, self.overwrite_check, self.clear_cache_button,
        ):
            widget.setEnabled(not running)
        if not running:
            self._update_output_controls()

    def _on_item_started(self, dataset_id, name, position, total):
        self._set_row_status(dataset_id, f"Starting {position}/{total}", "#2e758a")

    def _on_item_progress(self, dataset_id, percent, received, total):
        if total > 0:
            text = f"{percent}% · {self._human_size(received)} / {self._human_size(total)}"
        else:
            text = f"{self._human_size(received)}"
        self._set_row_status(dataset_id, text, "#2e758a")

    def _on_item_finished(self, dataset_id, success, message):
        if success:
            self._set_row_status(dataset_id, "✓ Complete", "#2e7d55", message)
        else:
            self._set_row_status(dataset_id, "Failed", "#a4443b", message)

    def _set_row_status(self, dataset_id, text, color, tooltip=""):
        row = self.row_by_id.get(dataset_id)
        if row is None:
            return
        item = self.table.item(row, 5)
        item.setText(text)
        item.setForeground(self._qcolor(color))
        item.setToolTip(tooltip)

    @staticmethod
    def _qcolor(value):
        return QColor(value)

    def _on_batch_finished(self, success_count, failure_count, cancelled, failures):
        self._set_running(False)
        self.progress_bar.setValue(100 if not cancelled else self.progress_bar.value())
        if self.closing_after_cancel:
            self.closing_after_cancel = False
            return
        if cancelled:
            self.status_label.setText(f"Cancelled — {success_count} completed")
            QMessageBox.information(
                self,
                "Download cancelled",
                f"The batch was cancelled.\n\n{success_count} dataset(s) completed successfully.",
            )
            return

        self.status_label.setText(f"Finished — {success_count} complete, {failure_count} failed")
        if failure_count:
            detail = "\n".join(failures)
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setWindowTitle("Batch completed with errors")
            box.setText(f"{success_count} dataset(s) completed and {failure_count} failed.")
            box.setDetailedText(detail)
            box.exec_()
        else:
            QMessageBox.information(
                self,
                "Download complete",
                f"{success_count} dataset(s) were downloaded and prepared successfully.",
            )

    def _clear_cache(self):
        if not os.path.exists(self.controller.cache_root):
            QMessageBox.information(self, "Cache", "The Natural Earth cache is already empty.")
            return
        answer = QMessageBox.question(
            self,
            "Clear download cache",
            "Delete cached Natural Earth ZIP files and extracted source data?\n\nSaved output files will not be affected.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            try:
                shutil.rmtree(self.controller.cache_root)
                QMessageBox.information(self, "Cache cleared", "The download cache was cleared.")
            except OSError as exc:
                QMessageBox.critical(self, "Cache error", f"The cache could not be cleared:\n{exc}")

    def _show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle("About Natural Earth Downloader")
        box.setIcon(QMessageBox.Information)
        box.setTextFormat(Qt.RichText)
        box.setText("""
            <h3>Natural Earth Downloader 0.1.2</h3>
            <p>Batch-download Natural Earth vector data into QGIS as GeoPackage, GeoJSON,
            ESRI Shapefile, or temporary layers.</p>
            <p><b>Data licence:</b> Natural Earth vector and raster data are in the public domain.</p>
            <p>This plugin is an independent project and is not affiliated with or endorsed by
            Natural Earth or NACIS.</p>
            <p><a href='https://www.naturalearthdata.com/about/terms-of-use/'>Natural Earth terms of use</a></p>
        """)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec_()

    @staticmethod
    def _human_size(value):
        value = float(max(0, value))
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024

    def closeEvent(self, event):
        if self.is_running:
            answer = QMessageBox.question(
                self,
                "Download in progress",
                "Cancel the current batch and close the window?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.closing_after_cancel = True
            self.controller.cancel()
        event.accept()
