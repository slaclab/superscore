import qtawesome as qta
from qtpy import QtCore, QtWidgets

from superscore.client import Client
from superscore.permission_manager import PermissionManager
from superscore.widgets.page.page import Page
from superscore.widgets.pv_browser_table import (PV_BROWSER_HEADER,
                                                 PVBrowserFilterProxyModel,
                                                 PVBrowserTableModel)
from superscore.widgets.squirrel_table_view import SquirrelTableView
from superscore.widgets.tag import TagDelegate, TagsWidget


class PVBrowserPage(Page):

    sigOpenPVDetails = QtCore.Signal(QtCore.QModelIndex, QtWidgets.QAbstractItemView)
    sigAddPV = QtCore.Signal()

    def __init__(self, client: Client, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.client = client

        self.setup_ui()

    def setup_ui(self):
        """Initialize the PV browser page with the PV browser table."""

        pv_browser_layout = QtWidgets.QVBoxLayout()
        pv_browser_layout.setContentsMargins(0, 11, 0, 0)
        self.setLayout(pv_browser_layout)

        self.search_bar = QtWidgets.QLineEdit(self)
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.addAction(
            qta.icon("fa5s.search"),
            QtWidgets.QLineEdit.LeadingPosition,
        )

        self.add_pv_button = QtWidgets.QPushButton()
        self.add_pv_button.setIcon(qta.icon("ph.plus"))
        self.add_pv_button.setIconSize(QtCore.QSize(16, 16))
        self.add_pv_button.setText("Add PV")
        self.add_pv_button.setObjectName("add-pv-btn")
        self.add_pv_button.clicked.connect(self.sigAddPV)

        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)

        search_bar_lyt = QtWidgets.QHBoxLayout()
        search_bar_lyt.addWidget(self.search_bar)
        search_bar_lyt.addSpacerItem(spacer)
        search_bar_lyt.addWidget(self.add_pv_button)
        pv_browser_layout.addLayout(search_bar_lyt)

        filter_tags = TagsWidget(tag_groups=self.client.backend.get_tags(), enabled=True)
        pv_browser_layout.addWidget(filter_tags)

        pv_browser_model = PVBrowserTableModel(self.client)
        self.pv_browser_filter = PVBrowserFilterProxyModel()
        self.pv_browser_filter.setSourceModel(pv_browser_model)

        self.pv_browser_table = SquirrelTableView(self)
        self.pv_browser_table.setModel(self.pv_browser_filter)
        self.pv_browser_table.setItemDelegateForColumn(
            PV_BROWSER_HEADER.TAGS.value,
            TagDelegate(self.client.backend.get_tags())
        )
        header_view = self.pv_browser_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.ResizeMode.Fixed)
        header_view.setSectionResizeMode(PV_BROWSER_HEADER.TAGS.value, header_view.ResizeMode.Stretch)
        header_view.sectionResized.connect(self.pv_browser_table.resizeRowsToContents)
        pv_browser_layout.addWidget(self.pv_browser_table)
        self.pv_browser_table.resizeColumnsToContents()

        self.search_bar.textEdited.connect(self.search_bar_middle_man)
        filter_tags.tagSetChanged.connect(self.pv_browser_filter.set_tag_set)
        self.pv_browser_table.doubleClicked.connect(self.open_details_middle_man)

        permission_manager = PermissionManager.get_instance()
        if not permission_manager.is_admin():
            self.add_pv_button.hide()
            self.pv_browser_table.setColumnHidden(PV_BROWSER_HEADER.DELETE.value, True)
        permission_manager.admin_status_changed.connect(self.add_pv_button.setVisible)
        permission_manager.admin_status_changed.connect(
            lambda is_admin: self.pv_browser_table.setColumnHidden(
                PV_BROWSER_HEADER.DELETE.value,
                not is_admin,
            )
        )

        self.pv_browser_table.clicked.connect(self.maybe_delete_row)

        self.setStyleSheet(
            """
            QPushButton {
                padding: 8px;
                border-radius: 4px;
                text-align: left;
            }
            QPushButton#add-pv-btn {
                border: 1px solid #555555;
                background-color: white;
            }
            QPushButton#add-pv-btn:hover {
                background-color: lightgray;
            }
            """
        )

    @QtCore.Slot(QtCore.QModelIndex)
    def maybe_delete_row(self, index):
        if index.column() == PV_BROWSER_HEADER.DELETE.value:
            self.pv_browser_table.model().sourceModel().removeRow(index.row())

    @QtCore.Slot()
    def search_bar_middle_man(self):
        search_text = self.search_bar.text()
        self.pv_browser_filter.setFilterFixedString(search_text)

    @QtCore.Slot(QtCore.QModelIndex)
    def open_details_middle_man(self, index: QtCore.QModelIndex):
        if not isinstance(index, QtCore.QModelIndex) or not index.isValid():
            return
        self.sigOpenPVDetails.emit(index, self.pv_browser_table)
