import sip

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsDataCollectionItem,
    QgsDataItem,
    QgsDataItemProvider,
    QgsDataProvider,
    QgsDirectoryItem,
    QgsMessageLog,
)
from qgis.PyQt.QtGui import QIcon

from pg_metadata.connection_manager import (
    check_pgmetadata_is_installed,
    connections_list,
    settings_connections_names,
)
from pg_metadata.qgis_plugin_tools.tools.resources import resources_path
from pg_metadata.tools import fetch_themes_single_database


class DataItemProvider(QgsDataItemProvider):
    def __init__(self, plugin):
        QgsDataItemProvider.__init__(self)
        self.root_item = None
        self.plugin = plugin

    def name(self):
        return "PgMetadataProvider"

    def capabilities(self):
        return QgsDataProvider.Database

    def createDataItem(self, path, parentItem):
        if not parentItem:
            root_item = PgMetadataBrowserRootItem(self.plugin)
            sip.transferto(root_item, None)
            self.root_item = root_item
            return root_item
        else:
            return None


class PgMetadataBrowserRootItem(QgsDataCollectionItem):
    def __init__(self, plugin=None):
        QgsDataCollectionItem.__init__(self, None, 'PgMetadata', 'PgMetadata')
        self.setIcon(QIcon(resources_path('icons', 'icon.png')))
        self.plugin = plugin

    def createChildren(self):
        connections, message = connections_list()
        connection_name = connections[0]
        non_empty_themes = fetch_themes_single_database(connection_name)
        QgsMessageLog.logMessage(f'Found themes: {non_empty_themes}', 'PgMetadata', level=Qgis.Info)

        items = []

        code, label = non_empty_themes.popitem()
        th_1 = PgMetadataBrowserGroupItem(self, label, "icon.png", self.plugin)
        th_1.setState(QgsDataItem.Populated)
        th_1.refresh()
        sip.transferto(th_1, self)
        items.append(th_1)

        code, label = non_empty_themes.popitem()
        th_2 = PgMetadataBrowserGroupItem(self, label, None, self.plugin)
        th_2.setState(QgsDataItem.Populated)
        th_2.refresh()
        sip.transferto(th_2, self)
        items.append(th_2)

        return items


class PgMetadataBrowserGroupItem(QgsDataCollectionItem):
    def __init__(self, parent, grp_name, icon, plugin):
        QgsDataCollectionItem.__init__(self, parent, grp_name, "/PgMetadata" + grp_name)
        if icon:
            self.setIcon(QIcon(resources_path('icons', icon)))
        else:
            self.setIcon(QgsApplication.getThemeIcon('/mActionAddGroup.svg'))
        self.plugin = plugin
        self.group_name = grp_name

    def createChildren(self):
        items = []
        item = PgMetadataBrowserItem(self)
        sip.transferto(item, self)
        items.append(item)
        return items


class PgMetadataBrowserItem(QgsDirectoryItem):
    def __init__(self, parent):
        self.project_name = 'prj name'
        self.path = 'pathpath'
        QgsDirectoryItem.__init__(self, parent, self.project_name, self.path, "/PgMetadata/" + self.project_name)
        self.setSortKey(f"1 {self.name()}")

