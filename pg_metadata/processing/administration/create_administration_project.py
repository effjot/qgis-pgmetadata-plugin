__copyright__ = "Copyright 2020, 3Liz"
__license__ = "GPL version 3"
__email__ = "info@3liz.org"
__revision__ = "$Format:%H$"

from qgis.core import (
    Qgis,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
    QgsProcessingParameterEnum,
    QgsProviderRegistry,
)

if Qgis.QGIS_VERSION_INT >= 31400:
    from qgis.core import QgsProcessingParameterProviderConnection

from pg_metadata.connection_manager import add_connection, connections_list
from pg_metadata.qgis_plugin_tools.tools.algorithm_processing import (
    BaseProcessingAlgorithm,
)
from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import resources_path

SCHEMA = 'pgmetadata'


class CreateAdministrationProject(BaseProcessingAlgorithm):

    CONNECTION_NAME = 'CONNECTION_NAME'
    PROJECT_FILE = 'PROJECT_FILE'
    
    PROJECT_LANG = 'PROJECT_LANG'
    LANG_CODES = ['en', 'fr', 'it', 'es', 'de']
    LANGUAGES = [tr('English'), tr('French'), tr('Italian'), tr('Spanish'), tr('German')]
    
    OUTPUT_STATUS = 'OUTPUT_STATUS'
    OUTPUT_STRING = 'OUTPUT_STRING'

    def name(self):
        return 'create_administration_project'

    def displayName(self):
        return tr('Create metadata administration project')

    def group(self):
        return tr('Administration')

    def groupId(self):
        return 'administration'

    def shortHelpString(self):
        short_help = tr(
            'This algorithm will create a new QGIS project file for PgMetadata administration purpose.')
        short_help += '\n\n'
        short_help += tr(
            'The generated QGIS project must then be opened by the administrator '
            'to create the needed metadata by using QGIS editing capabilities.')
        short_help += '\n\n'
        short_help += self.parameters_help_string()
        return short_help

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

        # target project file
        param = QgsProcessingParameterFileDestination(
            self.PROJECT_FILE,
            tr('QGIS project file to create'),
            defaultValue='',
            optional=False,
            fileFilter='QGS project (*.qgs)',
        )
        tooltip = tr("The destination file where to create the QGIS project.").format(SCHEMA)
        if Qgis.QGIS_VERSION_INT >= 31600:
            param.setHelp(tooltip)
        else:
            param.tooltip_3liz = tooltip
        self.addParameter(param)
        
        # target project language
        param = QgsProcessingParameterEnum(
            self.PROJECT_LANG,
            tr('Language for the metadata terms (glossary)'),
            options=self.LANGUAGES,
            defaultValue=0, optional=False)
        tooltip = tr('The language for the metadata terms (glossary).')
        if Qgis.QGIS_VERSION_INT >= 31600:
            param.setHelp(tooltip)
        else:
            param.tooltip_3liz = tooltip
        self.addParameter(param)
        

    def checkParameterValues(self, parameters, context):

        # Check if the target project file ends with qgs
        project_file = self.parameterAsString(parameters, self.PROJECT_FILE, context)
        if not project_file.endswith('.qgs'):
            return False, tr('The QGIS project file name must end with extension ".qgs"')

        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):

        if Qgis.QGIS_VERSION_INT >= 31400:
            connection_name = self.parameterAsConnectionName(
                parameters, self.CONNECTION_NAME, context)
        else:
            connection_name = self.parameterAsString(
                parameters, self.CONNECTION_NAME, context)

        # Write the file out again
        project_file = self.parameterAsString(parameters, self.PROJECT_FILE, context)

        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        connection = metadata.findConnection(connection_name)

        # Read in the template file
        template_file = resources_path('projects', 'pg_metadata_administration.qgs')
        with open(template_file, 'r') as fin:
            file_data = fin.read()

        # Replace the database connection information
        file_data = file_data.replace("service='pgmetadata'", connection.uri())

        # Replace the glossary language placeholder
        lang = self.LANG_CODES[self.parameterAsEnum(parameters, self.PROJECT_LANG, context)]
        file_data = file_data.replace('label_@LANG@', f'label_{lang}')
        file_data = file_data.replace('description_@LANG@', f'description_{lang}')

        with open(project_file, 'w') as fout:
            fout.write(file_data)

        add_connection(connection_name)

        msg = tr('QGIS Administration project has been successfully created from the database connection')
        msg += ': {}'.format(connection_name)
        feedback.pushInfo(msg)

        return {}
