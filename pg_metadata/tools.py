__copyright__ = "Copyright 2020, 3Liz"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"

from qgis.core import Qgis, QgsLayerItem, QgsProviderRegistry
from qgis.PyQt.QtCore import NULL
from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface

from pg_metadata.qgis_plugin_tools.tools.resources import resources_path

from pg_metadata.connection_manager import (
    check_pgmetadata_is_installed,
    connections_list,
    settings_connections_names,
)
from pg_metadata.qgis_plugin_tools.tools.i18n import tr


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

    elif geometry_type == 'RASTER':
        return QgsLayerItem.iconRaster()

    # Default icon
    return QIcon(resources_path('icons', 'icon.png'))


def fetch_themes_single_database(connection_name: str):
    metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
    con = metadata.findConnection(connection_name)

    sql = 'select distinct code, label from pgmetadata.v_themes_tables'

    #try:
    results = con.executeSql(sql)
    # except QgsProviderConnectionException as e:
    #     self.logMessage(str(e), Qgis.Critical)
    #     return

    if not results:
        iface.messageBar().pushMessage(tr("No themes containing layers defined in {}".format(connection_name)), level=Qgis.Warning)
        return

    non_empty_themes = dict(results)

    return non_empty_themes
