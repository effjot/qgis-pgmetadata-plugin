__copyright__ = "Copyright 2020, 3Liz, Florian Jenn"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"
__revision__ = "$Format:%H$"

import os

import processing

from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsProject,
    QgsVectorLayer,
    QgsProcessingException,
    QgsProcessingOutputString,
    QgsProcessingOutputMultipleLayers,
    QgsProcessingOutputVectorLayer,
    QgsProcessingContext,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterString,
    QgsProviderConnectionException,
    QgsProviderRegistry,
)

if Qgis.QGIS_VERSION_INT >= 31400:
    from qgis.core import QgsProcessingParameterProviderConnection

from pg_metadata.connection_manager import add_connection, connections_list
from pg_metadata.qgis_plugin_tools.tools.algorithm_processing import (
    BaseProcessingAlgorithm,
)
from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import (
    plugin_path,
    plugin_test_data_path,
)
from pg_metadata.qgis_plugin_tools.tools.version import version

SCHEMA = 'pgmetadata'


class AddThemeLayers(BaseProcessingAlgorithm):
    """
    Add all layers belonging to a metadata theme
    """

    CONNECTION_NAME = "CONNECTION_NAME"
    THEME = "THEME"
    OUTPUT = "OUTPUT"
    
    def name(self):
        return "add_theme_layers"

    def displayName(self):
        return tr("Add theme layers")

    def group(self):
        return tr('User')

    def groupId(self):
        return 'user'

    def shortHelpString(self):
        msg = tr(
            "This will add all layers marked with the selected theme to the project.")
        msg += '\n\n'
        msg += self.parameters_help_string()
        return msg

    def initAlgorithm(self, config):
        connections, _ = connections_list()
        if connections:
            connection_name = connections[0]
        else:
            connection_name = ''

        label = tr("Connection to the PostgreSQL database")
        tooltip = tr("The database where the schema '{}' is installed.").format(SCHEMA)
        if Qgis.QGIS_VERSION_INT >= 31400:
            param = QgsProcessingParameterProviderConnection(
                self.CONNECTION_NAME,
                label,
                "postgres",
                defaultValue=connection_name,
                optional=False,
            )
        else:
            param = QgsProcessingParameterString(
                self.CONNECTION_NAME,
                label,
                defaultValue=connection_name,
                optional=False,
            )
            param.setMetadata(
                {
                    "widget_wrapper": {
                        "class": "processing.gui.wrappers_postgis.ConnectionWidgetWrapper"
                    }
                }
            )
        if Qgis.QGIS_VERSION_INT >= 31600:
            param.setHelp(tooltip)
        else:
            param.tooltip_3liz = tooltip
        self.addParameter(param)

        param = QgsProcessingParameterString(
            self.THEME,
            tr("Theme to add")
        )
        self.addParameter(param)

        # Output is set of layers
        self.addOutput(
            #QgsProcessingOutputMultipleLayers(
            QgsProcessingOutputVectorLayer(
                self.OUTPUT,
                tr("Resulting layers"),
                #type=QgsProcessing.TypeVectorAnyGeometry
            )
        )
        #self.addParameter(param)


    def checkParameterValues(self, parameters, context):
        if Qgis.QGIS_VERSION_INT >= 31400:
            connection_name = self.parameterAsConnectionName(
                parameters, self.CONNECTION_NAME, context)
        else:
            connection_name = self.parameterAsString(
                parameters, self.CONNECTION_NAME, context)

        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        connection = metadata.findConnection(connection_name)
        if not connection:
            raise QgsProcessingException(tr("The connection {} does not exist.").format(connection_name))

        if SCHEMA not in connection.schemas():
            raise QgsProcessingException(tr("The schema {} does not exist "
                                            "in the database {}!").format(SCHEMA, connection_name))

        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        if Qgis.QGIS_VERSION_INT >= 31400:
            connection_name = self.parameterAsConnectionName(
                parameters, self.CONNECTION_NAME, context)
        else:
            connection_name = self.parameterAsString(
                parameters, self.CONNECTION_NAME, context)

        connection = metadata.findConnection(connection_name)
        if not connection:
            raise QgsProcessingException(tr("The connection {} does not exist.").format(connection_name))

        theme_id = self.parameterAsString(parameters, self.THEME, context)
        
        sql = "  SELECT d.schema_name, d.table_name"
        sql += " FROM pgmetadata.dataset d"
        sql += " INNER JOIN pgmetadata.v_valid_dataset v"
        sql += " ON concat(v.table_name, '.', v.schema_name) = concat(d.table_name, '.', d.schema_name)"
        sql += " WHERE '{}' = any (themes)".format(theme_id)

        try:
            layers = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            self.logMessage(str(e), Qgis.Critical)
            return

        if not layers:
            feedback.reportError(tr("No tables found for theme {theme}.").format(theme=theme_id))
            return {}
        
        feedback.pushInfo(f"erster {layers[0]}, zweiter {layers[1]}")
        
        layer = layers[0]
        
        # code for adding layer taken from locator.py
        schema_name = layer[0]
        table_name = layer[1]
        feedback.pushInfo(f"Lade {schema_name}.{table_name}.")
        
        if Qgis.QGIS_VERSION_INT < 31200:
            table = [t for t in connection.tables(schema_name) if t.tableName() == table_name][0]
        else:
            table = connection.table(schema_name, table_name)

        uri = QgsDataSourceUri(connection.uri())
        uri.setSchema(schema_name)
        uri.setTable(table_name)
        uri.setGeometryColumn(table.geometryColumn())
        geom_types = table.geometryColumnTypes()
        if geom_types:
            # Take the first one
            uri.setWkbType(geom_types[0].wkbType)
        # TODO, we should try table.crsList() and uri.setSrid()
        pk = table.primaryKeyColumns()
        if pk:
            uri.setKeyColumn(pk[0])

        feedback.pushInfo(f"uri: {uri}")
        #layer_to_add = QgsVectorLayer(uri.uri(), table_name, 'postgres')
        # Maybe there is a default style, you should load it
        #layer_to_add.loadDefaultStyle()
        #QgsProject.instance().addMapLayer(layer_to_add)

        #return {self.OUTPUT: layer_to_add}
        
        # from https://github.com/qgis/QGIS/blob/master/python/plugins/processing/algs/qgis/PostGISExecuteAndLoadSQL.py
        
        vlayer = QgsVectorLayer(uri.uri(), table_name, 'postgres')

        if not vlayer.isValid():
            raise QgsProcessingException(tr("""This layer is invalid!
                Please check the PostGIS log for error messages."""))

        context.temporaryLayerStore().addMapLayer(vlayer)
        context.addLayerToLoadOnCompletion(
            vlayer.id(),
            QgsProcessingContext.LayerDetails(table_name,
                                              context.project(),
                                              self.OUTPUT))

        return {self.OUTPUT: vlayer.id()}