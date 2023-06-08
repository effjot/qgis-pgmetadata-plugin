# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: Anton Kraus, Florian Jenn
"""

import logging
from dataclasses import dataclass
from collections import OrderedDict
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsProviderConnectionException
from PyQt5.QtWidgets import QMessageBox
from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui
from qgis.PyQt.QtGui import QIntValidator

LOGGER = logging.getLogger('pg_metadata')
EDITDIALOG_CLASS = load_ui('edit_metadata_dialog.ui')

#TODO falls nichts geändert, aber Ok gedrückt: Datum für Änderung der Metadaten unverändert lassen -> d.h. gar nichts in DB schreiben


def postgres_array_to_list(s: str) -> list[str]:
    #TODO: vielleicht https://qgis.org/pyqgis/master/core/QgsPostgresStringUtils.html verwendbar?
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


def query_to_ordereddict(connection, id_col: str, columns: list[str], from_where_clause: str) -> OrderedDict:
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


# TODO: ggf. Klasse für einzelnen Link verwenden
@dataclass
class Link:
    """Metadata link information"""
    id: int
    name: str


class Links:
    def __init__(self):
        self.links = None
        
    def clear(self):
        self.links = None
        
    def count(self):
        if not self.links:
            return 0
        return len(self.links)

    def get(self, id: int):
        if id not in self.links:
            return None
        return self.links[id]
    
    def get_all(self):
        return self.links.values()

    def delete(self, id: int):
        if id not in self.links:
            return
        del self.links[id]
    
    def read_from_db(self, connection, dataset_id: int, sort_key='name'):
        self.clear()
        self.links = query_to_ordereddict(
            connection, 'id',
            ['name', 'type', 'url', 'description', 'format', 'mime', 'size', 'fk_id_dataset'],
            f"FROM pgmetadata.link WHERE fk_id_dataset = {dataset_id} ORDER BY {sort_key}")
        
    def write_to_db(self, connection, dataset_id):
        if not self.links:
            return
        for link in self.get_all():
            if 'status' not in link.keys():
                continue
            size = link['size'] if link['size'] else 'NULL'
            if link['status'] == 'update':
                #FIXME: dollar quoting for fields that likely could contain quote characters
                #  -> parametrized queries possible with pyqgis?
                sql = f"UPDATE pgmetadata.link SET name = $quote${link['name']}$quote$, type = '{link['type']}', "
                sql += f"url = $quote${link['url']}$quote$, description = $quote${link['description']}$quote$, format = '{link['format']}', mime = '{link['mime']}', size = {size} "
                sql += f"WHERE id = {link['id']}"
                LOGGER.debug(f"  write_to_db(): update {link['id']} {link['name']}")
                #LOGGER.debug('sql=')
                #LOGGER.debug(sql)
            if link['status'] == 'new':
                if link['name'] and link['url']:
                    #FIXME: dollar quoting, see above
                    sql = "INSERT INTO pgmetadata.link (name, type, url, description, format, mime, size, fk_id_dataset) "
                    sql += f"VALUES ($quote${link['name']}$quote$, '{link['type']}', $quote${link['url']}$quote$, $quote${link['description']}$quote$, "
                    sql += f"'{link['format']}', '{link['mime']}', {size}, {dataset_id})"
                    LOGGER.debug(f"  write_to_db(): insert {link['id']} {link['name']}")
                else:  # Abbruch bei unvollständiger eingabe
                    QMessageBox.warning(self, 'Information', 'Fehlende Einträge für neuen Link.')
                    return
            if link['status'] == 'remove':
                sql = f"DELETE FROM pgmetadata.link WHERE id = {link['id']}"
                LOGGER.debug(f"  write_to_db(): delete {link['id']} {link['name']}")
            try:
                connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when updating the database: ') + str(e))
    
    def new(self):
        """Create new link with empty data and mark for database insert"""
        if self.links:
            new_id = min(self.links) - 1
        else:
            new_id = -1
        self.links[new_id] = {'id': new_id, 'name': '', 'url': '', 'status': 'new'}
        return new_id
    
    def update(self, link_id: int, link_data: dict):  # TODO PgMetadataLayerEditor.save_link() hier einbauen
        """Update link data and mark for database update"""
        link = self.links.get(link_id)
        for field in link_data:
            link[field] = link_data[field]
        if 'status' not in link:  # Do not overwrite "new" status
            link['status'] = 'update'
        
    def mark_delete(self, link_id):
        """Mark current link for removal from metadata in database"""
        link = self.links.get(link_id)
        LOGGER.debug(f'  mark_delete(): {link_id=}, {link=}')
        if 'status' not in link or link['status'] == 'update':
            link['status'] = 'remove'
        elif link['status'] == 'new':
            self.links.delete(link_id)

class PgMetadataLayerEditor(QDialog, EDITDIALOG_CLASS):

    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        validator = QIntValidator(1, 100000000, self)
        self.lineEdit_minimum_optimal_scale.setValidator(validator)
        self.lineEdit_maximum_optimal_scale.setValidator(validator)
        self.lineEdit_link_size.setValidator(validator)
        self.comboBox_linknames.currentIndexChanged.connect(self.links_tab_update_form)
        self.tabWidget.currentChanged.connect(self.links_tab_update_form)
        self.button_add_link.clicked.connect(self.new_link)
        self.button_remove_link.clicked.connect(self.remove_link)
        
        #self.button_remove_link.clicked.connect(self.remove_link)
        
        self.links = Links()

    def clear_linkinfo(self, reset_index: bool):
        self.textbox_link_name.clear()
        self.textbox_link_url.clear()
        self.textbox_link_description.clear()
        self.textbox_link_format.clear()
        self.lineEdit_link_size.clear()
        if reset_index:
            self.comboBox_link_types.setCurrentIndex(-1)
            self.comboBox_link_mimes.setCurrentIndex(-1)

    def new_link(self):
        #self.comboBox_linknames.setCurrentIndex(-1)
        self.clear_linkinfo(True)
        new_id = self.links.new()
        self.current_link_id = new_id
        self.comboBox_linknames.addItem('(Neuer Link)', new_id)
        self.comboBox_linknames.setCurrentIndex(self.comboBox_linknames.count() - 1)

    def remove_link(self):        
        idx = self.comboBox_linknames.currentIndex()
        LOGGER.debug(f'  remove_link() before: {idx=}, {self.current_link_id=}')
        self.links.mark_delete(self.current_link_id)
        self.current_link_id = None
        self.comboBox_linknames.removeItem(idx)
        LOGGER.debug(f'  remove_link() after: {self.comboBox_linknames.currentIndex()=}, {self.current_link_id=}')
        
    def save_link(self, link_id):
        """Link-Daten aus Dialog holen und in 'self.links[link_id]' merken"""
        if not link_id:
            return
        dlg_name = self.textbox_link_name.toPlainText()
        # Namen in Combobox aktualisieren
        link = self.links.get(link_id)
        if link['name'] != dlg_name:
            # Combobox ist evtl. schon auf neuem Link, darum Index für bearbeiteten Link suchen
            savelink_combobox_idx = self.comboBox_linknames.findData(link['id'])
            LOGGER.debug(f'  ComboBox: {dlg_name=}, {self.comboBox_linknames.currentIndex()=}, {savelink_combobox_idx=}')
            self.comboBox_linknames.setItemText(savelink_combobox_idx,
                                                '*' + dlg_name)       
        self.links.update(link_id, link_data={
            'name': dlg_name,
            'type': self.comboBox_link_types.currentData(),
            'url': self.textbox_link_url.toPlainText(),
            'description': self.textbox_link_description.toPlainText(),
            'format': self.textbox_link_format.toPlainText(),
            'mime': self.comboBox_link_mimes.currentData(),
            'size': self.lineEdit_link_size.text()
            })

    def links_tab_update_form(self):
        LOGGER.debug(f'links_tab_update_form()')
        if self.tabWidget.tabText(self.tabWidget.currentIndex()) != 'Links':
            LOGGER.debug('  nicht im Tab -> fertig')
            return
        if self.current_link_id == self.comboBox_linknames.currentData():
            LOGGER.debug('  kein neuer Link gewählt -> fertig')
            return
        if self.current_link_id:
            LOGGER.debug(f'  neuer Link gewählt: {self.current_link_id=} speichern')
            self.save_link(self.current_link_id)

        self.clear_linkinfo(True)

        # get ID of currently selected link
        self.current_link_id = self.comboBox_linknames.currentData()
        idx = self.comboBox_linknames.currentIndex()
        LOGGER.debug(f'  neu {idx=}; {self.current_link_id=}')
        
        current_link = self.links.get(self.current_link_id)
        # FIXME: sind die ifs nötig?
        if current_link['name']:        self.textbox_link_name.setText(current_link['name'])
        index = self.comboBox_link_types.findData(current_link['type'])
        if current_link['type']:        self.comboBox_link_types.setCurrentIndex(index)
        if current_link['url']:         self.textbox_link_url.setText(current_link['url'])
        if current_link['description']: self.textbox_link_description.setText(current_link['description'])
        if current_link['format']:      self.textbox_link_format.setText(current_link['format'])
        index = self.comboBox_link_mimes.findData(current_link['mime'])
        if current_link['mime']:        self.comboBox_link_mimes.setCurrentIndex(index)
        if current_link['size']:        self.lineEdit_link_size.setText(str(current_link['size']))

    def prepare_editor(self, datasource_uri, connection):
        self.table = datasource_uri.table()
        self.schema = datasource_uri.schema()
        LOGGER.info(f'Edit metadata for layer {datasource_uri.table()}, {connection}')
        sql = (f"SELECT title, abstract, project_number, categories, keywords, themes, minimum_optimal_scale, maximum_optimal_scale, data_last_update, id, spatial_level FROM pgmetadata.dataset "
               f"WHERE schema_name = '{self.schema}' and table_name = '{self.table}'")
        try:
            data = connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when querying the database: ') + str(e))
            return False
        
        # get foreign key for links-table #FIXME Nicht nur für Links! Mit dataset_id am Schluss auch zielgerichtet Medatatensatz akutalisieren
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
        self.categories = get_glossary(connection, 'dataset.categories')
        self.comboBox_categories.addItems(self.categories.values())  # fill comboBox with categories
        selected_categories_keys = postgres_array_to_list(data[0][3])
        selected_categories_values = []
        for i in selected_categories_keys:
            selected_categories_values.append(self.categories[i])
        self.comboBox_categories.setCheckedItems(selected_categories_values)  # set selected categories as checked
        
        # get themes and fill comboBox
        self.comboBox_themes.clear()
        self.themes = query_to_ordereddict(connection, 'id', ['code', 'label'], "FROM pgmetadata.theme ORDER BY label")
        selected_themes_keys = postgres_array_to_list(data[0][5])
        selected_themes_values = []
        for theme in self.themes.values():
            self.comboBox_themes.addItem(theme['label'], theme['code'])
            for i in selected_themes_keys:
                if i == theme['code']:
                    selected_themes_values.append(theme['label'])
        self.comboBox_themes.setCheckedItems(selected_themes_values)  # set selected themes as checked
        
        self.clear_linkinfo(False)
        
        # get link types and fill comboBox
        self.comboBox_link_types.clear()
        link_types = query_to_ordereddict(connection, 'id', ['code', 'label', 'description'], "FROM pgmetadata.v_glossary_translation_de WHERE field='link.type' ORDER BY item_order, code")
        for link_type in link_types.values():
            self.comboBox_link_types.addItem(link_type['label'], link_type['code'])
        self.comboBox_link_types.setCurrentIndex(-1)
        
        # get MIME types and fill comboBox
        self.comboBox_link_mimes.clear()
        link_mimes = query_to_ordereddict(connection, 'id', ['code', 'label', 'description'], "FROM pgmetadata.v_glossary_translation_de WHERE field='link.mime' ORDER BY item_order, code")
        for link_mime in link_mimes.values():
            self.comboBox_link_mimes.addItem(f"{link_mime['code']}: {link_mime['label']}", link_mime['code'])
        self.comboBox_link_mimes.setCurrentIndex(-1)
        
        # get links and fill comboBox
        self.comboBox_linknames.clear()
        self.links.read_from_db(connection, self.dataset_id)
        self.current_link_id = None  # heißt: gibt noch keinen Link, der angezeigt werden kann
        if self.links.count():
            for link in self.links.get_all():
                #LOGGER.debug(f'  add item {link=}')
                self.comboBox_linknames.addItem(link['name'], link['id'])
            self.comboBox_linknames.setCurrentIndex(0)
            LOGGER.debug(f'open_editor(): {self.current_link_id=}')
            self.links_tab_update_form()

    def open_editor(self, datasource_uri, connection):
        self.prepare_editor(datasource_uri, connection)
        self.show()
        result = self.exec_()
        if result:
            self.write_edits_to_db(connection)
        self.current_link_id = None  # zurücksetzen für nächstes Mal
        return result

    def write_edits_to_db(self, connection):
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
        
        # Store edited links in database
        self.save_link(self.current_link_id)
        self.links.write_to_db(connection, self.dataset_id)
        
        new_categories_keys = dict_reverse_lookup(self.categories, self.comboBox_categories.checkedItems())
        new_categories_array = list_to_postgres_array(new_categories_keys)
        
        new_themes_values = self.comboBox_themes.checkedItems()
        new_themes_keys = []
        for theme in self.themes.values():
            for i in new_themes_values:
                if i == theme['label']:
                    new_themes_keys.append(theme['code'])
        new_themes_array = list_to_postgres_array(new_themes_keys)
        
        sql = (f"UPDATE pgmetadata.dataset SET title = '{title}', abstract = '{abstract}', project_number = '{project_number}', "
               f" keywords = '{keywords}', categories = {new_categories_array}, themes = {new_themes_array}, "
               f" minimum_optimal_scale = {minimum_optimal_scale}, maximum_optimal_scale = {maximum_optimal_scale}, spatial_level = '{spatial_level}' "
               f"WHERE schema_name = '{self.schema}' and table_name = '{self.table}'")
        
        try:
            connection.executeSql(sql)
        except QgsProviderConnectionException as e:
            LOGGER.critical(tr('Error when updating the database: ') + str(e))
            return False
        
        return True
