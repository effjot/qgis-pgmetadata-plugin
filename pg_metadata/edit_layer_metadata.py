# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: praktikum2
"""

import logging
from collections import OrderedDict

from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsProviderConnectionException

from PyQt5.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt

from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui
from qgis.PyQt.QtGui import QIntValidator

LOGGER = logging.getLogger('pg_metadata')
EDITDIALOG_CLASS = load_ui('edit_metadata_dialog.ui')

#TODO fenster immer im Vordergrund?
#TODO bei 'OK' metadaten sofort anzeigen


def postgres_array_to_list(s: str) -> list[str]:
    l = s[1:-1].split(',')
    if len(l[0]) > 0:
        return l
    else:
        return []


def list_to_postgres_array(lst: list[str]) -> str:
    if not lst:
        return "'{}'"
    l = ["'" + element + "'" for element in lst]
    return 'array[' + ','.join(l) + ']'


def dict_reverse_lookup(dictionary: dict, values: list) -> list:
    return [key for key, val in dictionary.items() if val in values]


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


def get_themes(connection) -> OrderedDict:
    sql = "SELECT code, label FROM pgmetadata.theme ORDER BY label"
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
        validator = QIntValidator(1,100000000,self)
        self.lineEdit_minimum_optimal_scale.setValidator(validator)
        self.lineEdit_maximum_optimal_scale.setValidator(validator)
        self.tabWidget.currentChanged.connect(self.edit_links)
        
        # self.table_widget = QTableWidget(101, 2)
        # self.widget_layout.addWidget(self.table_widget)
        # self.setLayout(self.widget_layout)
        # self.fillTable()

    def open_editor(self, datasource_uri, connection):
        table = datasource_uri.table()
        schema = datasource_uri.schema()
        LOGGER.info(f'Edit layer type {datasource_uri.table()}, {connection}')
        sql = (f"SELECT title, abstract, project_number, categories, keywords, themes, minimum_optimal_scale, maximum_optimal_scale, data_last_update, id, spatial_level FROM pgmetadata.dataset "
               f"WHERE schema_name = '{schema}' and table_name = '{table}'")
        try:
            data = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when querying the database: ') + str(e))
            return False
        
        dataset_id = data[0][9]  # get foreign key for links-table
        
        self.textbox_title.setPlainText(data[0][0])
        self.textbox_abstract.setPlainText(data[0][1])
        self.textbox_project_number.setPlainText(data[0][2])
        self.textbox_keywords.setPlainText(str(data[0][4]))
        if data[0][6]:
            self.lineEdit_minimum_optimal_scale.setText(str(data[0][6]))
        else: self.lineEdit_minimum_optimal_scale.clear()
        if data[0][7]:
            self.lineEdit_maximum_optimal_scale.setText(str(data[0][7]))
        else: self.lineEdit_maximum_optimal_scale.clear()
        if data[0][10]:
            self.textbox_spatial_level.setPlainText(data[0][10])
        else: self.textbox_spatial_level.clear()
        
        
        # get categories and fill comboBox
        self.comboBox_categories.clear()
        categories = get_glossary(connection, 'dataset.categories')
        self.comboBox_categories.addItems(categories.values())  # fill comboBox with categories
        selected_categories_keys = postgres_array_to_list(data[0][3])
        selected_categories_values = []
        for i in selected_categories_keys:
            selected_categories_values.append(categories[i])
        self.comboBox_categories.setCheckedItems(selected_categories_values)  # set selected categories as checked
        
        # get themes and fill comboBox
        self.comboBox_themes.clear()
        themes = get_themes(connection)
        if themes:
            self.comboBox_themes.addItems(themes.values())  # fill comboBox with themes
            selected_themes_keys = postgres_array_to_list(data[0][5])
            if selected_themes_keys:
                selected_themes_values = [themes[k] for k in selected_themes_keys]
                self.comboBox_themes.setCheckedItems(selected_themes_values)  # set selected themes as checked
        
        self.show()
        result = self.exec_()
        if not result:
            return False
        
        title = self.textbox_title.toPlainText()
        abstract = self.textbox_abstract.toPlainText()
        project_number = self.textbox_project_number.toPlainText()
        keywords = self.textbox_keywords.toPlainText()
        
        spatial_level = self.textbox_spatial_level.toPlainText()
        
        minimum_optimal_scale = self.lineEdit_minimum_optimal_scale.text()
        maximum_optimal_scale = self.lineEdit_maximum_optimal_scale.text()
        if not minimum_optimal_scale:
            minimum_optimal_scale = 'NULL'
        if not maximum_optimal_scale:
            maximum_optimal_scale = 'NULL'
        
        
        
        #QMessageBox.warning(self, 'Information', f'something')
        
        new_categories_keys = dict_reverse_lookup(categories, self.comboBox_categories.checkedItems())
        new_categories_array = list_to_postgres_array(new_categories_keys)
        
        new_themes_keys = dict_reverse_lookup(themes, self.comboBox_themes.checkedItems())
        new_themes_array = list_to_postgres_array(new_themes_keys)
        
        sql = (f"UPDATE pgmetadata.dataset SET title = '{title}', abstract = '{abstract}', project_number = '{project_number}', "
               f" keywords = '{keywords}', categories = {new_categories_array}, themes = {new_themes_array}, "
               f" minimum_optimal_scale = {minimum_optimal_scale}, maximum_optimal_scale = {maximum_optimal_scale}, spatial_level = '{spatial_level}' "
               f"WHERE schema_name = '{schema}' and table_name = '{table}'")
        
        try:
            connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when updating the database: ') + str(e))
            return False
        
        
        
        # links_sql = f"SELECT * FROM pgmetadata.link WHERE fk_id_dataset = {dataset_id} ORDER BY id ASC"
        # linkdata = connection.executeSql(links_sql)
        # QMessageBox.warning(self, 'Information', f'Linkdata looks like this: {linkdata}')
        
        
        
        
        
        return True

    def edit_links(self, connection):
        pass
        # if not self.tabWidget.currentIndex() == 3: return #Third tab is "links" tab
        
        # sql = f"SELECT * FROM pgmetadata.link WHERE fk_id_dataset = {dataset_id} ORDER BY id ASC"
        
        # try:
        #     data = connection.executeSql(sql)
        # except QgsProviderConnectionException as e:
        #     LOGGER.critical(tr('Error when updating the database: ') + str(e))
        #     return False
        
        # return True
        
    def fill_table(self):
        pass
        # self.table_widget.clearContents()
        # self.table_widget.setSortingEnabled(False)
        # #self.table_widget.sortByColumn(0, Qt.AscendingOrder)
        # for num in range(101):
        #     item = QTableWidgetItem()
        #     item.setData(Qt.EditRole, num)
        #     self.table_widget.setItem(num, 0, item)
        #     item2 = QTableWidgetItem()
        #     item2.setData(Qt.EditRole, num)
        #     self.table_widget.setItem(num, 1, item2)
        # self.table_widget.setSortingEnabled(True)
