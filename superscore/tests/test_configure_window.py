import sys
from unittest.mock import MagicMock, mock_open, patch

import pytest
from qtpy.QtCore import QModelIndex, QPoint
from qtpy.QtWidgets import (QApplication, QInputDialog, QLineEdit, QMenu,
                            QMessageBox, QPushButton, QTableWidget,
                            QTableWidgetItem)

from superscore.widgets.configure_window import TagGroupsWindow, TagsDialog


@pytest.fixture
def app():
    """Create a QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def window(app):
    """Create a TagGroupsWindow instance for testing."""
    window = TagGroupsWindow()
    yield window
    window.close()


@pytest.fixture
def tags_dict():
    """Sample tags dictionary for testing."""
    return {1: "Important", 2: "Urgent", 3: "Personal"}


@pytest.fixture
def mock_save_callback():
    """Mock auto_save_callback function."""
    return MagicMock()


@pytest.fixture
def dialog(app, tags_dict, mock_save_callback):
    """Create a TagsDialog instance for testing."""
    dialog = TagsDialog("Test Group", tags_dict, None, mock_save_callback)
    yield dialog
    dialog.close()


def test_TagsDialog_init(dialog, tags_dict, mock_save_callback):
    """Test that the dialog initializes correctly."""
    assert dialog.windowTitle() == "Tags: Test Group"
    assert dialog.tags_dict == tags_dict
    assert dialog.group_name == "Test Group"
    assert dialog.auto_save_callback == mock_save_callback
    assert dialog.tag_list.columnCount() == 2
    assert dialog.tag_list.rowCount() == len(tags_dict)


def test_populate_tag_list(dialog, tags_dict):
    """Test that populate_tag_list correctly populates the tag table."""
    dialog.tag_list.setRowCount(0)
    dialog.populate_tag_list()

    assert dialog.tag_list.rowCount() == len(tags_dict)

    displayed_tags = [dialog.tag_list.item(row, 0).text()
                      for row in range(dialog.tag_list.rowCount())]
    assert set(displayed_tags) == set(tags_dict.values())


def test_filter_tags(dialog, tags_dict):
    """Test that filter_tags correctly filters the tag list."""
    dialog.search_input.setText("Imp")
    dialog.filter_tags()

    assert dialog.tag_list.rowCount() == 1
    assert dialog.tag_list.item(0, 0).text() == "Important"

    dialog.search_input.setText("")
    dialog.filter_tags()
    assert dialog.tag_list.rowCount() == len(tags_dict)


@patch.object(QInputDialog, 'getText', return_value=("New Tag", True))
def test_add_new_tag_success(mock_input, dialog, mock_save_callback):
    """Test adding a new tag successfully."""
    original_count = len(dialog.tags_dict)

    dialog.add_new_tag()

    assert len(dialog.tags_dict) == original_count + 1
    assert "New Tag" in dialog.tags_dict.values()

    mock_save_callback.assert_called_once()
    assert mock_save_callback.call_args[0][0] == "Test Group"
    assert mock_save_callback.call_args[0][1] == dialog.tags_dict


@patch.object(QInputDialog, 'getText', return_value=("Important", True))
@patch.object(QMessageBox, 'warning')
def test_add_new_tag_duplicate(mock_warning, mock_input, dialog, mock_save_callback):
    """Test adding a duplicate tag."""
    original_count = len(dialog.tags_dict)

    dialog.add_new_tag()

    assert len(dialog.tags_dict) == original_count

    mock_warning.assert_called_once()

    mock_save_callback.assert_not_called()


@patch.object(QInputDialog, 'getText', return_value=("", True))
def test_add_new_tag_empty(mock_input, dialog, mock_save_callback):
    """Test adding an empty tag."""
    original_count = len(dialog.tags_dict)

    dialog.add_new_tag()

    assert len(dialog.tags_dict) == original_count

    mock_save_callback.assert_not_called()


@patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes)
def test_remove_tag_confirmed(mock_question, dialog, mock_save_callback):
    """Test removing a tag with confirmation."""
    tag_key = 1
    tag_value = dialog.tags_dict[tag_key]
    original_count = len(dialog.tags_dict)

    dialog.remove_tag(tag_key)

    assert len(dialog.tags_dict) == original_count - 1
    assert tag_key not in dialog.tags_dict
    assert tag_value not in dialog.tags_dict.values()

    mock_save_callback.assert_called_once()


@patch.object(QMessageBox, 'question', return_value=QMessageBox.No)
def test_remove_tag_cancelled(mock_question, dialog, mock_save_callback):
    """Test cancelling tag removal."""
    tag_key = 1
    original_count = len(dialog.tags_dict)

    dialog.remove_tag(tag_key)

    assert len(dialog.tags_dict) == original_count
    assert tag_key in dialog.tags_dict

    mock_save_callback.assert_not_called()


@patch.object(QMenu, 'exec_')
@patch.object(QMenu, 'addAction')
def test_show_context_menu(mock_add_action, mock_exec, dialog):
    """Test showing context menu for a tag."""
    mock_item = QTableWidgetItem("Important")
    dialog.tag_list.setItem(0, 0, mock_item)

    position = QPoint(10, 10)

    with patch.object(dialog.tag_list, 'itemAt', return_value=mock_item):
        dialog.show_context_menu(position)

    mock_add_action.assert_called_once()

    mock_exec.assert_called_once()

# ------------------- Tests for TagGroupsWindow ------------------- #


def test_TagGroupsWindow_init(window):
    """Test that the window initializes correctly."""
    assert window.windowTitle() == "Tag Groups Manager"
    assert isinstance(window.groups_data, dict)
    assert window.table.columnCount() == 5
    assert window.table.rowCount() == 1  # Should have one default row


def test_get_group_name_from_row(window):
    """Test getting group name from a row."""
    # Test with an existing row
    row_button = window.table.cellWidget(0, 0)
    expected_name = row_button.text()

    assert window.get_group_name_from_row(0) == expected_name

    # Test with a non-existent row (default name format)
    assert window.get_group_name_from_row(999) == "New Group 1000"


def test_get_description_from_row(window):
    """Test getting description from a row."""
    # Test with an existing row
    desc_item = window.table.item(0, 2)
    expected_desc = desc_item.text()

    assert window.get_description_from_row(0) == expected_desc

    # Test with a non-existent row (default description)
    assert window.get_description_from_row(999) == "New group description"


def test_update_group_data(window):
    """Test updating group data."""
    # Test updating existing row
    window.update_group_data(0, "Updated Group", "Updated description")
    assert window.groups_data[0][0] == "Updated Group"
    assert window.groups_data[0][1] == "Updated description"

    # Test updating with tags
    tags_dict = {1: "Tag1", 2: "Tag2"}
    window.update_group_data(0, "Updated Group", "Updated description", tags_dict)
    assert window.groups_data[0][2] == tags_dict

    # Test creating new row data
    window.update_group_data(999, "New Group", "New description")
    assert window.groups_data[999][0] == "New Group"
    assert window.groups_data[999][1] == "New description"
    assert window.groups_data[999][2] == {}


@patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes)
def test_delete_row_confirmed(mock_question, window):
    """Test deleting a row with confirmation."""
    # Add a second row for testing
    window.add_new_group()
    original_count = window.table.rowCount()

    # Delete the first row
    result = window.delete_row(0)

    # Check that the row was deleted
    assert result is True
    assert window.table.rowCount() == original_count - 1
    assert 0 not in window.groups_data


@patch.object(QMessageBox, 'question', return_value=QMessageBox.No)
def test_delete_row_cancelled(mock_question, window):
    """Test cancelling row deletion."""
    original_count = window.table.rowCount()

    result = window.delete_row(0)

    assert result is False
    assert window.table.rowCount() == original_count
    assert 0 in window.groups_data


def test_delete_row_invalid(window):
    """Test deleting an invalid row."""
    result = window.delete_row(999)

    assert result is False


@patch.object(TagsDialog, 'exec_', return_value=1)
def test_handle_double_click(mock_exec, window):
    """Test handling double-click on a row."""
    index = MagicMock(spec=QModelIndex)
    index.row.return_value = 0

    window.handle_double_click(index)

    mock_exec.assert_called_once()


def test_add_new_group(window):
    """Test adding a new group."""
    original_count = window.table.rowCount()

    row = window.add_new_group()

    assert window.table.rowCount() == original_count + 1
    assert row == original_count
    assert row in window.groups_data

    assert isinstance(window.table.cellWidget(row, 0), QPushButton)
    assert window.table.item(row, 1).text() == "0 Tags"
    assert window.table.item(row, 2).text() == "New group description"
    assert isinstance(window.table.cellWidget(row, 3), QPushButton)
    assert isinstance(window.table.cellWidget(row, 4), QPushButton)


@patch.object(QLineEdit, 'text', return_value="Edited Group")
def test_toggle_edit_mode(mock_text, window):
    """Test toggling edit mode for a row."""
    edit_button = window.table.cellWidget(0, 3)

    assert edit_button.property("editing") is False

    with patch.object(window.table, 'setEditTriggers') as mock_set_triggers:
        edit_button.clicked.emit()

        assert edit_button.property("editing") is True
        assert edit_button.text() == "Save"
        mock_set_triggers.assert_called_with(QTableWidget.AllEditTriggers)

        assert isinstance(window.table.cellWidget(0, 0), QLineEdit)

    with patch.object(window.table, 'setEditTriggers') as mock_set_triggers:
        edit_button.clicked.emit()

        assert edit_button.property("editing") is False
        assert edit_button.text() == "Edit"
        mock_set_triggers.assert_called_with(QTableWidget.NoEditTriggers)

        assert isinstance(window.table.cellWidget(0, 0), QPushButton)
        assert window.table.cellWidget(0, 0).text() == "Edited Group"


def test_edit_next_cell(window):
    """Test moving to the next editable cell."""
    with patch.object(window.table, 'setCurrentCell') as mock_set_current:
        with patch.object(window.table, 'editItem') as mock_edit_item:
            window.edit_next_cell(0, 0)

            mock_set_current.assert_called_with(0, 2)
            assert mock_edit_item.called

    with patch.object(window.table, 'setCurrentCell') as mock_set_current:
        window.edit_next_cell(0, 2)
        mock_set_current.assert_not_called()


def test_handle_cell_changed(window):
    """Test handling cell content changes."""
    edit_button = window.table.cellWidget(0, 3)
    edit_button.setProperty("editing", True)

    with patch.object(window, 'edit_next_cell') as mock_edit_next:
        window.handle_cell_changed(0, 0)

        mock_edit_next.assert_called_with(0, 0)


def test_get_all_data(window):
    """Test getting all group data."""
    window.groups_data = {
        0: ("Group 1", "Description 1", {1: "Tag1"}),
        1: ("Group 2", "Description 2", {2: "Tag2"})
    }

    data = window.get_all_data()

    assert data == window.groups_data


@patch('builtins.open', new_callable=mock_open)
@patch('json.dump')
def test_save_data_success(mock_json_dump, mock_file, window):
    """Test successfully saving data to a file."""
    window.groups_data = {
        0: ("Group 1", "Description 1", {1: "Tag1"}),
        1: ("Group 2", "Description 2", {2: "Tag2"})
    }

    result = window.save_data("test_file.json")

    mock_file.assert_called_with("test_file.json", 'w')
    assert mock_json_dump.called
    assert result is True


@patch('builtins.open', side_effect=IOError("Test error"))
def test_save_data_failure(mock_file, window):
    """Test handling save failure."""
    result = window.save_data("test_file.json")

    assert result is False


@patch('builtins.open', new_callable=mock_open, read_data='{"0": ["Group 1", "Description 1", {"1": "Tag1"}]}')
@patch('json.load', return_value={"0": ["Group 1", "Description 1", {"1": "Tag1"}]})
def test_load_data_success(mock_json_load, mock_file, window):
    """Test successfully loading data from a file."""
    with patch.object(window, 'rebuild_table_from_data') as mock_rebuild:
        result = window.load_data("test_file.json")

        mock_file.assert_called_with("test_file.json", 'r')
        assert mock_json_load.called
        assert mock_rebuild.called
        assert result is True

        assert 0 in window.groups_data
        assert window.groups_data[0][0] == "Group 1"


@patch('builtins.open', side_effect=IOError("Test error"))
def test_load_data_failure(mock_file, window):
    """Test handling load failure."""
    result = window.load_data("test_file.json")

    assert result is False


def test_rebuild_table_from_data(window):
    """Test rebuilding the table from loaded data."""
    window.table.setRowCount(0)

    window.groups_data = {
        0: ("Group 1", "Description 1", {1: "Tag1"}),
        1: ("Group 2", "Description 2", {2: "Tag2", 3: "Tag3"})
    }

    window.rebuild_table_from_data()

    assert window.table.rowCount() == 2

    assert window.table.cellWidget(0, 0).text() == "Group 1"
    assert window.table.item(0, 1).text() == "1 Tag"
    assert window.table.item(0, 2).text() == "Description 1"

    assert window.table.cellWidget(1, 0).text() == "Group 2"
    assert window.table.item(1, 1).text() == "2 Tags"
    assert window.table.item(1, 2).text() == "Description 2"


@patch('builtins.print')
def test_print_all_data(mock_print, window):
    """Test printing all group data."""
    window.groups_data = {
        0: ("Group 1", "Description 1", {1: "Tag1"}),
        1: ("Group 2", "Description 2", {2: "Tag2", 3: "Tag3"})
    }

    result = window.print_all_data()

    assert mock_print.called
    assert isinstance(result, str)


def test_handle_delete_clicked(window):
    """Test handling click on delete button."""
    delete_button = window.table.cellWidget(0, 4)

    with patch.object(window, 'delete_row') as mock_delete:
        delete_button.clicked.emit()

        mock_delete.assert_called_with(0)
