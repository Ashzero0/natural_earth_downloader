# Natural Earth Downloader for QGIS

Installable QGIS plugin prototype for browsing and downloading several Natural Earth vector datasets in one batch.

## Features

- Clean searchable catalogue with scale, category and geometry filters.
- Multi-selection and **Select visible** workflow.
- Outputs:
  - one GeoPackage containing several layers;
  - one GeoJSON per dataset;
  - one ESRI Shapefile set per dataset;
  - temporary QGIS memory layers.
- QGIS-aware networking through `QgsNetworkAccessManager`.
- Sequential downloads with progress, cancellation and per-layer error handling.
- Local archive and extraction cache.
- Safe ZIP extraction checks.
- Optional automatic loading and simple styling.
- No third-party Python packages.

## Install

1. In QGIS, open **Plugins → Manage and Install Plugins**.
2. Open **Install from ZIP**.
3. Select `natural_earth_downloader_v1.zip`.
4. Accept the experimental-plugin warning if QGIS displays one.
5. Open **Vector → Natural Earth Downloader** or use the toolbar button.

Test target: QGIS 3.44. Minimum metadata version: QGIS 3.22.

## Recommended first test

1. Filter scale to **1:110m**.
2. Select **Countries**, **Land**, **Ocean**, **Lakes**, and **Rivers and lake centerlines**.
3. Keep the default GeoPackage output.
4. Download and verify that all layers appear in the project.

## Catalogue design

The catalogue is curated in `catalog.py`. Direct Natural Earth archive URLs follow this pattern:

```text
https://naturalearth.s3.amazonaws.com/{scale}_{category}/ne_{scale}_{dataset}.zip
```

The initial catalogue focuses on common cultural and physical vector layers. It can be expanded by adding entries to `THEMES`.

## Cache

The plugin cache is stored below the active QGIS profile directory:

```text
cache/natural_earth_downloader/
```

Use **Clear cache** in the plugin to remove downloaded ZIP archives and extracted source files. Saved outputs are not removed.

## Licence and attribution

Plugin code: GNU GPL v2 or later.

Natural Earth vector and raster datasets are public domain. Attribution is not required, but the plugin identifies Natural Earth as the data source. This plugin is independent and is not affiliated with or endorsed by Natural Earth or NACIS.

## Known prototype limitations

- Vector datasets only; raster support is not included yet.
- Conversion and extraction occur in the main QGIS thread after each download. Very large layers may briefly pause the interface.
- The catalogue is curated rather than fetched dynamically.
- Styling is intentionally simple and does not reproduce the full Natural Earth Quick Start styling.
