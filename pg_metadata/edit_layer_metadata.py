# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: Anton Kraus, Florian Jenn
"""

import logging
from dataclasses import dataclass
from collections import OrderedDict, defaultdict
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import (
    QgsApplication,
    QgsProviderConnectionException
)
from PyQt5.QtWidgets import QMessageBox
from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui
from qgis.PyQt.QtGui import QIntValidator


LINK_TYPE_PRESETS = OrderedDict([
    ('Webseite', {'type': 'WWW:LINK', 'mime': 'html'}),
    ('Download', {'type': 'download', 'mime': 'html'}),
    ('Information', {'type': 'information', 'mime': 'html'}),
    ('WMS-Dienst', {'type': 'OGC:WMS', 'mime': 'txml'}),
    ('WMTS-Dienst', {'type': 'OGC:WMTS', 'mime': 'txml'}),
    ('WFS-Dienst', {'type': 'OGC:WFS', 'mime': 'txml'}),
    ('Datei', {'type': 'file', 'mime': 'octet-stream'}),
    ('CSV-Datei', {'type': 'file', 'mime': 'csv'}),
    ('Excel-Datei (.xlsx)', {'type': 'file', 'mime': 'xlsx'}),
    ('Word-Datei (.docx)', {'type': 'file', 'mime': 'docx'}),
    ('PDF-Datei,', {'type': 'file', 'mime': 'pdf'}),
    ('Shapefile', {'type': 'ESRI:SHP', 'mime': 'octet-stream'}),
    ('Geopackage', {'type': 'OGC:GPKG', 'mime': 'octet-stream'}),    
    ('Ordner', {'type': 'directory', 'mime': 'directory'})
    ])


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
    terms = [defaultdict(lambda: None, zip(columns, row)) for row in rows]
    terms_by_id = OrderedDict()
    for t in terms:
        terms_by_id[t[id_col]] = t
    return terms_by_id


class Links:
    def __init__(self):
        self.links: OrderedDict = None
        self.next_new_id: int = -1
        
    def clear(self):
        self.links = None
        
    def count(self):
        if not self.links:
            return 0
        return len(self.links)

    def get(self, link_id: int):
        if link_id not in self.links:
            return None
        return self.links[link_id]
    
    def get_all(self):
        return self.links.values()

    def delete(self, link_id: int):
        if link_id not in self.links:
            return
        del self.links[link_id]
    
    def read_from_db(self, connection, dataset_id: int, sort_key='name'):
        self.clear()
        self.links = query_to_ordereddict(
            connection, 'id',
            ['name', 'type', 'url', 'description', 'format', 'mime', 'size', 'fk_id_dataset'],
            f"FROM pgmetadata.link WHERE fk_id_dataset = {dataset_id} ORDER BY {sort_key}")
    
    def min_info_missing(self):
        """FIXE: wahrscheinlich nicht mehr nötig"""
        missing_info = []
        for link in self.get_all():
            if 'status' not in link or link['status'] == 'remove':
                continue
            if not (link['name'] and link['url']):
                missing_info.append(link)
        if missing_info:
            QMessageBox.warning(None, 'Unvollständige Links',
                                'Bei folgenden Link(s) fehlen Name oder URL:\n'
                                + '\n'.join([f"#{l['id']} {l['name']}: {l['url']}" for l in missing_info]))
        return missing_info

    def write_to_db(self, connection, dataset_id):
        if not self.links:
            return True
        # if self.min_info_missing():
        #     return False
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
                    QMessageBox.warning(None, 'Information', 'Fehlende Einträge für neuen Link.')
                    return
            if link['status'] == 'remove':
                sql = f"DELETE FROM pgmetadata.link WHERE id = {link['id']}"
                LOGGER.debug(f"  write_to_db(): delete {link['id']} {link['name']}")
            try:
                connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when updating the database: ') + str(e))
        return True

    def new(self):
        """Create new link with empty data and mark for database insert"""
        new_id = self.next_new_id
        self.links[new_id] = defaultdict(lambda: None,
                                         {'id': new_id, 'name': '', 'url': '',
                                          'type': None, 'mime': None, 'status': 'new'})
        self.next_new_id -= 1
        LOGGER.debug(f'  Links.new() -> {new_id=}; {self.next_new_id}')
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
            self.delete(link_id)


class PgMetadataLayerEditor(QDialog, EDITDIALOG_CLASS):
    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        validator = QIntValidator(1, 100_000_000, self)
        self.lne_minimum_optimal_scale.setValidator(validator)
        self.lne_maximum_optimal_scale.setValidator(validator)
        self.lne_link_size.setValidator(validator)
        self.tabWidget.currentChanged.connect(self.tab_current_changed)
        self.cmb_link_select.currentIndexChanged.connect(self.tab_links_update_form)
        self.btn_link_add.setIcon(QgsApplication.getThemeIcon('/symbologyAdd.svg'))
        self.btn_link_add.clicked.connect(self.new_link)
        self.btn_link_remove.setIcon(QgsApplication.getThemeIcon('/symbologyRemove.svg'))
        self.btn_link_remove.clicked.connect(self.remove_link)
        self.buttonBox.accepted.disconnect()
        self.buttonBox.accepted.connect(self.dlg_accept)  

        self.tab_current_idx: int = self.tabWidget.currentIndex()
        self.tab_links_idx: int = self.tabWidget.indexOf(self.tab_links)
        
        self.links = Links()
        self.current_link_id: int

    def clear_linkinfo(self, reset_index: bool):
        #FIXME: reset_index nötig? Umbenennen in tab_links_clear_form()
        self.txt_link_name.clear()
        self.txt_link_url.clear()
        self.txt_link_description.clear()
        self.txt_link_format.clear()
        self.lne_link_size.clear()
        if reset_index:
            self.cmb_link_type.setCurrentIndex(-1)
            self.cmb_link_mime.setCurrentIndex(-1)

    def new_link(self):
        if self.links.count() > 0:
            saved = self.save_link(self.current_link_id)
            if not saved:
                return False
        new_id = self.links.new()
        self.cmb_link_select.addItem('(Neuer Link)', new_id)
        self.cmb_link_select.setCurrentIndex(self.cmb_link_select.findData(new_id))
        self.current_link_id = new_id

    def remove_link(self):        
        idx = self.cmb_link_select.currentIndex()
        LOGGER.debug(f'remove_link() before: {idx=}, {self.current_link_id=}')
        self.links.mark_delete(self.current_link_id)
        self.current_link_id = None
        self.cmb_link_select.removeItem(idx)
        LOGGER.debug(f'  remove_link() after: {self.cmb_link_select.currentIndex()=}, {self.current_link_id=}')
        
    def save_link(self, link_id):
        """Link-Daten aus Dialog holen und merken.
        
        Wird vor Aktualisierung der Formularfelder aufgerufen, d.h. die Felder
        enthalten noch die zu speichernden Daten. self.current_link ist auch
        noch der zu speichernde Link.  Die Combobox kann aber schon auf dem neuen
        Link sein.
        """
        
        if not link_id:
            return True
        link = self.links.get(link_id)
        savelink_combobox_idx = self.cmb_link_select.findData(link_id)
        dlg_name = self.txt_link_name.toPlainText()       
        dlg_url = self.txt_link_url.toPlainText()
        
        if not (dlg_name and dlg_url):  # minimally required information missing
            self.cmb_link_select.setCurrentIndex(savelink_combobox_idx)
            self.tabWidget.setCurrentIndex(self.tab_links_idx)
            QMessageBox.warning(self, 'Unvollständige Links',
                                'In diesem Link fehlen Name oder URL. Bitte ergänzen.')
            return False
            
        # Namen in Combobox aktualisieren (Sternchen für Änderungen)
        if link['name'] != dlg_name:            
            LOGGER.debug(f'  ComboBox: {dlg_name=}, {self.cmb_link_select.currentIndex()=}, {savelink_combobox_idx=}')
            self.cmb_link_select.setItemText(savelink_combobox_idx,
                                                '*' + dlg_name)       
        self.links.update(link_id, link_data={
            'name': dlg_name,
            'type': self.cmb_link_type.currentData(),
            'url': dlg_url,
            'description': self.txt_link_description.toPlainText(),
            'format': self.txt_link_format.toPlainText(),
            'mime': self.cmb_link_mime.currentData(),
            'size': self.lne_link_size.text()
            })
        return True

    def tab_current_changed(self):
        LOGGER.debug('tab_current_changed()')
        prev_tab_idx = self.tab_current_idx
        self.tab_current_idx = self.tabWidget.currentIndex()
        if prev_tab_idx == self.tab_links_idx:  # Changed from the Links tab to another → save currently edited link
            self.save_link(self.current_link_id)
        elif self.tab_current_idx == self.tab_links_idx:
            self.tab_links_update_form()
        else:
            LOGGER.debug('  nicht im Tab -> fertig')
        
    def tab_links_update_form(self):
        LOGGER.debug('tab_links_update_form()')
        if self.current_link_id == self.cmb_link_select.currentData():
            LOGGER.debug('  kein neuer Link gewählt -> fertig')
            return
        if self.current_link_id:
            LOGGER.debug(f'  neuer Link gewählt: {self.current_link_id=} speichern')
            saved = self.save_link(self.current_link_id)
            if not saved:
                return
        self.clear_linkinfo(True)
        # get ID of currently selected link
        self.current_link_id = self.cmb_link_select.currentData()
        LOGGER.debug(f'  neu {self.cmb_link_select.currentIndex()=}; {self.current_link_id=}')
        current_link = self.links.get(self.current_link_id)
        if current_link['name']: self.txt_link_name.setText(current_link['name'])
        if current_link['type']:
            index = self.cmb_link_type.findData(current_link['type'])
            self.cmb_link_type.setCurrentIndex(index)
        if current_link['url']: self.txt_link_url.setText(current_link['url'])
        if current_link['description']: self.txt_link_description.setText(current_link['description'])
        if current_link['format']: self.txt_link_format.setText(current_link['format'])
        if current_link['mime']: 
            index = self.cmb_link_mime.findData(current_link['mime'])
            self.cmb_link_mime.setCurrentIndex(index)
        if current_link['size']: self.lne_link_size.setText(str(current_link['size']))

    def dlg_accept(self):
        """OK-Button bestätigt+schließt nur, wenn aktueller Link gespeichert werden konnte."""
        #QMessageBox.warning(self, 'gedrückt', 'OK gedrückd')
        saved = self.save_link(self.current_link_id)
        if saved:
            #QMessageBox.warning(self, 'gedrückt2', 'nach OK gedrückt')
            self.accept()

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
        
        if data[0][0]: self.txt_title.setPlainText(data[0][0])
        if data[0][1]: self.txt_abstract.setPlainText(data[0][1])
        if data[0][2]: self.txt_project_number.setPlainText(data[0][2])
        if data[0][4]: self.txt_keywords.setPlainText(str(data[0][4]))
        if data[0][6]: self.lne_minimum_optimal_scale.setText(str(data[0][6]))
        if data[0][7]: self.lne_maximum_optimal_scale.setText(str(data[0][7]))
        if data[0][10]: self.txt_spatial_level.setPlainText(data[0][10])
        
        # get categories and fill comboBox
        self.cmb_categories.clear()
        self.categories = get_glossary(connection, 'dataset.categories')
        self.cmb_categories.addItems(self.categories.values())  # fill comboBox with categories
        selected_categories_keys = postgres_array_to_list(data[0][3])
        selected_categories_values = []
        for i in selected_categories_keys:
            selected_categories_values.append(self.categories[i])
        self.cmb_categories.setCheckedItems(selected_categories_values)  # set selected categories as checked
        
        # get themes and fill comboBox
        self.cmb_themes.clear()
        self.themes = query_to_ordereddict(connection, 'id', ['code', 'label'], "FROM pgmetadata.theme ORDER BY label")
        selected_themes_keys = postgres_array_to_list(data[0][5])
        selected_themes_values = []
        for theme in self.themes.values():
            self.cmb_themes.addItem(theme['label'], theme['code'])
            for i in selected_themes_keys:
                if i == theme['code']:
                    selected_themes_values.append(theme['label'])
        self.cmb_themes.setCheckedItems(selected_themes_values)  # set selected themes as checked
        
        # get link types and fill comboBox
        self.cmb_link_type.clear()
        link_types = query_to_ordereddict(connection, 'id', ['code', 'label', 'description'], "FROM pgmetadata.v_glossary_translation_de WHERE field='link.type' ORDER BY item_order, code")
        for link_type in link_types.values():
            self.cmb_link_type.addItem(link_type['label'], link_type['code'])
        self.cmb_link_type.setCurrentIndex(-1)
        
        # get MIME types and fill comboBox
        self.cmb_link_mime.clear()
        link_mimes = query_to_ordereddict(connection, 'id', ['code', 'label', 'description'], "FROM pgmetadata.v_glossary_translation_de WHERE field='link.mime' ORDER BY item_order, code")
        for link_mime in link_mimes.values():
            self.cmb_link_mime.addItem(f"{link_mime['code']}: {link_mime['label']}", link_mime['code'])
        self.cmb_link_mime.setCurrentIndex(-1)
        
        # set up linke type presets 
        self.cmb_link_type_preset.clear()
        for preset in LINK_TYPE_PRESETS:
            self.cmb_link_type_preset.addItem(preset)
        self.cmb_link_type_preset.setCurrentIndex(-1)
        
        # get links and fill comboBox
        self.cmb_link_select.clear()
        self.clear_linkinfo(False)
        self.links.read_from_db(connection, self.dataset_id)
        self.current_link_id = None  # heißt: gibt noch keinen Link, der angezeigt werden kann
        if self.links.count():
            for link in self.links.get_all():
                #LOGGER.debug(f'  add item {link=}')
                self.cmb_link_select.addItem(link['name'], link['id'])
            self.cmb_link_select.setCurrentIndex(0)
            LOGGER.debug(f'open_editor(): {self.current_link_id=}')
        self.tab_links_update_form()
        
    def open_editor(self, datasource_uri, connection):
        self.prepare_editor(datasource_uri, connection)
        self.show()
        result = self.exec_()
        if result:
            self.write_edits_to_db(connection)
        self.current_link_id = None  # zurücksetzen für nächstes Mal
        return result

    def write_edits_to_db(self, connection):
        title = self.txt_title.toPlainText()
        abstract = self.txt_abstract.toPlainText()
        project_number = self.txt_project_number.toPlainText()
        keywords = self.txt_keywords.toPlainText()
        spatial_level = self.txt_spatial_level.toPlainText()
        minimum_optimal_scale = self.lne_minimum_optimal_scale.text()
        maximum_optimal_scale = self.lne_maximum_optimal_scale.text()
        if not minimum_optimal_scale:
            minimum_optimal_scale = 'NULL'
        if not maximum_optimal_scale:
            maximum_optimal_scale = 'NULL'
        
        # Store edited links in database
        self.save_link(self.current_link_id)
        self.links.write_to_db(connection, self.dataset_id)
        
        new_categories_keys = dict_reverse_lookup(self.categories, self.cmb_categories.checkedItems())
        new_categories_array = list_to_postgres_array(new_categories_keys)
        
        new_themes_values = self.cmb_themes.checkedItems()
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
