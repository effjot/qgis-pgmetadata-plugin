# -*- coding: utf-8 -*-
""" Browser panel entry for adding themes """

import sip
# import posixpath

from qgis.core import (
    QgsApplication,
    QgsDataCollectionItem,
    QgsDataItem,
    QgsDataItemProvider,
    QgsDataProvider,
    QgsDirectoryItem,
    QgsErrorItem,
    QgsExpressionContextUtils,
    QgsProject,
    QgsProviderRegistry,
    QgsMessageLog,
    Qgis
)
from qgis.PyQt.QtGui import QIcon

from pg_metadata.qgis_plugin_tools.tools.resources import (
#    plugin_path,
    resources_path,
)


class ThemeBrowserRootItem(QgsDataCollectionItem):
    """ PgMetadata root entry in the browser panel. """

    #local_project_removed = pyqtSignal()

    def __init__(self, plugin=None):
        QgsDataCollectionItem.__init__(self, None, "PgMetadata Themes", "PgMetadata Themes")
        self.setIcon(QIcon(resources_path('icons', 'icon.png')))
        self.plugin = plugin
        # self.project_manager = plugin.manager
        # self.mc = self.project_manager.mc if self.project_manager is not None else None
        # self.error = ""
        # self.wizard = None

    # def update_client_and_manager(self, mc=None, manager=None, err=None):
    #     """Update Mergin client and project manager - used when starting or after a config change."""
    #     self.mc = mc
    #     self.project_manager = manager
    #     self.error = err
    #     self.depopulate()

    def createChildren(self):
        # if self.error or self.mc is None:
        #     self.error = self.error if self.error else "Not configured!"
        #     error_item = QgsErrorItem(self, self.error, "Mergin/error")
        #     error_item.setIcon(QIcon(icon_path("exclamation-triangle-solid.svg")))
        #     sip.transferto(error_item, self)
        #     return [error_item]

        items = []
        my_projects = MerginGroupItem(self, "My projects", "created", "user-solid.svg", 1, self.plugin)
        my_projects.setState(QgsDataItem.Populated)
        my_projects.refresh()
        sip.transferto(my_projects, self)
        items.append(my_projects)

        shared_projects = MerginGroupItem(self, "Shared with me", "shared", "user-friends-solid.svg", 2, self.plugin)
        shared_projects.setState(QgsDataItem.Populated)
        shared_projects.refresh()
        sip.transferto(shared_projects, self)
        items.append(shared_projects)

        all_projects = MerginGroupItem(self, "Explore", None, "list-solid.svg", 3, self.plugin)
        all_projects.setState(QgsDataItem.Populated)
        all_projects.refresh()
        sip.transferto(all_projects, self)
        items.append(all_projects)

        return items

    # def actions(self, parent):
    #     action_configure = QAction(QIcon(icon_path("cog-solid.svg")), "Configure", parent)
    #     action_configure.triggered.connect(self.plugin.configure)

    #     action_create = QAction(QIcon(icon_path("plus-square-solid.svg")), "Create new project", parent)
    #     action_create.triggered.connect(self.plugin.create_new_project)
    #     actions = [action_configure]
    #     if self.mc:
    #         actions.append(action_create)
    #     return actions


class MerginGroupItem(QgsDataCollectionItem):
    """ Mergin group data item. Contains filtered list of Mergin projects. """

    def __init__(self, parent, grp_name, grp_filter, icon, order, plugin):
        QgsDataCollectionItem.__init__(self, parent, grp_name, "/Mergin" + grp_name)
        self.filter = grp_filter
        # self.setIcon(QIcon(icon_path(icon)))
        self.setSortKey(order)
        self.plugin = plugin
        self.project_manager = 'prj manager' #plugin.manager
        self.projects = []
        self.group_name = grp_name
        self.total_projects_count = None
        self.fetch_more_item = None

    def fetch_projects(self): #, page=1, per_page=PROJS_PER_PAGE):
        # """Get paginated projects list from Mergin service. If anything goes wrong, return an error item."""
        # if self.project_manager is None:
        #     error_item = QgsErrorItem(self, "Failed to log in. Please check the configuration", "/Mergin/error")
        #     sip.transferto(error_item, self)
        #     return [error_item]
        # try:
        #     resp = self.project_manager.mc.paginated_projects_list(
        #         flag=self.filter, page=page, per_page=per_page, order_params="namespace_asc,name_asc")
        #     self.projects += resp["projects"]
        #     self.total_projects_count = int(resp["count"]) if is_number(resp["count"]) else 0
        # except URLError:
        #     error_item = QgsErrorItem(self, "Failed to get projects from server", "/Mergin/error")
        #     sip.transferto(error_item, self)
        #     return [error_item]
        # except Exception as err:
        #     error_item = QgsErrorItem(self, "Error: {}".format(str(err)), "/Mergin/error")
        #     sip.transferto(error_item, self)
        #     return [error_item]
        self.projects = [{'namespace': 'a namespace', 'name': 'a project'}]
        self.total_projects_count = 1
        return None

    def createChildren(self):
        if not self.projects:
            error = self.fetch_projects()
            if error is not None:
                return error
        items = []
        for project in self.projects:
            project_name = project["namespace"] + project["name"]  # posix path for server API calls
            local_proj_path = project_name #= mergin_project_local_path(project_name)
            if local_proj_path is None: # or not os.path.exists(local_proj_path):
                # item = MerginRemoteProjectItem(self, project, self.project_manager)
                # item.setState(QgsDataItem.Populated)  # make it non-expandable
                pass
            else:
                item = MerginLocalProjectItem(self, project, self.project_manager)
            sip.transferto(item, self)
            items.append(item)
        # self.set_fetch_more_item()
        # if self.fetch_more_item is not None:
        #     items.append(self.fetch_more_item)
        return items

    # def set_fetch_more_item(self):
    #     """Check if there are more projects to be fetched from Mergin service and set the fetch-more item."""
    #     if self.fetch_more_item is not None:
    #         try:
    #             self.removeChildItem(self.fetch_more_item)
    #         except RuntimeError:
    #             pass
    #         self.fetch_more_item = None
    #     fetched_count = len(self.projects)
    #     if fetched_count < self.total_projects_count:
    #         self.fetch_more_item = FetchMoreItem(self)
    #         self.fetch_more_item.setState(QgsDataItem.Populated)
    #         sip.transferto(self.fetch_more_item, self)
    #     group_name = f"{self.group_name} ({self.total_projects_count})"
    #     self.setName(group_name)

    # def fetch_more(self):
    #     """Fetch another page of projects and add them to the group item."""
    #     if self.fetch_more_item is None:
    #         QMessageBox.information(None, "Fetch Mergin Projects", "All projects already listed.")
    #         return
    #     page_to_get = floor(self.rowCount() / PROJS_PER_PAGE) + 1
    #     dummy = self.fetch_projects(page=page_to_get)
    #     self.refresh()

    # def reload(self):
    #     self.projects = []
    #     self.refresh()

    # def actions(self, parent):
    #     action_refresh = QAction(QIcon(icon_path("redo-solid.svg")), "Reload", parent)
    #     action_refresh.triggered.connect(self.reload)
    #     actions = [action_refresh]
    #     if self.fetch_more_item is not None:
    #         action_fetch_more = QAction(QIcon(icon_path("fetch_more.svg")), "Fetch more", parent)
    #         action_fetch_more.triggered.connect(self.fetch_more)
    #         actions.append(action_fetch_more)
    #     if self.name().startswith("My projects"):
    #         action_create = QAction(
    #             QIcon(icon_path("plus-square-solid.svg")), "Create new project", parent
    #         )
    #         action_create.triggered.connect(self.plugin.create_new_project)
    #         actions.append(action_create)
    #     return actions


class MerginLocalProjectItem(QgsDirectoryItem):
    """Data item to represent a local Mergin project."""

    def __init__(self, parent, project, project_manager):
        self.project_name = 'test project name' #posixpath.join(project["namespace"], project["name"])  # posix path for server API calls
        self.path = 'test path' #mergin_project_local_path(self.project_name)
        QgsDirectoryItem.__init__(self, parent, self.project_name, self.path, "/Mergin/" + self.project_name)
        self.setSortKey(f"1 {self.name()}")
        self.project = project
        self.project_manager = project_manager
        # if self.project_manager is not None:
        #     self.mc = self.project_manager.mc
        # else:
        #     self.mc = None

    # def open_project(self):
    #     self.project_manager.open_project(self.path)

    # def project_status(self):
    #     if not self.path:
    #         return
    #     if not self.project_manager.unsaved_changes_check(self.path):
    #         return
    #     self.project_manager.project_status(self.path)

    # def sync_project(self):
    #     if not self.path:
    #         return
    #     self.project_manager.project_status(self.path)

    # def _reload_project(self):
    #     """ This will forcefully reload the QGIS project because the project (or its data) may have changed """
    #     qgis_files = find_qgis_files(self.path)
    #     if QgsProject.instance().fileName() in qgis_files:
    #         iface.addProject(QgsProject.instance().fileName())

    # def remove_local_project(self):
    #     if not self.path:
    #         return
    #     cur_proj = QgsProject.instance()
    #     cur_proj_path = cur_proj.absolutePath()
    #     msg = (
    #         "Your local changes will be lost. Make sure your project is synchronised with server. \n\n"
    #         "Do you want to proceed?".format(self.project_name)
    #     )
    #     btn_reply = QMessageBox.question(
    #         None, "Remove local project", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
    #     )
    #     if btn_reply == QMessageBox.No:
    #         return

    #     if os.path.exists(self.path):
    #         try:
    #             if same_dir(cur_proj_path, self.path):
    #                 msg = (
    #                     "The project is currently open. It will get cleared if you proceed.\n\n"
    #                     "Proceed anyway?".format(self.project_name)
    #                 )
    #                 btn_reply = QMessageBox.question(
    #                     None, "Remove local project", msg, QMessageBox.No | QMessageBox.No, QMessageBox.Yes
    #                 )
    #                 if btn_reply == QMessageBox.No:
    #                     return

    #                 cur_proj.clear()
    #                 # clearing project does not trigger toggling toolbar buttons state
    #                 # change, so we need to fire the singnal manually
    #                 iface.newProjectCreated.emit()
    #                 registry = QgsProviderRegistry.instance()
    #                 registry.setLibraryDirectory(registry.libraryDirectory())

    #             # remove logging file handler
    #             mp = MerginProject(self.path)
    #             log_file_handler = mp.log.handlers[0]
    #             log_file_handler.close()
    #             mp.log.removeHandler(log_file_handler)
    #             del mp

    #             # as releasing lock on previously open files takes some time
    #             # we have to wait a bit before removing them, otherwise rmtree
    #             # will fail and removal of the local rpoject will fail as well
    #             QTimer.singleShot(250, lambda: shutil.rmtree(self.path))
    #         except PermissionError as e:
    #             QgsApplication.messageLog().logMessage(f"Mergin plugin: {str(e)}")
    #             msg = (
    #                 f"Failed to delete your project {self.project_name} because it is open.\n"
    #                 "You might need to close project or QGIS to remove its files."
    #             )
    #             QMessageBox.critical(None, "Project delete", msg, QMessageBox.Close)
    #             return

    #     settings = QSettings()
    #     settings.remove(f"Mergin/localProjects/{self.project_name}")
    #     self.parent().reload()

    # def submit_logs(self):
    #     if not self.path:
    #         return
    #     self.project_manager.submit_logs(self.path)

    # def clone_remote_project(self):
    #     user_info = self.mc.user_info()
    #     dlg = CloneProjectDialog(username=user_info["username"], user_organisations=user_info.get("organisations", []))
    #     if not dlg.exec_():
    #         return  # cancelled
    #     try:
    #         self.mc.clone_project(self.project_name, dlg.project_name, dlg.project_namespace)
    #         msg = "Mergin project cloned successfully."
    #         QMessageBox.information(None, "Clone project", msg, QMessageBox.Close)
    #         self.parent().reload()
    #     except (URLError, ClientError) as e:
    #         msg = "Failed to clone project {}:\n\n{}".format(self.project_name, str(e))
    #         QMessageBox.critical(None, "Clone project", msg, QMessageBox.Close)
    #     except LoginError as e:
    #         login_error_message(e)

    # def actions(self, parent):
    #     action_remove_local = QAction(QIcon(icon_path("trash-solid.svg")), "Remove locally", parent)
    #     action_remove_local.triggered.connect(self.remove_local_project)

    #     action_open_project = QAction("Open QGIS project", parent)
    #     action_open_project.triggered.connect(self.open_project)

    #     action_sync_project = QAction(QIcon(icon_path("sync-solid.svg")), "Synchronize", parent)
    #     action_sync_project.triggered.connect(self.sync_project)

    #     action_clone_remote = QAction(QIcon(icon_path("copy-solid.svg")), "Clone", parent)
    #     action_clone_remote.triggered.connect(self.clone_remote_project)

    #     action_status = QAction(QIcon(icon_path("info-circle-solid.svg")), "Status", parent)
    #     action_status.triggered.connect(self.project_status)

    #     action_diagnostic_log = QAction(QIcon(icon_path("medkit-solid.svg")), "Diagnostic log", parent)
    #     action_diagnostic_log.triggered.connect(self.submit_logs)

    #     actions = [
    #         action_open_project,
    #         action_status,
    #         action_sync_project,
    #         action_clone_remote,
    #         action_remove_local,
    #         action_diagnostic_log,
    #     ]
    #     return actions




class DataItemProvider(QgsDataItemProvider):
    def __init__(self, plugin):
        QgsDataItemProvider.__init__(self)
        self.root_item = None
        self.plugin = plugin

    def name(self):
        return "PgMetadata Themes"

    def capabilities(self):
        return QgsDataProvider.Database

    def createDataItem(self, path, parentItem):
        if not parentItem:
            root_item = ThemeBrowserRootItem(self.plugin)
            sip.transferto(root_item, None)
            self.root_item = root_item
            return root_item
        else:
            return None