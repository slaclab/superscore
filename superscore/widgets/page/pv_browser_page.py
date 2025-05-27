import qtawesome as qta
from qtpy import QtWidgets

from superscore.client import Client
from superscore.widgets.page.page import Page
from superscore.widgets.pv_browser_table import (PVBrowserFilterProxyModel,
                                                 PVBrowserTableModel)
from superscore.widgets.tag import TagsWidget


class PVBrowserPage(Page):
    """
    A page for browsing process variables (PVs) in a table format.

    This class extends the Page class to provide a specific implementation for
    displaying and managing PVs in a tabular format. It inherits the functionality
    of the Page class while focusing on PV-related operations.
    """
    def __init__(self, parent: QtWidgets.QWidget, client: Client):
        super().__init__(parent)
        self.setObjectName("PVBrowserPage")
        self.client = client

        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface for the PV Browser page."""
        pv_browser_layout = QtWidgets.QVBoxLayout()
        pv_browser_layout.setContentsMargins(0, 11, 0, 0)
        self.setLayout(pv_browser_layout)

        search_bar = QtWidgets.QLineEdit(self)
        search_bar.setClearButtonEnabled(True)
        search_bar.addAction(
            qta.icon("fa5s.search"),
            QtWidgets.QLineEdit.LeadingPosition,
        )
        search_bar_lyt = QtWidgets.QHBoxLayout()
        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        search_bar_lyt.addWidget(search_bar)
        search_bar_lyt.addSpacerItem(spacer)
        pv_browser_layout.addLayout(search_bar_lyt)

        pv_browser_model = PVBrowserTableModel(self.client)
        pv_browser_filter = PVBrowserFilterProxyModel()
        pv_browser_filter.setSourceModel(pv_browser_model)
        search_bar.editingFinished.connect(pv_browser_filter.setFilterFixedString)

        tags_widget = TagsWidget(
            tag_groups=self.client.backend.get_tags(),
            enabled=True,
        )
        pv_browser_layout.addWidget(tags_widget)

        pv_browser_table = QtWidgets.QTableView(self)
        pv_browser_table.setModel(pv_browser_filter)
        pv_browser_table.verticalHeader().hide()
        header_view = pv_browser_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.ResizeToContents)
        header_view.setStretchLastSection(True)
        pv_browser_layout.addWidget(pv_browser_table)
