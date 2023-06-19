# -*- coding: utf-8 -*-
"""
Created on Thu Sep  8 14:16:32 2022

@author: Anton Kraus, Florian Jenn
"""

import logging
from collections import OrderedDict, defaultdict
#from typing import Optional
from qgis.PyQt.QtWidgets import (
    QDialog,
    QInputDialog
)
from qgis.core import (
    NULL,
    QgsApplication,
    QgsProviderConnectionException
)
from PyQt5.QtCore import (
    Qt,
    QDateTime,
    QVariant
)
from PyQt5.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QMessageBox,
    QTableWidgetItem,
    QHeaderView
)
from pg_metadata.qgis_plugin_tools.tools.i18n import tr
from pg_metadata.qgis_plugin_tools.tools.resources import load_ui
from qgis.PyQt.QtGui import QIntValidator


LINK_TYPE_PRESETS = OrderedDict([
    ('Webseite', {'type': 'WWW:LINK', 'mime': 'html'}),
    ('Download', {'type': 'download', 'mime': 'octet-stream'}),
    ('Information', {'type': 'information', 'mime': 'html'}),
    ('WMS-Dienst', {'type': 'OGC:WMS', 'mime': 'txml'}),
    ('WMTS-Dienst', {'type': 'OGC:WMTS', 'mime': 'txml'}),
    ('WFS-Dienst', {'type': 'OGC:WFS', 'mime': 'txml'}),
    ('Datei', {'type': 'file', 'mime': 'octet-stream'}),
    ('Text-Datei (.txt)', {'type': 'file', 'mime': 'plain'}),
    ('CSV-Datei', {'type': 'file', 'mime': 'csv'}),
    ('Excel-Datei (.xlsx)', {'type': 'file', 'mime': 'xlsx'}),
    ('Word-Datei (.docx)', {'type': 'file', 'mime': 'docx'}),
    ('PDF-Datei', {'type': 'file', 'mime': 'pdf'}),
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


def sql_quote_or_null(val, as_number=False):
    if not val or (type(val) == QVariant and val.isNull()):
        return 'NULL'
    if as_number or type(val) == int or type(val) == float:
        return val
    return f'$q${val}$q$'


def dict_reverse_lookup(dictionary: dict, values: list) -> list:
    return [key for key, val in dictionary.items() if val in values]


def get_glossary(connection, field: str) -> OrderedDict:
    sql = f"SELECT code, label FROM pgmetadata.v_glossary_translation_de WHERE field = '{field}' ORDER BY item_order"
    try:
        rows = connection.executeSql(sql)
    except QgsProviderConnectionException as e:
        LOGGER.critical(tr('Error when querying the database: ') + str(e))
        return False
    terms = OrderedDict()
    for row in rows:
        terms[row[0]] = row[1]
    return terms


def replace_qvariantnull(iterable):
    return map(lambda x: None if type(x) == QVariant and x.isNull() else x,
               iterable)

def query_to_ordereddict(connection, id_col: str, columns: list[str], from_where_clause: str) -> OrderedDict:
    columns.insert(0, id_col)
    sql = f"SELECT {', '.join(columns)} {from_where_clause}"
    #LOGGER.info(f'query(): {sql=}')
    try:
        rows = connection.executeSql(sql)
    except QgsProviderConnectionException as e:
        LOGGER.critical(tr('Error when querying the database: ') + str(e))
        return False
    terms = [defaultdict(lambda: None, zip(columns, replace_qvariantnull(row)))
             for row in rows]
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
        if not dataset_id:
            self.links = OrderedDict()
            return
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
                return False
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


class AvailableContacts:
    def __init__(self):
        self.contacts = OrderedDict()
        self.organisation_members = defaultdict(OrderedDict, {})

    def clear(self):
        self.contacts.clear()
        self.organisation_members.clear()

    def read_from_db(self, connection, sort_key='organisation_name, organisation_unit, name'):
        self.clear()
        self.contacts = query_to_ordereddict(
            connection, 'id',
            ['name', 'organisation_name', 'organisation_unit', 'email', 'phone'],
            f"FROM pgmetadata.contact ORDER BY {sort_key}")
        for contact_id, contact in self.contacts.items():
            org = contact['organisation_name']
            if org:
                self.organisation_members[org][contact_id] = contact

    def get(self, contact_id: int):
        if contact_id not in self.contacts:
            return None
        return self.contacts[contact_id]
    
    def flatten(self, contacts, include_org=True):
        return {contact_id:
                "{name}{openbr}{orgname}{sep}{orgunit}{closebr}".format(
                    name=contact['name'],
                    openbr=' (' if include_org and contact['organisation_name'] else '',
                    orgname=contact['organisation_name'] if include_org and contact['organisation_name'] else '',
                    sep=', ' if include_org and contact['organisation_unit'] else '',
                    orgunit=contact['organisation_unit'] if include_org and contact['organisation_unit'] else '',
                    closebr=')' if include_org and contact['organisation_name'] else '')
                for contact_id, contact in contacts.items()}
    
    def get_all_flat(self):
        return self.flatten(self.contacts)
    
    def get_organisation_flat(self, org_name: str):
        if org_name in self.organisation_members:
            return self.flatten(self.organisation_members[org_name], include_org=False)
        else:
            return None


class AssignedContacts:
    def __init__(self):
        self.assignments = OrderedDict()
        self.next_new_id: int = -1

    def clear(self):
        self.assignments.clear()

    def count(self):
        if not self.assignments:
            return 0
        return len(self.assignments)

    def read_from_db(self, connection, dataset_id: int, sort_key='contact_role, id'):
        self.clear()
        if not dataset_id:
            self.assignments = OrderedDict()
            return
        self.assignments = query_to_ordereddict(
            connection, 'id', ['contact_role', 'fk_id_contact', 'fk_id_dataset'],
            f"FROM pgmetadata.dataset_contact WHERE fk_id_dataset = {dataset_id} ORDER by {sort_key}")

    def get(self, assignment_id: int):
        if assignment_id not in self.assignments:
            return None
        return self.assignments[assignment_id]

    def get_all(self):
        return self.assignments.values()

    def new(self):
        """Create new contact assignment with empty data and mark for database insert"""
        new_id = self.next_new_id
        self.assignments[new_id] = defaultdict(lambda: None,
                                               {'id': new_id, 'contact_role': None, 
                                                'fk_id_contact': None, 'status': 'new'})
        self.next_new_id -= 1
        LOGGER.debug(f'  AssignedContacts.new() -> {new_id=}; {self.next_new_id}')
        return new_id

    def delete(self, assignment_id: int):
        if assignment_id not in self.assignments:
            return
        del self.assignments[assignment_id]
        
    def mark_delete(self, assignment_id):
        """Mark current link for removal from metadata in database"""
        ass = self.assignments.get(assignment_id)
        LOGGER.debug(f'  mark_delete(): {assignment_id=}, {ass=}')
        if 'status' not in ass or ass['status'] == 'update':
            ass['status'] = 'remove'
        elif ass['status'] == 'new':
            self.delete(assignment_id)

    def write_to_db(self, connection, dataset_id):
        if not self.assignments:
            return True
        for ass in self.get_all():
            LOGGER.debug(f"AssignedContacts.write_to_db(): {ass=}")
            if 'status' not in ass.keys():
                continue
            if ass['status'] == 'update':
                sql = f"UPDATE pgmetadata.dataset_contact SET fk_id_contact = {ass['fk_id_contact']}, "
                sql += f"contact_role = $quote${ass['contact_role']}$quote$ WHERE id = {ass['id']}"
                LOGGER.debug(f"  AssignedContacts.write_to_db(): update {ass['id']} {ass['contact_role']}")
                LOGGER.debug('sql=')
                LOGGER.debug(sql)
            if ass['status'] == 'new':
                sql = "INSERT INTO pgmetadata.dataset_contact (fk_id_dataset, fk_id_contact, contact_role) "
                sql += f"VALUES ({dataset_id}, {ass['fk_id_contact']}, $quote${ass['contact_role']}$quote$)"
                LOGGER.debug(f"  AssignedContacts.write_to_db(): insert {ass['id']} {ass['contact_role']}")
                LOGGER.debug('sql=')
                LOGGER.debug(sql)
            if ass['status'] == 'remove':
                sql = f"DELETE FROM pgmetadata.dataset_contact WHERE id = {ass['id']}"
                LOGGER.debug(f"  AssignedContacts.write_to_db(): delete {ass['id']} {ass['contact_role']}")
            try:
                connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when updating the database: ') + str(e))
                return False
        return True

def makefun_widget_sync(this, other):
    if type(this) in [QDateEdit, QDateTimeEdit] and type(other) in [QDateEdit, QDateTimeEdit]:
        def sync():
            LOGGER.info(f'sync date {this.objectName()} -> {other.objectName()}')
            this_dt = this.dateTime()
            other_dt = other.dateTime()
            if this_dt != other_dt:
                other.setDateTime(this_dt)
        return sync
    if type(this) == QComboBox and type(other) == QComboBox:
        def sync():
            this_idx = this.currentIndex()
            other_idx = other.currentIndex()
            if this_idx != other_idx:
                other.setCurrentIndex(this_idx)
        return sync
    raise NotImplementedError(f"Type {type(this)} not implemented")
    
class PgMetadataLayerEditor(QDialog, EDITDIALOG_CLASS):
    def __init__(self, parent=None):
        super().__init__()
        self.setupUi(self)
        
        validator = QIntValidator(1, 100_000_000, self)
        self.lne_minimum_optimal_scale.setValidator(validator)
        self.lne_maximum_optimal_scale.setValidator(validator)
        self.lne_link_size.setValidator(validator)
        self.tabWidget.currentChanged.connect(self.tab_current_changed)
        self.btn_dat_publ_now.setIcon(QgsApplication.getThemeIcon('/propertyicons/temporal.svg'))
        self.btn_dat_publ_now.clicked.connect(self.set_datetime_publ)
        self.btn_datetime_publ_now.setIcon(QgsApplication.getThemeIcon('/propertyicons/temporal.svg'))
        self.btn_datetime_publ_now.clicked.connect(self.set_datetime_publ)
        self.dat_publ.dateChanged.connect(makefun_widget_sync(self.dat_publ, self.dattim_publ))
        self.dattim_publ.dateChanged.connect(makefun_widget_sync(self.dattim_publ, self.dat_publ))
        self.cmb_confidentiality.currentIndexChanged.connect(makefun_widget_sync(self.cmb_confidentiality, self.cmb_confidentiality2))
        self.cmb_confidentiality2.currentIndexChanged.connect(makefun_widget_sync(self.cmb_confidentiality2, self.cmb_confidentiality))
        self.btn_datetime_upd_now.setIcon(QgsApplication.getThemeIcon('/propertyicons/temporal.svg'))
        self.btn_datetime_upd_now.clicked.connect(self.set_datetime_upd)
        self.cmb_link_select.currentIndexChanged.connect(self.tab_links_update_form)
        self.btn_link_add.setIcon(QgsApplication.getThemeIcon('/symbologyAdd.svg'))
        self.btn_link_add.clicked.connect(self.new_link)
        self.btn_link_remove.setIcon(QgsApplication.getThemeIcon('/symbologyRemove.svg'))
        self.btn_link_remove.clicked.connect(self.remove_link)
        self.cmb_link_type_preset.activated.connect(self.link_type_preset_selected)
        self.cmb_link_type.activated.connect(self.link_type_preset_reset)
        self.cmb_link_mime.activated.connect(self.link_type_preset_reset)
        self.btn_contact_add.setIcon(QgsApplication.getThemeIcon('/symbologyAdd.svg'))
        self.btn_contact_add.clicked.connect(self.add_contact)
        self.btn_contact_remove.setIcon(QgsApplication.getThemeIcon('/symbologyRemove.svg'))
        self.btn_contact_remove.clicked.connect(self.remove_contact)
        self.btn_creator_add.setIcon(QgsApplication.getThemeIcon('/symbologyAdd.svg'))
        self.btn_creator_add.clicked.connect(self.add_creator)
        # When OK is clicked, check+save current link before closing
        self.buttonBox.accepted.disconnect()
        self.buttonBox.accepted.connect(self.dlg_accept)  

        self.tab_current_idx: int = self.tabWidget.currentIndex()
        self.tab_important_idx: int = self.tabWidget.indexOf(self.tab_important_metadata)
        self.tab_links_idx: int = self.tabWidget.indexOf(self.tab_links)
        self.tab_contacts_idx: int = self.tabWidget.indexOf(self.tab_contacts)

        self.new_metadata_record: bool = None
        self.dataset_id: int = None        
        self.links = Links()
        self.current_link_id: int
        self.available_contacts = AvailableContacts()
        self.assigned_contacts = AssignedContacts()

    def set_datetime_publ(self, datetime: QDateTime = None):
        if not datetime:
            datetime = QDateTime.currentDateTime()
        self.dattim_publ.setDateTime(datetime)
        self.dattim_publ.setEnabled(True)
        self.dat_publ.setDateTime(datetime)
        self.dat_publ.setEnabled(True)

    def set_datetime_upd(self, datetime: QDateTime = None):
        if not datetime:
            datetime = QDateTime.currentDateTime()
        self.dattim_upd.setDateTime(datetime)
        self.dattim_upd.setEnabled(True)

    def tab_links_clear_form(self):
        #FIXME: reset_index nötig? Umbenennen in tab_links_clear_form()
        self.txt_link_name.clear()
        self.txt_link_url.clear()
        self.txt_link_description.clear()
        self.txt_link_format.clear()
        self.lne_link_size.clear()
        self.cmb_link_type_preset.setCurrentIndex(-1)
        self.cmb_link_type.setCurrentIndex(-1)
        self.cmb_link_mime.setCurrentIndex(-1)
            
    def link_type_preset_selected(self):
        if self.cmb_link_type_preset.currentIndex() < 0:
            QMessageBox.warning(self, 'Preset', 'nichts zu tun')
            return
        preset = self.cmb_link_type_preset.currentText()
        type_code = LINK_TYPE_PRESETS[preset]['type']
        mime_code = LINK_TYPE_PRESETS[preset]['mime']
        #QMessageBox.warning(self, 'Preset', f"{preset=} | {type_code=} | {mime_code=}")
        self.cmb_link_type.setCurrentIndex(self.cmb_link_type.findData(type_code))
        self.cmb_link_mime.setCurrentIndex(self.cmb_link_mime.findData(mime_code))
        
    def link_type_preset_reset(self):
        self.cmb_link_type_preset.setCurrentIndex(-1)

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
    
    def assignment_set_row(self, row: int, assignment):
        contact = self.available_contacts.get(assignment['fk_id_contact'])
        role = QTableWidgetItem(self.roles[assignment['contact_role']])
        name = QTableWidgetItem(contact.get('name', ''))
        org_name = QTableWidgetItem(contact.get('organisation_name', ''))
        org_unit = QTableWidgetItem(contact.get('organisation_unit', ''))
        email = QTableWidgetItem(contact.get('email', ''))
        phone = QTableWidgetItem(contact.get('phone', ''))
        ass_id = QTableWidgetItem(str(assignment['id']))
        self.table_contacts.setItem(row, 0, role)
        self.table_contacts.setItem(row, 1, name)
        self.table_contacts.setItem(row, 2, org_name)
        self.table_contacts.setItem(row, 3, org_unit)
        self.table_contacts.setItem(row, 4, email)
        self.table_contacts.setItem(row, 5, phone)
        self.table_contacts.setItem(row, 6, ass_id)

    def add_contact(self, filter_by_org: str=None, role_code: str=None):
        if filter_by_org:
            contacts = self.available_contacts.get_organisation_flat(filter_by_org)
        else:
            contacts = self.available_contacts.get_all_flat()
        if not role_code:
            dlg = QInputDialog()
            dlg.setComboBoxItems(self.roles.values())  #FIXME: can’t add Data to combobox with QInputDialog -> make custom dialog
            dlg.setWindowTitle(tr("Neuen Kontakt hinzufügen"))
            dlg.setLabelText(tr("Rolle/Aufgabe auswählen"))
            if not dlg.exec_():
                return 
            role_text = dlg.textValue()
            role_code = dict_reverse_lookup(self.roles, [role_text])[0]
        dlg = QInputDialog()
        dlg.setComboBoxItems(contacts.values())  #FIXME: can’t add Data to combobox with QInputDialog -> make custom dialog
        dlg.setWindowTitle(tr("Neuen Kontakt hinzufügen"))
        dlg.setLabelText(tr(f"Kontakt für Rolle „{role_text}“ auswählen"))
        if not dlg.exec_():
            return 
        selected = dlg.textValue()
        contact_id = dict_reverse_lookup(contacts, [selected])[0]
        new_id = self.assigned_contacts.new()
        new_ass = self.assigned_contacts.get(new_id)
        new_ass['contact_role'] = role_code
        new_ass['fk_id_contact'] = contact_id
        row = self.table_contacts.rowCount()
        self.table_contacts.insertRow(row)
        self.assignment_set_row(row, new_ass)
        
    def remove_contact(self):
        #LOGGER.debug("remove_contact():")
        row = self.table_contacts.currentRow()
        ass_id = int(self.table_contacts.item(row, 6).data(Qt.DisplayRole))
        #LOGGER.debug(f"  {row=}, {ass_id=}")
        if ass_id == 0:
            return
        self.assigned_contacts.mark_delete(ass_id)
        self.table_contacts.removeRow(row)

    def add_creator(self):
        contact_id = self.cmb_creator.currentData()
        new_id = self.assigned_contacts.new()
        new_ass = self.assigned_contacts.get(new_id)
        new_ass['contact_role'] = 'OR'
        new_ass['fk_id_contact'] = contact_id
        row = self.table_contacts.rowCount()
        self.table_contacts.insertRow(row)
        self.assignment_set_row(row, new_ass)

    def validate_important_metadata(self):
        if self.txt_title.toPlainText() and self.txt_abstract.toPlainText():
            return True
        self.tabWidget.setCurrentIndex(self.tab_important_idx)
        QMessageBox.warning(self, 'Unvollständige Metadaten',
                                'Es müssen mindesten Titel und Zusammenfassung angegeben werden. Bitte ergänzen.')
        return False

    def tab_current_changed(self):
        LOGGER.debug('tab_current_changed()')
        prev_tab_idx = self.tab_current_idx
        self.tab_current_idx = self.tabWidget.currentIndex()

        if prev_tab_idx == self.tab_important_idx:
            self.validate_important_metadata()

        if prev_tab_idx == self.tab_links_idx:  # Changed from the Links tab to another → save currently edited link
            self.save_link(self.current_link_id)
        elif self.tab_current_idx == self.tab_links_idx:
            self.tab_links_update_form()

        if self.tab_current_idx == self.tab_contacts_idx:
            self.tab_contacts_update_form()
        
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
        self.tab_links_clear_form()
        # get ID of currently selected link
        self.current_link_id = self.cmb_link_select.currentData()
        LOGGER.debug(f'  neu {self.cmb_link_select.currentIndex()=}; {self.current_link_id=}')
        current_link = self.links.get(self.current_link_id)
        if current_link['name']: self.txt_link_name.setText(current_link['name'])
        if current_link['type']:
            idx = self.cmb_link_type.findData(current_link['type'])
            LOGGER.debug(f'  link type {current_link["type"]}: idx = {idx}')
            self.cmb_link_type.setCurrentIndex(idx)
        if current_link['url']: self.txt_link_url.setText(current_link['url'])
        if current_link['description']: self.txt_link_description.setText(current_link['description'])
        if current_link['format']: self.txt_link_format.setText(current_link['format'])
        if current_link['mime']: 
            idx = self.cmb_link_mime.findData(current_link['mime'])
            LOGGER.debug(f'  link mime {current_link["mime"]}: idx = {idx}')
            self.cmb_link_mime.setCurrentIndex(idx)
        if current_link['size']: self.lne_link_size.setText(str(current_link['size']))

    def tab_contacts_update_form(self):
        #LOGGER.debug(f"Available contacts: {self.available_contacts.get_organisation('GCI GmbH')}")
        pass

    def dlg_accept(self):
        """OK-Button bestätigt+schließt nur, wenn Minimalangaben vollständig sind und aktueller Link gespeichert werden konnte."""
        important_validated = self.validate_important_metadata()
        link_saved = self.save_link(self.current_link_id)
        if important_validated and link_saved:
            self.accept()

    def prepare_editor(self, datasource_uri, connection):
        self.table = datasource_uri.table()
        self.schema = datasource_uri.schema()
        if self.new_metadata_record:
            LOGGER.info(f'New metadata for layer {datasource_uri.table()}, {connection}')
            data = [[None] * 16]
        else:
            LOGGER.info(f'Edit metadata for layer {datasource_uri.table()}, {connection}')
            sql = ("SELECT id, title, abstract, project_number, categories, keywords, themes,"  # 0 - 6
                   " spatial_level, minimum_optimal_scale, maximum_optimal_scale,"  # 7 - 9
                   " publication_date, data_last_update, publication_frequency,"  # 10 - 12
                   " confidentiality, license, license_attribution "  # 13 - 15
                   f"FROM pgmetadata.dataset WHERE schema_name = '{self.schema}' and table_name = '{self.table}'")
            try:
                data = connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when querying the database: ') + str(e))
                return False
        
        # primary/foreign key for currently edited layer metadata
        self.dataset_id = data[0][0]
        
        # fill simple fields
        if data[0][1]: self.txt_title.setPlainText(data[0][1])
        if data[0][2]: self.txt_abstract.setPlainText(data[0][2])
        if data[0][3]: self.txt_project_number.setPlainText(data[0][3])
        if data[0][5]: self.txt_keywords.setPlainText(str(data[0][5]))
        if data[0][7]: self.txt_spatial_level.setPlainText(data[0][7])
        if data[0][8]: self.lne_minimum_optimal_scale.setText(str(data[0][8]))
        if data[0][9]: self.lne_maximum_optimal_scale.setText(str(data[0][9]))
        if data[0][15]: self.txt_license_attribution.setPlainText(data[0][15])
        publ = data[0][10]
        if publ and not (type(publ) == QVariant and publ.isNull()):
            self.set_datetime_publ(publ)
        upd = data[0][11]
        if upd and not (type(upd) == QVariant and upd.isNull()):
            self.set_datetime_upd(upd)
        
        # get categories and fill comboBox
        self.cmb_categories.clear()
        self.categories = get_glossary(connection, 'dataset.categories')
        self.cmb_categories.addItems(self.categories.values())  # fill comboBox with categories
        if data[0][4]:
            selected_categories_keys = postgres_array_to_list(data[0][4])
        else:
            selected_categories_keys = []
        selected_categories_values = []
        for i in selected_categories_keys:
            selected_categories_values.append(self.categories[i])
        self.cmb_categories.setCheckedItems(selected_categories_values)  # set selected categories as checked
        
        # get themes and fill comboBox
        self.cmb_themes.clear()
        self.themes = query_to_ordereddict(connection, 'id', ['code', 'label'], "FROM pgmetadata.theme ORDER BY label")
        if data[0][6]:
            selected_themes_keys = postgres_array_to_list(data[0][6])
        else:
            selected_themes_keys = []
        selected_themes_values = []
        for theme in self.themes.values():
            self.cmb_themes.addItem(theme['label'], theme['code'])
            for i in selected_themes_keys:
                if i == theme['code']:
                    selected_themes_values.append(theme['label'])
        self.cmb_themes.setCheckedItems(selected_themes_values)  # set selected themes as checked

        # get publication frequencies and fill combobox
        self.cmb_freq.clear()
        self.frequencies = get_glossary(connection, 'dataset.publication_frequency')
        for code, freq in self.frequencies.items():
            self.cmb_freq.addItem(freq, code)
        selected_code = data[0][12]
        if not selected_code or (type(selected_code) == QVariant and selected_code.isNull()):
            self.cmb_freq.setCurrentIndex(self.cmb_freq.findData('UNK'))
        else:        
            self.cmb_freq.setCurrentIndex(self.cmb_freq.findData(selected_code))
            
        # get license values and fill combobox
        self.cmb_license.clear()
        self.licenses = get_glossary(connection, 'dataset.license')
        self.licenses[NULL] = 'Keine Lizenz'  #TODO: Löschen, sobald Schlüssel in offiziellem Plugin enthalten
        for code, lic in self.licenses.items():
            self.cmb_license.addItem(lic, code)
        selected_code = data[0][14]
        if not selected_code or (type(selected_code) == QVariant and selected_code.isNull()):
            self.cmb_license.setCurrentIndex(self.cmb_license.findData(NULL))  #TODO: anpassen, sobald Schlüssel in offiziellem Plugin enthalten
        else:        
            self.cmb_license.setCurrentIndex(self.cmb_license.findData(selected_code))
            
        # get confidentialty value and fill combobox
        self.confidentialities = get_glossary(connection, 'dataset.confidentiality')
        if 'UNK' not in self.confidentialities:  #TODO: Löschen, sobald Schlüssel in offiziellem Plugin enthalten
            self.confidentialities['UNK'] = 'Unbekannt'
        self.cmb_confidentiality.clear()
        self.cmb_confidentiality2.clear()        
        for code, confid in self.confidentialities.items():
            self.cmb_confidentiality.addItem(confid, code)
            self.cmb_confidentiality2.addItem(confid, code)
        selected_code = data[0][13]
        if not selected_code or (type(selected_code) == QVariant and selected_code.isNull()):
            self.cmb_confidentiality.setCurrentIndex(self.cmb_confidentiality.findData('UNK'))
            self.cmb_confidentiality2.setCurrentIndex(self.cmb_confidentiality.findData('UNK'))
        else:        
            self.cmb_confidentiality.setCurrentIndex(self.cmb_confidentiality.findData(selected_code))
            self.cmb_confidentiality2.setCurrentIndex(self.cmb_confidentiality.findData(selected_code))

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
        
        # set up link type presets 
        self.cmb_link_type_preset.clear()
        for preset in LINK_TYPE_PRESETS:
            self.cmb_link_type_preset.addItem(preset)
        self.cmb_link_type_preset.setCurrentIndex(-1)
        
        # get links and fill comboBox
        self.cmb_link_select.clear()
        self.tab_links_clear_form()
        self.links.read_from_db(connection, self.dataset_id)
        self.current_link_id = None  # heißt: gibt noch keinen Link, der angezeigt werden kann
        if self.links.count():
            for link in self.links.get_all():
                self.cmb_link_select.addItem(link['name'], link['id'])
            self.cmb_link_select.setCurrentIndex(0)
            LOGGER.debug(f'open_editor(): {self.current_link_id=}')
        self.tab_links_update_form()
        
        # set up contacts tab and creator “quick-add” form
        self.available_contacts.read_from_db(connection)
        self.roles = get_glossary(connection, 'contact.contact_role')
        self.assigned_contacts.read_from_db(connection, self.dataset_id)
        self.table_contacts.setRowCount(self.assigned_contacts.count())
        for row, assignment in enumerate(self.assigned_contacts.get_all()):
            self.assignment_set_row(row, assignment)
        hdr = self.table_contacts.horizontalHeader()
        hdr.setVisible(True)
        hdr.hideSection(6)  # assigned_contact_id only for internal use
        self.table_contacts.resizeColumnsToContents()    
        for col in range(self.table_contacts.columnCount() - 1):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            if hdr.sectionSize(col) > 180:
                hdr.resizeSection(col, 180)
        for contact_id, contact in self.available_contacts.get_organisation_flat('GCI GmbH').items():
            self.cmb_creator.addItem(contact, contact_id)
        self.cmb_creator.setCurrentIndex(-1)
        
    def open_editor(self, datasource_uri, connection, new: bool = False):
        """Show editor dialog, return True for successful edit, None for cancel, False for error"""
        self.new_metadata_record = new
        self.prepare_editor(datasource_uri, connection)
        self.show()
        result = self.exec_()
        if result:
            result = self.write_edits_to_db(connection)
        else:
            result = None
        return result

    def write_edits_to_db(self, connection) -> bool:
        schema = sql_quote_or_null(self.schema)
        table = sql_quote_or_null(self.table)
        title = sql_quote_or_null(self.txt_title.toPlainText())
        abstract = sql_quote_or_null(self.txt_abstract.toPlainText())
        project_number = sql_quote_or_null(self.txt_project_number.toPlainText())
        keywords = sql_quote_or_null(self.txt_keywords.toPlainText())
        if self.dattim_publ.isEnabled():
            pubdate = "'" + self.dattim_publ.dateTime().toString(Qt.ISODate) + "'"
        else:
            pubdate = 'NULL'
        if self.dattim_upd.isEnabled():
            upddate = "'" + self.dattim_upd.dateTime().toString(Qt.ISODate) + "'"
        else:
            upddate = 'NULL'
        freq = sql_quote_or_null(self.cmb_freq.currentData())
        confidentiality = sql_quote_or_null(self.cmb_confidentiality.currentData())
        license = sql_quote_or_null(self.cmb_license.currentData())
        license_attribution = sql_quote_or_null(self.txt_license_attribution.toPlainText())
        spatial_level = sql_quote_or_null(self.txt_spatial_level.toPlainText())
        minimum_optimal_scale = sql_quote_or_null(self.lne_minimum_optimal_scale.text(), as_number=True)
        maximum_optimal_scale = sql_quote_or_null(self.lne_maximum_optimal_scale.text(), as_number=True)

        new_categories_keys = dict_reverse_lookup(self.categories, self.cmb_categories.checkedItems())
        new_categories_array = list_to_postgres_array(new_categories_keys)
        
        new_themes_values = self.cmb_themes.checkedItems()
        new_themes_keys = []
        for theme in self.themes.values():
            for i in new_themes_values:
                if i == theme['label']:
                    new_themes_keys.append(theme['code'])
        new_themes_array = list_to_postgres_array(new_themes_keys)
        
        if self.new_metadata_record:
            sql = ("INSERT INTO pgmetadata.dataset (schema_name, table_name, title, abstract, project_number, keywords, categories, themes,"
                   " publication_date, data_last_update, publication_frequency, confidentiality, license, license_attribution,"
                   " minimum_optimal_scale, maximum_optimal_scale, spatial_level) "
                   f"VALUES ({schema}, {table}, {title}, {abstract}, {project_number}, {keywords},"
                   f" {new_categories_array}, {new_themes_array}, {pubdate}, {upddate}, {freq}, {confidentiality}, {license}, {license_attribution},"
                   f" {minimum_optimal_scale}, {maximum_optimal_scale}, {spatial_level})")
            try:
                connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when inserting metadata record into the database: ') + str(e))
                return False
            sql = f"SELECT id FROM pgmetadata.dataset WHERE schema_name = {schema} and table_name = {table}"
            try:
                data = connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when querying new metadata record: ') + str(e))
                return False
            self.dataset_id = data[0][0]
        else:
            sql = (f"UPDATE pgmetadata.dataset SET title = {title}, abstract = {abstract}, project_number = {project_number},"
                   f" keywords = {keywords}, categories = {new_categories_array}, themes = {new_themes_array},"
                   f" publication_date = {pubdate}, data_last_update = {upddate}, publication_frequency = {freq},"
                   f" confidentiality = {confidentiality}, license = {license}, license_attribution = {license_attribution},"
                   f" minimum_optimal_scale = {minimum_optimal_scale}, maximum_optimal_scale = {maximum_optimal_scale}, spatial_level = {spatial_level} "
                   f"WHERE schema_name = {schema} and table_name = {table}")
            try:
                connection.executeSql(sql)
            except QgsProviderConnectionException as e:
                LOGGER.critical(tr('Error when updating the database: ') + str(e))
                return False
        
        self.save_link(self.current_link_id)
        if not self.links.write_to_db(connection, self.dataset_id):
            return False
        if not self.assigned_contacts.write_to_db(connection, self.dataset_id):
            return False
            
        return True
