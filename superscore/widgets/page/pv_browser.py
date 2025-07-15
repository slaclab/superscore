import qtawesome as qta
from qtpy import QtCore, QtWidgets, QtGui
from typing import Dict, List, Any
from superscore.client import Client
from superscore.widgets.page.page import Page
from superscore.widgets.pv_browser_table import (PV_BROWSER_HEADER,
                                                 PVBrowserFilterProxyModel,
                                                 PVBrowserTableModel, 
                                                 CSVTableModel)
from superscore.widgets.squirrel_table_view import SquirrelTableView
from superscore.widgets.tag import TagDelegate, TagsWidget
from superscore.utils import parse_csv_to_dict
from superscore.permission_manager import PermissionManager

class PVBrowserPage(Page):

    open_details_signal = QtCore.Signal(QtCore.QModelIndex, QtWidgets.QAbstractItemView)

    def __init__(self, client: Client, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.client = client
        self.permission_manager = PermissionManager.get_instance()

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

        search_bar_lyt = QtWidgets.QHBoxLayout()
        spacer = QtWidgets.QSpacerItem(1, 1, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        search_bar_lyt.addWidget(self.search_bar)
        search_bar_lyt.addSpacerItem(spacer)

        #clear_icon = qta.icon("ph.x-circle-fill", color=superscore.color.GREY, scale_factor=1.1)
        #self.clear_button.setIcon(clear_icon)
        
        self.import_pvs = QtWidgets.QPushButton("import pvs")
        self.import_pvs.setFixedWidth(100)
        self.import_pvs.clicked.connect(self.select_file)

        if self.permission_manager.is_admin():
            search_bar_lyt.addWidget(self.import_pvs)

        pv_browser_layout.addLayout(search_bar_lyt)

        filter_tags = TagsWidget(tag_groups=self.client.backend.get_tags(), enabled=True)
        pv_browser_layout.addWidget(filter_tags)

        pv_browser_model = PVBrowserTableModel(self.client)
        self.pv_browser_filter = PVBrowserFilterProxyModel()
        self.pv_browser_filter.setSourceModel(pv_browser_model)

        self.pv_browser_table = SquirrelTableView(self)
        self.pv_browser_table.setModel(self.pv_browser_filter)
        self.pv_browser_table.setItemDelegateForColumn(PV_BROWSER_HEADER.TAGS.value, TagDelegate(self.client.backend.get_tags()))
        header_view = self.pv_browser_table.horizontalHeader()
        header_view.setSectionResizeMode(header_view.Fixed)
        header_view.setStretchLastSection(True)
        header_view.sectionResized.connect(self.pv_browser_table.resizeRowsToContents)
        pv_browser_layout.addWidget(self.pv_browser_table)
        self.pv_browser_table.resizeColumnsToContents()

        self.search_bar.editingFinished.connect(self.search_bar_middle_man)
        filter_tags.tagSetChanged.connect(self.pv_browser_filter.set_tag_set)
        self.pv_browser_table.doubleClicked.connect(self.open_details_middle_man)

    def select_file(self) -> None:
        """Open file dialog to select CSV file"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.csv_file_path = file_path
            self.csv_data = parse_csv_to_dict(self.csv_file_path)
            self.show_table()
    
    def show_table(self) -> None:
        """Show the parsed cvs data in a table dialog"""
        dialog = CSVTableDialog(self.csv_data, self)
        dialog.exec_()

    @QtCore.Slot()
    def search_bar_middle_man(self):
        search_text = self.search_bar.text()
        self.pv_browser_filter.setFilterFixedString(search_text)

    @QtCore.Slot(QtCore.QModelIndex)
    def open_details_middle_man(self, index: QtCore.QModelIndex):
        if not isinstance(index, QtCore.QModelIndex) or not index.isValid():
            return
        self.open_details_signal.emit(index, self.pv_browser_table)

class CSVTableDialog(QtWidgets.QDialog):
    def __init__(self, csv_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.csv_data = csv_data
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("CSV Data Table")
        self.setGeometry(200, 200, 1000, 600)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Info label
        info_label = QtWidgets.QLabel(f"Displaying {len(self.csv_data)} rows of CSV data")
        info_label.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        layout.addWidget(info_label)
        
        # Create table view
        self.table_view = QtWidgets.QTableView()
        self.model = CSVTableModel(self.csv_data)
        self.table_view.setModel(self.model)
        
        # Configure table appearance
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.table_view.setSortingEnabled(True)
        
        # Auto-resize columns
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        
        layout.addWidget(self.table_view)
        
        h_layout = QtWidgets.QHBoxLayout()
        import_button = QtWidgets.QPushButton("Import Data")
        import_button.clicked.connect(self.import_data)
        h_layout.addWidget(import_button)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.close)
        h_layout.addWidget(close_button)

        layout.addLayout(h_layout)

    def import_data(self) -> None:
        """Import all data into backend"""        
        if not self.csv_data:
            QtWidgets.QMessageBox.warning(self, "Warning", "No data to import.")
            return
        
        success_count, error_count, errors = self._import_rows(self.csv_data)
        self._show_import_results(success_count, error_count, errors, len(self.csv_data))
            
        if success_count > 0:
            self.accept()  
            

    def _import_rows(self, rows_to_import: List[Dict[str, Any]]) -> tuple:
        """
        Import rows into the backend.
        Returns: (success_count, error_count, error_list)
        """
        success_count = 0
        error_count = 0
        errors = []
        
        for i, row_data in enumerate(rows_to_import):
            try:
                parameter = self._create_parameter_from_row(row_data)
                
                # Add to backend through parent
                if self.parent_page and hasattr(self.parent_page, 'client'):
                    self.parent_page.client.add(parameter)
                    success_count += 1
                    print(f"Successfully imported: {row_data['PV']}")
                else:
                    raise Exception("No client connection available")
                
            except Exception as e:
                error_count += 1
                error_msg = f"Row {i+1} ({row_data.get('PV', 'Unknown')}): {str(e)}"
                errors.append(error_msg)
                print(f"Failed to import: {error_msg}")
        
        # Refresh parent table if any imports succeeded
        if success_count > 0 and self.parent_page:
            try:
                self.parent_page.refresh_table()
                print("Parent table refreshed")
            except Exception as e:
                print(f"Failed to refresh parent table: {e}")
        
        return success_count, error_count, errors
    
    def _show_import_results(self, success_count: int, error_count: int, errors: List[str], total_attempted: int):
        """Show import results to user"""
        if error_count == 0:
            QtWidgets.QMessageBox.information(
                self,
                "Import Successful",
                f"Successfully imported all {success_count} entries."
            )
        elif success_count == 0:
            error_details = "\n".join(errors[:3])  
            if len(errors) > 3:
                error_details += f"\n... and {len(errors) - 3} more errors"
            
            QtWidgets.QMessageBox.critical(
                self,
                "Import Failed",
                f"Failed to import any entries.\n\n"
                f"First few errors:\n{error_details}"
            )
        else:
            error_details = "\n".join(errors[:3])  
            if len(errors) > 3:
                error_details += f"\n... and {len(errors) - 3} more errors"
            
            QtWidgets.QMessageBox.warning(
                self,
                "Import Completed with Errors",
                f"Import Results:\n"
                f"• Successfully imported: {success_count}\n"
                f"• Failed: {error_count}\n"
                f"• Total attempted: {total_attempted}\n\n"
                f"First few errors:\n{error_details}"
            )