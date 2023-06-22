__copyright__ = "Copyright 2020, 3Liz"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"

from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsLayerItem,
    QgsLayerTreeLayer,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import NULL
from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface

from pg_metadata.qgis_plugin_tools.tools.resources import resources_path


FIX_INVALID_CONNECTIONS_QUIETLY = True  # Do not show message bars and dialogs for invalid DB connections


def icon_for_geometry_type(geometry_type: str) -> QIcon():
    """ Return the correct icon according to the geometry type. """
    if geometry_type == NULL:
        return QgsLayerItem.iconTable()

    elif geometry_type in ('POINT', 'MULTIPOINT'):
        return QgsLayerItem.iconPoint()

    elif geometry_type in ('LINESTRING', 'MULTILINESTRING'):
        return QgsLayerItem.iconLine()

    elif geometry_type in ('POLYGON', 'MULTIPOLYGON'):
        return QgsLayerItem.iconPolygon()
    
    elif geometry_type == 'RASTER':
        return QgsLayerItem.iconRaster()

    # Default icon
    return QIcon(resources_path('icons', 'icon.png'))


def add_layer(connection, schema_name, table_name, geometry_type, title,
              group=None, index: int = None):
    QgsMessageLog.logMessage(f'Adding layer "{connection}"."{schema_name}"."{table_name}"'
                             f' as "{title}", {geometry_type=} to {group.name()=}',
                             'PgMetadata', level=Qgis.Info)
    table = connection.table(schema_name, table_name)
    uri = QgsDataSourceUri(connection.uri())
    uri.setSchema(schema_name)
    uri.setTable(table_name)
    uri.setGeometryColumn(table.geometryColumn())
    geom_types = table.geometryColumnTypes()
    if geom_types:
        # Take the first one
        uri.setWkbType(geom_types[0].wkbType)  # Unfortunately, there is no wkbType for raster
                                               # (only “unknown“), so we cannot use this below
    # TODO, we should try table.crsList() and uri.setSrid()
    pk = table.primaryKeyColumns()
    if pk:
        uri.setKeyColumn(pk[0])

    if geometry_type != 'RASTER':
        layer = QgsVectorLayer(uri.uri(), title, 'postgres')
        # Maybe there is a default style, you should load it
        layer.loadDefaultStyle()
    else:
        layer = QgsRasterLayer(uri.uri(), title, 'postgresraster')
        # NOTE: raster styles cannot be stored in database yet

    if not group and not index:
        res = QgsProject.instance().addMapLayer(layer) #, addToLegend)
        return res
    if not group:
        group = QgsProject.instance().layerTreeRoot()
    if not index:
        res = group.addLayer(layer)
    else:
        res = group.insertLayer(index, layer)
    return res


def add_group(group_name, index: int = None):
    """Add a new group at given index or at default position (above selected layer)"""
    if not index:
        active = iface.activeLayer()
        
        root = QgsProject.instance().layerTreeRoot()
        active_node = root.findLayer(active)
        parent_group = active_node.parent()
        index = parent_group.children().index(active_node)

    new_group = parent_group.insertGroup(index, group_name)
    return new_group
