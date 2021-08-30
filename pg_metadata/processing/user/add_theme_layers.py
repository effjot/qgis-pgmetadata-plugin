__copyright__ = "Copyright 2020, 3Liz, Florian Jenn"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"
__revision__ = "$Format:%H$"

import os

import processing

from qgis.core import (
    Qgis,
    QgsProcessingException,
    QgsProcessingOutputString,
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
    OVERRIDE = "OVERRIDE"
    DATABASE_VERSION = "DATABASE_VERSION"
    THEME = "THEME"

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

        # param = QgsProcessingParameterBoolean(
        #     self.OVERRIDE,
        #     tr("Erase the schema {} ?").format(SCHEMA),
        #     defaultValue=False,
        # )
        # tooltip = tr("** Be careful ** This will remove data in the schema !")
        # if Qgis.QGIS_VERSION_INT >= 31600:
        #     param.setHelp(tooltip)
        # else:
        #     param.tooltip_3liz = tooltip
        # self.addParameter(param)

        param = QgsProcessingParameterString(
            self.THEME,
            tr("Theme to add")
        )
        self.addParameter(param)
        
        self.addOutput(
            QgsProcessingOutputString(self.DATABASE_VERSION, tr("Database version"))
        )

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
        
        # # Drop schema if needed
        # override = self.parameterAsBool(parameters, self.OVERRIDE, context)
        # if override and SCHEMA in connection.schemas():
        #     feedback.pushInfo(tr("Removing the schema {}…").format(SCHEMA))
        #     try:
        #         connection.dropSchema(SCHEMA, True)
        #     except QgsProviderConnectionException as e:
        #         raise QgsProcessingException(str(e))

        # # Create full structure
        # sql_files = [
        #     "00_initialize_database.sql",
        #     "{}/10_FUNCTION.sql".format(SCHEMA),
        #     "{}/20_TABLE_SEQUENCE_DEFAULT.sql".format(SCHEMA),
        #     "{}/30_VIEW.sql".format(SCHEMA),
        #     "{}/40_INDEX.sql".format(SCHEMA),
        #     "{}/50_TRIGGER.sql".format(SCHEMA),
        #     "{}/60_CONSTRAINT.sql".format(SCHEMA),
        #     "{}/70_COMMENT.sql".format(SCHEMA),
        #     "{}/90_GLOSSARY.sql".format(SCHEMA),
        #     "99_finalize_database.sql",
        # ]

        # plugin_dir = plugin_path()
        # plugin_version = version()
        # dev_version = False
        # run_migration = os.environ.get(
        #     "TEST_DATABASE_INSTALL_{}".format(SCHEMA.upper())
        # )
        # if plugin_version in ["master", "dev"] and not run_migration:
        #     feedback.reportError(
        #         "Be careful, running the install on a development branch!"
        #     )
        #     dev_version = True

        # if run_migration:
        #     plugin_dir = plugin_test_data_path()
        #     feedback.reportError(
        #         "Be careful, running migrations on an empty database using {} "
        #         "instead of {}".format(run_migration, plugin_version)
        #     )
        #     plugin_version = run_migration

        # # Loop sql files and run SQL code
        # for sql_file in sql_files:
        #     feedback.pushInfo(sql_file)
        #     sql_file = os.path.join(plugin_dir, "install/sql/{}".format(sql_file))
        #     with open(sql_file, "r") as f:
        #         sql = f.read()
        #         if len(sql.strip()) == 0:
        #             feedback.pushInfo("  Skipped (empty file)")
        #             continue

        #         try:
        #             connection.executeSql(sql)
        #         except QgsProviderConnectionException as e:
        #             connection.executeSql("ROLLBACK;")
        #             raise QgsProcessingException(str(e))
        #         feedback.pushInfo("  Success !")

        # # Add version
        # if run_migration or not dev_version:
        #     metadata_version = plugin_version
        # else:
        #     migrations = available_migrations(000000)
        #     last_migration = migrations[-1]
        #     metadata_version = (
        #         last_migration.replace("upgrade_to_", "").replace(".sql", "").strip()
        #     )
        #     feedback.reportError("Latest migration is {}".format(metadata_version))

        # self.vacuum_all_tables(connection, feedback)

        # sql = """
        #     INSERT INTO {}.qgis_plugin
        #     (id, version, version_date, status)
        #     VALUES (0, '{}', now()::timestamp(0), 1)""".format(SCHEMA, metadata_version)

        # try:
        #     connection.executeSql(sql)
        # except QgsProviderConnectionException as e:
        #     connection.executeSql("ROLLBACK;")
        #     raise QgsProcessingException(str(e))
        # feedback.pushInfo("Database version '{}'.".format(metadata_version))

        # if not run_migration:
        #     self.install_html_templates(feedback, connection_name, context)
        # else:
        #     feedback.reportError(
        #         'As you are running an old version of the database, HTML templates are not installed.')

        # add_connection(connection_name)

        sql = "  SELECT d.schema_name, d.table_name"
        sql += " FROM pgmetadata.dataset d"
        sql += " INNER JOIN pgmetadata.v_valid_dataset v"
        sql += " ON concat(v.table_name, '.', v.schema_name) = concat(d.table_name, '.', d.schema_name)"
        sql += " WHERE '{}' = any (themes)".format(theme_id)

        try:
            data = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            self.logMessage(str(e), Qgis.Critical)
            return

        if not data:
            feedback.reportError(tr("No tables found for theme {theme}.").format(theme=theme_id))
            return {}
        
        feedback.pushInfo(f"erster {data[0]}, zweiter {data[1]}")
            
        return {}
