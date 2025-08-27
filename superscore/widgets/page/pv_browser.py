from typing import Any, Dict, List

import qtawesome as qta
from qtpy import QtCore, QtGui, QtWidgets

from superscore.client import Client
from superscore.model import Parameter
from superscore.permission_manager import PermissionManager
from superscore.utils import parse_csv_to_dict
from superscore.widgets.page.page import Page
from superscore.widgets.pv_browser_table import (PV_BROWSER_HEADER,
                                                 CSVTableModel,
                                                 PVBrowserFilterProxyModel,
                                                 PVBrowserTableModel)
from superscore.widgets.squirrel_table_view import SquirrelTableView
from superscore.widgets.tag import TagDelegate, TagsWidget


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
        pv_browser_layout.setContentsMargins(0, 11, 11, 0)
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

        self.import_pvs = QtWidgets.QPushButton("Import PVs")
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
        header_view.setSectionResizeMode(header_view.ResizeMode.Fixed)
        header_view.setStretchLastSection(True)
        header_view.sectionResized.connect(self.pv_browser_table.resizeRowsToContents)
        pv_browser_layout.addWidget(self.pv_browser_table)
        self.pv_browser_table.resizeColumnsToContents()

        self.search_bar.textEdited.connect(self.search_bar_middle_man)
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

    def refresh_table(self):
        """Refresh the PV browser table after import"""
        source_model = self.pv_browser_filter.sourceModel()
        if hasattr(source_model, 'refresh'):
            source_model.refresh()
        elif hasattr(source_model, 'layoutChanged'):
            source_model.layoutChanged.emit()


class CSVTableDialog(QtWidgets.QDialog):
    def __init__(self, csv_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.csv_data = csv_data
        self.parent_page = parent
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("CSV Data Table")
        self.setGeometry(200, 200, 1200, 600)

        layout = QtWidgets.QVBoxLayout(self)

        info_label = QtWidgets.QLabel(f"Displaying {len(self.csv_data)} rows of CSV data")
        info_label.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        layout.addWidget(info_label)

        backend_tag_def = {}
        if self.parent_page and hasattr(self.parent_page, 'client'):
            backend_tag_def = self.parent_page.client.backend.get_tags()

        self.model = CSVTableModel(self.csv_data, backend_tag_def)

        validation_results = self.model.get_validation_results()
        self._show_validation_feedback(layout, validation_results)

        self.table_view = QtWidgets.QTableView()
        self.table_view.setModel(self.model)

        tags_column_index = 2
        tag_delegate = TagDelegate(self.model.tag_def, self.table_view)
        self.table_view.setItemDelegateForColumn(tags_column_index, tag_delegate)

        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QtWidgets.QTableView.SelectRows)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)

        self.table_view.resizeColumnsToContents()

        layout.addWidget(self.table_view)

        button_layout = QtWidgets.QHBoxLayout()

        import_all_btn = QtWidgets.QPushButton("Import Data")
        import_all_btn.clicked.connect(self.import_data)
        button_layout.addWidget(import_all_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def import_data(self) -> None:
        """Import all data into backend"""
        if not self.csv_data:
            QtWidgets.QMessageBox.warning(self, "Warning", "No data to import.")
            return

        try:
            success_count, error_count, errors = self._import_rows(self.csv_data)
            self._show_import_results(success_count, error_count, errors, len(self.csv_data))

            if success_count > 0:
                self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", f"Failed to import all data: {str(e)}")
            print(f"Import failed: {e}")

    def _import_rows(self, rows_to_import: List[Dict[str, Any]]) -> tuple:
        """
        Import rows into the backend.
        Returns: (success_count, error_count, error_list)
        """
        parameters = []

        for row_data in rows_to_import:
            parameter = self._create_parameter_from_row(row_data)
            parameters.append(parameter)

        parent = getattr(self, "parent_page", None)
        client = getattr(parent, "client", None)
        backend = getattr(client, "backend", None)
        if backend is None:
            return 0, len(rows_to_import), ["No client connection available"]
        try:
            backend.add_multiple_pvs(parameters)
        except Exception as e:
            print(f"Failed to import rows: {str(e)}")
            return 0, len(rows_to_import), [str(e)]

        if parent is not None:
            parent.refresh_table()

        return len(rows_to_import), 0, []

    def _create_parameter_from_row(self, row_data: Dict[str, Any]):
        """Create a Parameter object from CSV row data with proper tag handling"""
        pv_name = row_data['PV']
        description = row_data['Description']
        csv_groups = row_data['groups']

        tag_def = {}
        if self.parent_page and hasattr(self.parent_page, 'client'):
            tag_def = self.parent_page.client.backend.get_tags()

        tagset = self._create_tag_mapping_from_csv(csv_groups, tag_def)

        parameter = Parameter(
            pv_name=pv_name,
            description=description,
            tags=tagset,
        )

        return parameter

    def _create_tag_mapping_from_csv(self, csv_groups: Dict[str, List[str]], tag_def: Dict) -> Dict[int, set]:
        """
        Create a mapping from CSV groups to your tag system.
        """
        tagset = {}

        for tag_group_id, (group_name, desc, choices) in tag_def.items():
            csv_values = csv_groups.get(group_name, [])
            tag_ids = set()

            for tag_id, tag_name in choices.items():
                if tag_name in csv_values:
                    tag_ids.add(tag_id)

            tagset[tag_group_id] = tag_ids

        return tagset

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
                f"Error:\n{error_details}"
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

    def _show_validation_feedback(self, layout, validation_results):
        """Show detailed validation feedback to user"""
        rejected_groups = validation_results['rejected_groups']
        rejected_values = validation_results['rejected_values']

        if rejected_groups or rejected_values:
            validation_group = QtWidgets.QGroupBox("Validation Results")
            validation_group.setStyleSheet("QGroupBox { color: orange; font-weight: bold; }")
            validation_layout = QtWidgets.QVBoxLayout(validation_group)

            if rejected_groups:
                group_label = QtWidgets.QLabel(
                    f"Rejected Groups (not found in backend): {', '.join(rejected_groups)}"
                )
                group_label.setStyleSheet("color: red; padding: 2px;")
                group_label.setWordWrap(True)
                validation_layout.addWidget(group_label)

            if rejected_values:
                values_label = QtWidgets.QLabel("Rejected Values:")
                values_label.setStyleSheet("color: red; padding: 2px;")
                validation_layout.addWidget(values_label)

                for group_name, rejected_vals in rejected_values.items():
                    val_detail = QtWidgets.QLabel(
                        f"   • {group_name}: {', '.join(sorted(rejected_vals))}"
                    )
                    val_detail.setStyleSheet("color: red; padding-left: 10px;")
                    val_detail.setWordWrap(True)
                    validation_layout.addWidget(val_detail)

            if self.model.tag_def:
                available_label = QtWidgets.QLabel("Available Backend Options:")
                available_label.setStyleSheet("color: green; font-weight: bold; padding: 2px;")
                validation_layout.addWidget(available_label)

                for tag_group_id, (group_name, desc, choices) in self.model.tag_def.items():
                    option_detail = QtWidgets.QLabel(
                        f"   • {group_name}: {', '.join(sorted(choices.values()))}"
                    )
                    option_detail.setStyleSheet("color: green; padding-left: 10px;")
                    option_detail.setWordWrap(True)
                    validation_layout.addWidget(option_detail)

            layout.addWidget(validation_group)


class TagMappingDialog(QtWidgets.QDialog):
    """Dialog to help users map CSV groups to existing tag groups"""

    def __init__(self, csv_groups: List[str], tag_def: Dict, parent=None):
        super().__init__(parent)
        self.csv_groups = csv_groups
        self.tag_def = tag_def
        self.mappings = {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Map CSV Groups to Tags")
        self.setGeometry(300, 300, 500, 400)

        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("Map your CSV groups to existing tag groups:")
        layout.addWidget(label)

        self.mapping_widgets = {}
        for csv_group in self.csv_groups:
            group_layout = QtWidgets.QHBoxLayout()

            csv_label = QtWidgets.QLabel(f"'{csv_group}' →")
            csv_label.setFixedWidth(150)
            group_layout.addWidget(csv_label)

            combo = QtWidgets.QComboBox()
            combo.addItem("(Skip this group)")
            for tag_group_id, (group_name, desc, choices) in self.tag_def.items():
                combo.addItem(group_name, tag_group_id)

            group_layout.addWidget(combo)
            layout.addLayout(group_layout)

            self.mapping_widgets[csv_group] = combo

        button_layout = QtWidgets.QHBoxLayout()
        ok_button = QtWidgets.QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def get_mappings(self) -> Dict[str, int]:
        """Return the selected mappings"""
        mappings = {}
        for csv_group, combo in self.mapping_widgets.items():
            tag_group_id = combo.currentData()
            if tag_group_id is not None:
                mappings[csv_group] = tag_group_id
        return mappings
