import json
from typing import Callable, Dict, Optional, Set, Tuple

import qtawesome as qta
from qtpy.QtCore import QModelIndex, QPoint, Qt
from qtpy.QtWidgets import (QAbstractItemView, QAction, QDialog, QFrame,
                            QHBoxLayout, QHeaderView, QInputDialog, QLabel,
                            QLineEdit, QMenu, QMessageBox, QPushButton,
                            QSizePolicy, QSpacerItem, QTableWidget,
                            QTableWidgetItem, QVBoxLayout, QWidget)


class TagsDialog(QDialog):
    """
    Dialog for managing tags within a group.

    This dialog allows users to view, add, remove, and search for tags
    belonging to a specific tag group. Changes are saved automatically
    when tags are added or removed.
    """

    def __init__(self, group_name: str, tags_dict: Optional[Dict[int, str]] = None, parent: Optional[QWidget] = None,
                 auto_save_callback: Optional[Callable[[str, Dict[int, str]], None]] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle(f"Tags: {group_name}")
        self.setMinimumSize(400, 500)

        self.tags_dict = tags_dict or {}

        self.group_name = group_name
        self.auto_save_callback = auto_save_callback

        layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self.filter_tags)
        search_layout.addWidget(self.search_input)

        layout.addLayout(search_layout)

        self.tag_list = QTableWidget()
        self.tag_list.setColumnCount(2)
        self.tag_list.setHorizontalHeaderLabels(["Tag", ""])
        self.tag_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tag_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.tag_list.setColumnWidth(1, 50)
        self.tag_list.verticalHeader().setVisible(False)
        self.tag_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tag_list.setAlternatingRowColors(True)
        self.tag_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tag_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tag_list.customContextMenuRequested.connect(self.show_context_menu)
        self.tag_list.setShowGrid(False)

        layout.addWidget(self.tag_list)

        self.populate_tag_list()

        button_layout = QHBoxLayout()

        add_button = QPushButton("+ New Tag")
        add_button.clicked.connect(self.add_new_tag)

        search_layout.addWidget(add_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    def populate_tag_list(self) -> None:
        """
        Populate the tag list table with tags matching the current filter.
        """
        self.tag_list.setRowCount(0)

        filter_text = self.search_input.text().lower()

        for key, tag in self.tags_dict.items():
            if filter_text and filter_text not in tag.lower():
                continue

            row = self.tag_list.rowCount()
            self.tag_list.insertRow(row)

            item = QTableWidgetItem(tag)
            self.tag_list.setItem(row, 0, item)

            delete_button = QPushButton()
            delete_button.setIcon(qta.icon("msc.trash"))
            delete_button.setFlat(True)

            delete_button.clicked.connect(lambda _, k=key: self.remove_tag(k))

            delete_button.setProperty("tag_key", key)

            cell_widget = QWidget()
            layout = QHBoxLayout(cell_widget)
            layout.addWidget(delete_button)
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)
            self.tag_list.setCellWidget(row, 1, cell_widget)

    def filter_tags(self) -> None:
        """
        Filter the tag dict based on the search input.

        This method is called when the search text changes, and it
        updates the tag dict to show only tags that match the filter.
        """
        self.populate_tag_list()

    def add_new_tag(self) -> None:
        """
        Add a new tag to the group.
        """
        tag, ok = QInputDialog.getText(self, "Add Tag", "Enter tag name:")
        if ok and tag:
            # Check if tag already exists in values
            if tag in self.tags_dict.values():
                QMessageBox.warning(self, "Duplicate Tag",
                                    f"The tag '{tag}' already exists.")
            else:
                next_key = 0
                if self.tags_dict:
                    next_key = max(self.tags_dict.keys()) + 1

                self.tags_dict[next_key] = tag
                self.populate_tag_list()

                if self.auto_save_callback:
                    self.auto_save_callback(self.group_name, self.tags_dict)

    def remove_tag(self, key: int) -> None:
        """
        Remove a tag from the group by its key.

        Parameters
        ----------
        key : int
            The dictionary key of the tag to remove
        """
        tag = self.tags_dict[key]
        confirm = QMessageBox.question(
            self,
            'Confirm Remove',
            f'Are you sure you want to remove the tag "{tag}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            del self.tags_dict[key]
            self.populate_tag_list()

            if self.auto_save_callback:
                self.auto_save_callback(self.group_name, self.tags_dict)

    def show_context_menu(self, position: QPoint) -> None:
        """
        Show a context menu for the tag at the given position.
        """
        menu = QMenu()

        item = self.tag_list.itemAt(position)
        if item:
            row = item.row()
            tag_item = self.tag_list.item(row, 0)
            tag = tag_item.text()

            key = None
            for k, v in self.tags_dict.items():
                if v == tag:
                    key = k
                    break

            if key is not None:
                remove_action = QAction(f"Remove '{tag}'", self)
                remove_action.triggered.connect(lambda _, k=key: self.remove_tag(k))
                menu.addAction(remove_action)

                menu.exec_(self.tag_list.viewport().mapToGlobal(position))


class TagGroupsWindow(QWidget):
    """
    Main window for managing tag groups.

    This window allows users to create, edit, and delete tag groups, as well as
    manage the tags within each group.
    """

    def __init__(self) -> None:
        """
        Initialize the tag groups window.

        Sets up the UI and initializes the data structure for storing tag groups.
        """
        super().__init__()
        self.setGeometry(100, 100, 800, 500)
        self.setWindowTitle("Tag Groups Manager")

        self.groups_data: Dict[int, Tuple[str, str, Dict[int, str]]] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        main_frame = QFrame()
        main_frame.setFrameShape(QFrame.StyledPanel)
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel("Tag Groups")
        title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        h_layout = QHBoxLayout()

        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        h_layout.addSpacerItem(spacer)

        new_group_button = QPushButton("+ New Group")
        new_group_button.setFixedWidth(100)
        new_group_button.clicked.connect(self.add_new_group)
        h_layout.addWidget(new_group_button)

        main_layout.addLayout(h_layout)

        frame_layout.addWidget(header_widget)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setStyleSheet('QTableView::item {border-right: 1px solid #d6d9dc;}')
        # Start with editing disabled
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self.handle_double_click)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setFrameShape(QFrame.NoFrame)
        self.table.cellChanged.connect(self.handle_cell_changed)

        self.add_new_group()

        self.table.setColumnWidth(0, 100)  # Group name column
        self.table.setColumnWidth(1, 100)  # Tag count column
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Description column
        self.table.setColumnWidth(3, 80)  # Edit button column
        self.table.setColumnWidth(4, 80)  # Delete button column

        for i in range(self.table.rowCount()):
            self.table.setRowHeight(i, 50)

        frame_layout.addWidget(self.table)

        main_layout.addWidget(main_frame)

        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #ddd;
            }
            QTableWidget::item {
                padding: 5px;
            }
            alternate-background-color: #f0f0f0;
        """)

        self.table.setShowGrid(False)
        self.original_edit_triggers = QTableWidget.NoEditTriggers

    def get_group_name_from_row(self, row: int) -> str:
        """
        Get the group name from a specific row.

        Parameters
        ----------
        row : int
            The row index

        Returns
        -------
        str
            The group name displayed in that row
        """
        group_button = self.table.cellWidget(row, 0)
        return group_button.text() if group_button else f"New Group {row + 1}"

    def get_description_from_row(self, row: int) -> str:
        """
        Get the description from a specific row.

        Parameters
        ----------
        row : int
            The row index

        Returns
        -------
        str
            The description text in that row
        """
        desc_item = self.table.item(row, 2)
        return desc_item.text() if desc_item else "New group description"

    def update_group_data(self, row: int, name: str, description: str,
                          tags_dict: Optional[Dict[int, str]] = None) -> None:
        """
        Update the groups_data dictionary when group details change.

        Parameters
        ----------
        row : int
            The row index in the table
        name : str
            The name of the group
        description : str
            The updated description
        tags_dict : Dict[int, str], optional
            New dictionary of tags if provided, by default None
        """
        if tags_dict is not None:
            tag_dict = tags_dict
        elif row in self.groups_data:
            tag_dict = self.groups_data[row][2]
        else:
            tag_dict = {}

        self.groups_data[row] = (name, description, tag_dict)

    def delete_row(self, row: int) -> bool:
        """
        Delete a row from the table and its corresponding data.

        Parameters
        ----------
        row : int
            The row index to delete

        Returns
        -------
        bool
            True if the row was deleted, False otherwise
        """
        if row < 0 or row >= self.table.rowCount():
            print(f"Invalid row index: {row}")
            return False

        group_name = self.get_group_name_from_row(row)

        confirm = QMessageBox.question(
            self,
            'Confirm Delete',
            f'Are you sure you want to delete the group "{group_name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            if row in self.groups_data:
                del self.groups_data[row]

            self.table.removeRow(row)

            '''
            # Reindex the remaining groups to maintain sequential keys
            new_groups_data = {}
            for i in range(self.table.rowCount()):
                old_row = -1
                for j in range(i, self.table.rowCount() + 1):
                    if j in self.groups_data:
                        old_row = j
                        break

                if old_row != -1:
                    new_groups_data[i] = self.groups_data[old_row]

                    # Update the row properties on buttons
                    edit_button = self.table.cellWidget(i, 3)
                    if edit_button:
                        edit_button.setProperty("row", i)

                    delete_button = self.table.cellWidget(i, 4)
                    if delete_button:
                        delete_button.setProperty("row", i)

            self.groups_data = new_groups_data
            '''

            return True

        return False

    def handle_double_click(self, index: QModelIndex) -> None:
        """
        Handle double-click on a table row.

        Opens the tag dialog for the selected group with auto-saving enabled.

        Parameters
        ----------
        index : QModelIndex
            The model index that was double-clicked
        """
        row = index.row()

        edit_button = self.table.cellWidget(row, 3)
        if edit_button and edit_button.property("editing"):
            return

        group_name = self.get_group_name_from_row(row)
        description = self.get_description_from_row(row)

        current_tags_dict = {}
        if row in self.groups_data:
            current_tags_dict = self.groups_data[row][2]

        # Create a callback function for auto-saving
        def auto_save_tags(group_name: str, tags_dict: Dict[int, str]) -> None:
            self.update_group_data(row, group_name, description, tags_dict)

            tag_count = len(tags_dict)
            count_text = f"{tag_count} {'Tags' if tag_count != 1 else 'Tag'}"
            count_item = self.table.item(row, 1)
            if count_item:
                count_item.setText(count_text)

        dialog = TagsDialog(group_name, current_tags_dict, self, auto_save_tags)
        dialog.exec_()

    def add_new_group(self) -> int:
        """
        Add a new group to the table and data structure.

        Returns
        -------
        int
            The row index of the newly added group
        """
        current_row = self.table.rowCount()
        self.table.insertRow(current_row)
        self.table.setRowHeight(current_row, 50)

        group_name = f"New Group {current_row + 1}"
        description = "New group description"

        self.groups_data[current_row] = (group_name, description, {})

        group_button = QPushButton(group_name)
        group_button.setStyleSheet(
            "text-align: center; background-color: #f0f0f0; border-radius: 10px;")
        self.table.setCellWidget(current_row, 0, group_button)

        count_item = QTableWidgetItem("0 Tags")
        count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(current_row, 1, count_item)

        desc_item = QTableWidgetItem(description)
        desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(current_row, 2, desc_item)

        edit_button = QPushButton("Edit")
        edit_button.setProperty("editing", False)
        edit_button.setProperty("row", current_row)
        edit_button.clicked.connect(self.toggle_edit_mode)
        self.table.setCellWidget(current_row, 3, edit_button)

        delete_button = QPushButton("Delete")
        delete_button.setProperty("row", current_row)
        delete_button.clicked.connect(self.handle_delete_clicked)
        self.table.setCellWidget(current_row, 4, delete_button)

        return current_row

    def toggle_edit_mode(self) -> None:
        """
        Toggle the edit mode for a row.

        When entering edit mode, replaces the group name button with a line edit
        and makes the description editable. When exiting edit mode, saves the changes
        and restores the button.
        """
        button = self.sender()
        if not button:
            return

        current_row = -1
        for i in range(self.table.rowCount()):
            if self.table.cellWidget(i, 3) == button:
                current_row = i
                break

        if current_row < 0:
            return

        is_editing = button.property("editing")

        if not is_editing:
            self.table.setEditTriggers(QTableWidget.AllEditTriggers)

            group_button = self.table.cellWidget(current_row, 0)
            group_name = group_button.text() if group_button else "Group"

            button.setProperty("original_name", group_name)

            line_edit = QLineEdit(group_name)
            line_edit.setFrame(False)

            line_edit.setStyleSheet(
                "background-color: white; border: 1px solid #ccc; border-radius: 3px; padding: 3px;")
            self.table.setCellWidget(current_row, 0, line_edit)
            line_edit.selectAll()
            line_edit.setFocus()

            desc_item = self.table.item(current_row, 2)
            if desc_item:
                desc_item.setFlags(Qt.ItemIsEnabled |
                                   Qt.ItemIsEditable | Qt.ItemIsSelectable)

            button.setText("Save")
            button.setProperty("editing", True)

        else:
            line_edit = self.table.cellWidget(current_row, 0)
            new_name = ""

            if isinstance(line_edit, QLineEdit):
                new_name = line_edit.text()
            else:
                new_name = button.property("original_name") or "Group"

            if not new_name:
                new_name = "Group"

            desc_item = self.table.item(current_row, 2)
            description = desc_item.text() if desc_item else "No description"

            self.update_group_data(current_row, new_name, description)

            self.table.removeCellWidget(current_row, 0)
            group_button = QPushButton(new_name)
            group_button.setStyleSheet(
                "text-align: center; background-color: #f0f0f0; border-radius: 10px;")
            self.table.setCellWidget(current_row, 0, group_button)

            if desc_item:
                desc_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            self.table.setEditTriggers(QTableWidget.NoEditTriggers)

            self.table.setSelectionBehavior(QTableWidget.SelectRows)

            button.setText("Edit")
            button.setProperty("editing", False)

    def edit_next_cell(self, row: int, column: int) -> None:
        """
        Move to the next editable cell after a cell has been edited.

        Parameters
        ----------
        row : int
            The current row
        column : int
            The current column
        """
        if column == 0:
            desc_item = self.table.item(row, 2)
            if desc_item:
                self.table.setCurrentCell(row, 2)
                self.table.editItem(desc_item)
        else:
            pass

    def handle_cell_changed(self, row: int, column: int) -> None:
        """
        Handle when a cell's content has changed.

        Moves to the next editable cell if in edit mode.

        Parameters
        ----------
        row : int
            The row of the changed cell
        column : int
            The column of the changed cell
        """
        edit_button = self.table.cellWidget(row, 3)
        if edit_button and edit_button.property("editing"):
            self.edit_next_cell(row, column)

    def get_all_data(self) -> Dict[str, Tuple[Set[str], str]]:
        """
        Return the entire groups data dictionary.

        Returns
        -------
        Dict[str, Tuple[Set[str], str]]
            Dictionary with group names as keys and tuples of (tags set, description) as values
        """
        return self.groups_data

    def save_data(self, filename: str) -> bool:
        """
        Save the groups data to a file.

        Parameters
        ----------
        filename : str
            Path to the file where data should be saved

        Returns
        -------
        bool
            True if save was successful, False otherwise
        """
        try:
            with open(filename, 'w') as f:
                json.dump(self.groups_data, f, default=lambda o: list(o)
                          if isinstance(o, set) else o)
            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False

    def load_data(self, filename: str) -> bool:
        """
        Load the groups data from a file.

        Parameters
        ----------
        filename : str
            Path to the file to load data from

        Returns
        -------
        bool
            True if load was successful, False otherwise
        """
        try:
            with open(filename, 'r') as f:
                data = json.load(f)

            self.groups_data = {int(k): v for k, v in data.items()}

            self.rebuild_table_from_data()
            return True
        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def rebuild_table_from_data(self) -> None:
        """
        Rebuild the table based on the loaded data.

        Clears the current table and repopulates it with rows for each group
        in the groups_data dictionary.
        """
        self.table.setRowCount(0)

        for row, (group_name, description, tag_dict) in self.groups_data.items():
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setRowHeight(row_idx, 50)

            group_button = QPushButton(group_name)
            group_button.setStyleSheet(
                "text-align: center; background-color: #f0f0f0; border-radius: 10px;")
            self.table.setCellWidget(row_idx, 0, group_button)

            tag_count = len(tag_dict)
            count_text = f"{tag_count} {'Tags' if tag_count != 1 else 'Tag'}"
            count_item = QTableWidgetItem(count_text)
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 1, count_item)

            desc_item = QTableWidgetItem(description)
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 2, desc_item)

            edit_button = QPushButton("Edit")
            edit_button.setProperty("editing", False)
            edit_button.setProperty("row", row_idx)
            edit_button.clicked.connect(self.toggle_edit_mode)
            self.table.setCellWidget(row_idx, 3, edit_button)

            delete_button = QPushButton("Delete")
            delete_button.setProperty("row", row_idx)
            delete_button.clicked.connect(self.handle_delete_clicked)
            self.table.setCellWidget(row_idx, 4, delete_button)

    def print_all_data(self) -> str:
        """
        Print all the group data in a readable format.

        Returns
        -------
        str
            String representation of the groups data dictionary
        """
        print("\n===== TAG GROUPS DATA =====")
        print(f"Total Groups: {len(self.groups_data)}")
        print("===========================")

        for row, (group_name, description, tag_dict) in self.groups_data.items():
            tag_list = ", ".join(sorted(tag_dict.values())) if tag_dict else "No tags"

            print(f"\nGROUP {row+1}: {group_name}")
            print(f"Description: {description}")
            print(f"Tags ({len(tag_dict)}): {tag_list}")
            print("---------------------------")

        print("\n")

        return str(self.groups_data)

    def handle_delete_clicked(self) -> None:
        """
        Handle click on a delete button.

        Identifies which row's delete button was clicked and deletes that row.
        """
        button = self.sender()
        if not button:
            return

        original_row = button.property("row")

        current_row = -1
        for i in range(self.table.rowCount()):
            if self.table.cellWidget(i, 4) == button:
                current_row = i
                break

        row_to_delete = current_row if current_row >= 0 else original_row

        self.delete_row(row_to_delete)
