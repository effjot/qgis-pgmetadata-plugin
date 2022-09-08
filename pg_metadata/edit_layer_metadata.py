# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: praktikum2
"""

import logging

from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsProviderConnectionException

from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui

LOGGER = logging.getLogger('pg_metadata')
EDITDIALOG_CLASS = load_ui('edit_metadata_dialog.ui')


# @dataclass
# class PgEditorValues:
#     title: str
#     abstract: str


class PgMetadataLayerEditor(QDialog, EDITDIALOG_CLASS):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)

    def open_editor(self, datasource_uri, connection):
        #self.show()
        table = datasource_uri.table()
        schema = datasource_uri.schema()
        LOGGER.critical(f'Edit layer type {datasource_uri.table()}, {connection}')
        sql = f"select title, abstract, project_number from pgmetadata.dataset where schema_name = '{schema}' and table_name = '{table}'"
        try:
            data = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when querying the database: ') + str(e))
            return False
        
        self.textbox_title.setPlainText(data[0][0])
        self.textbox_abstract.setPlainText(data[0][1])
        self.textbox_project_number.setPlainText(data[0][2])
        
        self.show()
        result = self.exec_()
        if not result:
            return False

        title = self.textbox_title.toPlainText()
        abstract = self.textbox_abstract.toPlainText()
        project_number = self.textbox_project_number.toPlainText()
        sql = (f"UPDATE pgmetadata.dataset SET title = '{title}', abstract = '{abstract}', project_number = '{project_number}' "
               f"WHERE schema_name = '{schema}' and table_name = '{table}'")
        try:
            connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when updating the database: ') + str(e))
            return False
        
        return True