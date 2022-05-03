__copyright__ = "Copyright 2021, 3Liz"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"


from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, Qt, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.utils import iface

from pg_metadata.browser_panel import DataItemProvider
from pg_metadata.dock import PgMetadataDock
from pg_metadata.locator import LocatorFilter
from pg_metadata.processing.provider import PgMetadataProvider
from pg_metadata.qgis_plugin_tools.tools.custom_logging import setup_logger
from pg_metadata.qgis_plugin_tools.tools.i18n import setup_translation, tr
from pg_metadata.qgis_plugin_tools.tools.resources import (
    plugin_path,
    resources_path,
)


class PgMetadata:
    def __init__(self):
        """ Constructor. """
        self.dock = None
        self.provider = None
        self.locator_filter = None
        self.dock_action = None
        self.help_action = None

        setup_logger('pg_metadata')

        locale, file_path = setup_translation(
            folder=plugin_path("i18n"), file_pattern="pgmetadata_{}.qm")
        if file_path:
            self.translator = QTranslator()
            self.translator.load(file_path)
            # noinspection PyCallByClass,PyArgumentList
            QCoreApplication.installTranslator(self.translator)

    def initProcessing(self):
        """ Add the QGIS Processing provider. """
        if not self.provider:
            self.provider = PgMetadataProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        """ Build the plugin GUI. """
        self.initProcessing()

        icon = QIcon(resources_path('icons', 'icon.png'))

        # Open the online help
        self.help_action = QAction(icon, 'PgMetadata', iface.mainWindow())
        iface.pluginHelpMenu().addAction(self.help_action)
        self.help_action.triggered.connect(self.open_help)

        if not self.dock:
            self.dock = PgMetadataDock()
            iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)

            # Open/close the dock from plugin menu
            self.dock_action = QAction(icon, 'PgMetadata', iface.mainWindow())
            iface.pluginMenu().addAction(self.dock_action)
            self.dock_action.triggered.connect(self.open_dock)

        if not self.locator_filter:
            self.locator_filter = LocatorFilter(iface)
            iface.registerLocatorFilter(self.locator_filter)

        # Item in Add Layers menu for loading all layers from Theme
        self.addtheme_action = QAction(icon,
                                       tr('Add all Layers from PgMetadata Theme…'),
                                       iface.mainWindow())
        iface.addLayerMenu().addAction(self.addtheme_action)
        self.addtheme_action.triggered.connect(self.dock.add_theme_layers)
        
        # Add custom provider to Browser panel for adding Themes
        self.data_item_provider = DataItemProvider(self)
        QgsApplication.instance().dataItemProviderRegistry().addProvider(self.data_item_provider)

    @staticmethod
    def open_help():
        """ Open the online help. """
        QDesktopServices.openUrl(QUrl('https://docs.3liz.org/qgis-pgmetadata-plugin/'))

    def open_dock(self):
        """ Open the dock. """
        self.dock.show()
        self.dock.raise_()

    def unload(self):
        """ Unload the plugin. """
        if self.dock:
            iface.removeDockWidget(self.dock)
            self.dock.deleteLater()

        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            del self.provider

        if self.locator_filter:
            iface.deregisterLocatorFilter(self.locator_filter)
            del self.locator_filter

        if self.dock_action:
            iface.pluginMenu().removeAction(self.dock_action)
            del self.dock_action

        if self.help_action:
            iface.pluginHelpMenu().removeAction(self.help_action)
            del self.help_action
            
        if self.addtheme_action:
             iface.addLayerMenu().removeAction(self.addtheme_action)

        if self.data_item_provider:
            QgsApplication.instance().dataItemProviderRegistry().removeProvider(self.data_item_provider)
            self.data_item_provider = None

    @staticmethod
    def run_tests(pattern='test_*.py', package=None):
        """Run the test inside QGIS."""
        try:
            from pathlib import Path

            from pg_metadata.qgis_plugin_tools.infrastructure.test_runner import (
                test_package,
            )
            if package is None:
                package = '{}.__init__'.format(Path(__file__).parent.name)
            test_package(package, pattern)
        except (AttributeError, ModuleNotFoundError):
            message = 'Could not load tests. Are you using a production package?'
            print(message) # NOQA
