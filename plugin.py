# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .main_dialog import NaturalEarthDownloaderDialog


class NaturalEarthDownloaderPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        self.action = None
        self.dialog = None

        self.menu_name = self.tr("&Natural Earth Downloader")

        self.icon_path = os.path.join(
            self.plugin_dir,
            "resources",
            "icon.png"
        )

    def tr(self, text):
        return QCoreApplication.translate(
            "NaturalEarthDownloader",
            text
        )

    def initGui(self):
        icon = QIcon(self.icon_path)

        self.action = QAction(
            icon,
            self.tr("Natural Earth Downloader"),
            self.iface.mainWindow(),
        )

        self.action.setToolTip(
            self.tr("Download Natural Earth vector datasets")
        )

        self.action.triggered.connect(self.run)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu(
            self.menu_name,
            self.action
        )

    def run(self):
        if self.dialog is None:
            self.dialog = NaturalEarthDownloaderDialog(
                self.iface,
                self.iface.mainWindow()
            )

            self.dialog.setWindowIcon(
                QIcon(self.icon_path)
            )

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()