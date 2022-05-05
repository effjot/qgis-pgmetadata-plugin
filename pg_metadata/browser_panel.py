import sip

from qgis.core import (
    QgsApplication,
    QgsDataCollectionItem,
    QgsDataItem,
    QgsDataItemProvider,
    QgsDataProvider,
    QgsDirectoryItem,
)
from qgis.PyQt.QtGui import QIcon

from pg_metadata.qgis_plugin_tools.tools.resources import (
#    plugin_path,
    resources_path,
)


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
        items = []

        th_1 = PgMetadataBrowserGroupItem(self, "Theme 1", "icon.png", self.plugin)
        th_1.setState(QgsDataItem.Populated)
        th_1.refresh()
        sip.transferto(th_1, self)
        items.append(th_1)

        th_2 = PgMetadataBrowserGroupItem(self, "Theme 2", None, self.plugin)
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

