# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: praktikum2
"""

import logging
from collections import OrderedDict

from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsProviderConnectionException

from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui

LOGGER = logging.getLogger('pg_metadata')
EDITDIALOG_CLASS = load_ui('edit_metadata_dialog.ui')


def postgres_array_to_list(s: str) -> list[str]:
    return s[1:-1].split(',')


def get_glossary(connection, field: str) -> OrderedDict:
    sql = f"SELECT code, label_de FROM pgmetadata.glossary WHERE field = '{field}' ORDER BY item_order"
    try:
        rows = connection.executeSql(sql)
    except QgsProviderConnectionException as e:
        LOGGER.critical(tr('Error when querying the database: ') + str(e))
        return False
    terms = OrderedDict()
    for row in rows:
        terms[row[0]] = row[1]
    return terms


class PgMetadataLayerEditor(QDialog, EDITDIALOG_CLASS):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)

    def open_editor(self, datasource_uri, connection):
        table = datasource_uri.table()
        schema = datasource_uri.schema()
        LOGGER.info(f'Edit layer type {datasource_uri.table()}, {connection}')
        sql = (f"SELECT title, abstract, project_number, categories, keywords, themes FROM pgmetadata.dataset "
               f"WHERE schema_name = '{schema}' and table_name = '{table}'")
        try:
            data = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when querying the database: ') + str(e))
            return False
        
        self.textbox_title.setPlainText(data[0][0])
        self.textbox_abstract.setPlainText(data[0][1])
        self.textbox_project_number.setPlainText(data[0][2])
        self.textbox_keywords.setPlainText(str(data[0][4]))
        #self.textbox_themes.setPlainText(data[0][5])
        
        # get categories and fill comboBox
        categories = get_glossary(connection, 'dataset.categories')
        selected_categories_keys = postgres_array_to_list(data[0][3])
        selected_categories_values = []
        for i in selected_categories_keys:
            selected_categories_values.append(categories[i])
        self.comboBox_categories.addItems(categories.values())  # fill comboBox with categories
        self.comboBox_categories.setCheckedItems(selected_categories_values)  # set selected categories as checked
        
        self.show()
        result = self.exec_()
        if not result:
            return False

        title = self.textbox_title.toPlainText()
        abstract = self.textbox_abstract.toPlainText()
        project_number = self.textbox_project_number.toPlainText()
        keywords = self.textbox_keywords.toPlainText()
        themes = self.textbox_themes.toPlainText()
        
        sql = (f"UPDATE pgmetadata.dataset SET title = '{title}', abstract = '{abstract}', project_number = '{project_number}', "
               f" keywords = '{keywords}', themes = '{themes}', "
               f"WHERE schema_name = '{schema}' and table_name = '{table}'")
        try:
            connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when updating the database: ') + str(e))
            return False
        
        return True