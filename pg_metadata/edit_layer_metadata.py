# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: praktikum2
"""

import logging
from collections import OrderedDict

from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsProviderConnectionException
from PyQt5.QtWidgets import QMessageBox
from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui
from qgis.PyQt.QtGui import QIntValidator

LOGGER = logging.getLogger('pg_metadata')
EDITDIALOG_CLASS = load_ui('edit_metadata_dialog.ui')

#TODO bei 'OK' metadaten sofort anzeigen
#TODO falls nichts geändert, aber Ok gedrückt: Datum für Änderung der Metadaten unverändert lassen


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


def str_or_null(s: str):
    if s:
        return f"'{s}'"
    return 'null'


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


def get_links(connection, id_col: str, columns: list[str], from_where_clause: str) -> OrderedDict:
    columns.insert(0, id_col)
    sql = f"SELECT {', '.join(columns)} {from_where_clause}"
    try:
        rows = connection.executeSql(sql)
    except QgsProviderConnectionException as e:
        LOGGER.critical(tr('Error when querying the database: ') + str(e))
        return False
    terms = [dict(zip(columns, row)) for row in rows]
    terms_by_id = OrderedDict()
    for t in terms:
        terms_by_id[t[id_col]] = t
    return terms_by_id


def count_all_links(connection) -> OrderedDict():
    sql = "SELECT id, name FROM pgmetadata.link ORDER BY id ASC"
    try:
        rows = connection.executeSql(sql)
    except QgsProviderConnectionException as e:
        LOGGER.critical(tr('Error when querying the database: ') + str(e))
        return False
    terms = OrderedDict()
    for row in rows:
        terms[row[0]] = row[1]
    return len(terms)  #FIXME thier max statt len um doppelte ids zu vermeiden


class PgMetadataLayerEditor(QDialog, EDITDIALOG_CLASS):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        validator = QIntValidator(1,100000000,self)
        self.lineEdit_minimum_optimal_scale.setValidator(validator)
        self.lineEdit_maximum_optimal_scale.setValidator(validator)
        self.lineEdit_link_size.setValidator(validator)
        self.comboBox_linknames.activated.connect(self.fill_linkinfos)
        
        #TODO callback für Textfeld, sodass bei Änderung die Combobox neu befüllt wird
        #self.textbox_link_name.textChanged.connect(self.xxx)

    def fill_linkinfos(self):
        # empty all boxes from former entries
        self.textbox_link_name.clear()
        self.comboBox_link_types.setCurrentIndex(-1)
        self.textbox_link_url.clear()
        self.textbox_link_description.clear()
        self.textbox_link_format.clear()
        self.comboBox_link_mimes.setCurrentIndex(-1)
        self.lineEdit_link_size.clear()
        
        if self.comboBox_linknames.currentIndex() < 0:  #FIXME erforerlich??
            return
        
        # get ID of currently selected link
        self.current_link_id = self.comboBox_linknames.currentData()
        
        if self.current_link_id == 0: self.add_link()
        
        else:  # when an existing link is selected
            current_link = self.links[self.current_link_id]
            if current_link['name']:        self.textbox_link_name.setText(current_link['name'])
            index = self.comboBox_link_types.findData(current_link['type'])
            if current_link['type']:        self.comboBox_link_types.setCurrentIndex(index)
            if current_link['url']:         self.textbox_link_url.setText(current_link['url'])
            if current_link['description']: self.textbox_link_description.setText(current_link['description'])
            if current_link['format']:      self.textbox_link_format.setText(current_link['format'])
            index = self.comboBox_link_mimes.findData(current_link['mime'])
            if current_link['mime']:        self.comboBox_link_mimes.setCurrentIndex(index)
            if current_link['size']:        self.lineEdit_link_size.setText(str(current_link['size']))

    def update_links(self, connection):
        new_link_name = self.textbox_link_name.toPlainText()
        new_link_type = self.comboBox_link_types.currentData()
        new_link_url = self.textbox_link_url.toPlainText()
        new_link_description = self.textbox_link_description.toPlainText()
        new_link_format = self.textbox_link_format.toPlainText()
        new_link_mime = self.comboBox_link_mimes.currentData()
        new_link_size = self.lineEdit_link_size.text()
        if not new_link_size: new_link_size = 0
        
        if self.comboBox_linknames.currentData() !=  0:
            sql = f"UPDATE pgmetadata.link SET name = '{new_link_name}', type = '{new_link_type}', "
            sql += f"url = '{new_link_url}', description = '{new_link_description}', format = {str_or_null(new_link_format)}, mime = '{new_link_mime}', size = '{new_link_size}' "
            sql += f"WHERE id = {self.current_link_id}"
        else:
            if new_link_name:  # if name is chosen, new link will be written
                sql = f"INSERT INTO pgmetadata.link (id, name, type, url, description, format, mime, size, fk_id_dataset) "
                sql += f"VALUES ({self.count_links + 1}, '{new_link_name}', '{new_link_type}', '{new_link_url}', '{new_link_description}', "
                sql += f"'{new_link_format}', '{new_link_mime}', {new_link_size}, {self.dataset_id})"
            else:
                return
        try:
            connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when updating the database: ') + str(e))

    def add_link(self):  # called when "Neuer Link" is selected in ComboBox
        #.warning(self, 'Information', 'Funktion "Neuer Link" aufgerufen')
        #QMessageBox.warning(self, 'Information', f'Anzahl aller Links in der DB: {count_all_links()}')
        
        #check if mandatory fields are populated
        #TODO button for delete link
        pass

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
        
        # get foreign key for links-table
        self.dataset_id = data[0][9]
        
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
        
        # empty all textboxes for links
        self.textbox_link_name.clear()
        self.textbox_link_url.clear()
        self.textbox_link_description.clear()
        self.textbox_link_format.clear()
        self.lineEdit_link_size.clear()
        
        # get links and fill comboBox
        self.comboBox_linknames.clear()
        self.comboBox_linknames.addItem('Link hinzufügen...', 0)
        self.links = get_links(connection, 'id',
                  ['name', 'type', 'url', 'description', 'format', 'mime', 'size', 'fk_id_dataset'],
                  f"FROM pgmetadata.link WHERE fk_id_dataset = {self.dataset_id} ORDER BY type")
        for link in self.links.values():
            self.comboBox_linknames.addItem(link['name'], link['id'])
        self.comboBox_linknames.setCurrentIndex(0)
        
        # get link types and fill comboBox
        self.comboBox_link_types.clear()
        link_types = get_links(connection, 'id', ['code', 'label_en', 'description_en'], "FROM pgmetadata.glossary WHERE field='link.type'")
        for link_type in link_types.values():
            self.comboBox_link_types.addItem(f"{link_type['code']} = {link_type['label_en']}", link_type['code'])
        self.comboBox_link_types.setCurrentIndex(-1)
        
        # get link mimes and fill comboBox
        self.comboBox_link_mimes.clear()
        link_mimes = get_links(connection, 'id', ['code', 'label_en', 'description_en'], "FROM pgmetadata.glossary WHERE field='link.mime'")
        for link_mime in link_mimes.values():
            self.comboBox_link_mimes.addItem(link_mime['label_en'], link_mime['code'])
        self.comboBox_link_mimes.setCurrentIndex(-1)
        
        # count number of existing links (returns integer)
        self.count_links = count_all_links(connection)
        
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
        
        #Call SQL for update links (also for "add link")
        self.update_links(connection)
        
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
        
        return True
