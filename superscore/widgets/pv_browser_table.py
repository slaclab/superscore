import logging
from enum import Enum, auto
from typing import Dict, List, Any
from qtpy import QtCore

from superscore.model import Parameter
from superscore.type_hints import TagSet

logger = logging.getLogger(__name__)

NO_DATA = "--"


class PV_BROWSER_HEADER(Enum):
    DEVICE = 0
    PV = auto()
    READBACK = auto()
    TAGS = auto()

    def display_string(self) -> str:
        return self._strings[self]


# Must be added outside class def to avoid processing as an enum member
PV_BROWSER_HEADER._strings = {
    PV_BROWSER_HEADER.DEVICE: "Device",
    PV_BROWSER_HEADER.PV: "PV Name",
    PV_BROWSER_HEADER.READBACK: "Readback",
    PV_BROWSER_HEADER.TAGS: "Tags",
}


class PVBrowserTableModel(QtCore.QAbstractTableModel):
    def __init__(self, client, parent=None):
        super().__init__(parent=parent)
        self.client = client
        self._data = list(self.client.search(
            ("entry_type", "eq", Parameter),
        ))

    def rowCount(self, _=QtCore.QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, _=QtCore.QModelIndex()) -> int:
        return len(PV_BROWSER_HEADER)

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ) -> Any:
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                return PV_BROWSER_HEADER(section).display_string()
        return None

    def data(
        self,
        index: QtCore.QModelIndex,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ) -> Any:
        column = PV_BROWSER_HEADER(index.column())
        if not index.isValid():
            return None
        elif role == QtCore.Qt.TextAlignmentRole and index.data() == NO_DATA:
            return QtCore.Qt.AlignCenter
        elif role == QtCore.Qt.ToolTipRole:
            entry = self._data[index.row()]
            if column == PV_BROWSER_HEADER.PV:
                return entry.pv_name
            elif column == PV_BROWSER_HEADER.READBACK and entry.readback is not None:
                return entry.readback.pv_name
        elif role == QtCore.Qt.DisplayRole:
            entry = self._data[index.row()]
            if column == PV_BROWSER_HEADER.DEVICE:
                return None
            elif column == PV_BROWSER_HEADER.PV:
                return entry.pv_name
            elif column == PV_BROWSER_HEADER.READBACK:
                return entry.readback.pv_name if entry.readback else NO_DATA
            elif column == PV_BROWSER_HEADER.TAGS:
                return entry.tags if entry.tags else {}
        elif role == QtCore.Qt.UserRole:
            # Return the full entry object for further processing
            entry = self._data[index.row()]
            return entry
        return None


class PVBrowserFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None, tag_set: TagSet = None):
        super().__init__(parent=parent)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.setFilterKeyColumn(PV_BROWSER_HEADER.PV.value)

        self.tag_set = tag_set or {}  # Initialize with an empty tag dict

    def set_tag_set(self, tag_set: TagSet) -> None:
        """Set the tag set for filtering. Apply filter to model immediately.

        Parameters
        ----------
        tag_set : TagSet
            The set of tags to filter entries by.
        """
        self.tag_set = tag_set
        logger.debug(f"Tag set updated: {self.tag_set}")
        self.invalidateFilter()

    def is_tag_subset(self, entry_tags: TagSet) -> bool:
        """Check if the entry's tags are a subset of the filter's tag set.

        Parameters
        ----------
        entry_tags : TagSet
            The tags of the entry to check.

        Returns
        -------
        bool
            True if the entry's tags are a subset of the filter's tag set, False otherwise.
        """
        is_subset = all(self.tag_set[group].issubset(entry_tags.get(group, set())) for group in self.tag_set)
        logger.debug(f"Tag values subset: {is_subset}")

        return is_subset

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        row_index = self.sourceModel().index(source_row, 0, source_parent)
        entry = self.sourceModel().data(row_index, QtCore.Qt.UserRole)
        if not entry:
            return False

        logger.debug(f"Filtering row {source_row} with entry: {entry}")

        search_accepts_row = super().filterAcceptsRow(source_row, source_parent)
        return self.is_tag_subset(entry.tags) and search_accepts_row


class CSVTableModel(QtCore.QAbstractTableModel):
    def __init__(self, csv_data: List[Dict[str, Any]], parent=None):
        super().__init__(parent=parent)
        self._data = csv_data
        self._headers = self._build_headers()
        
    def _build_headers(self) -> List[str]:
        """Build headers from the first row of data"""
        if not self._data:
            return []
        
        headers = ['PV', 'Description']
        # Add all group column names
        if self._data[0].get('groups'):
            headers.extend(sorted(self._data[0]['groups'].keys()))
        
        return headers
    
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._data)
    
    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._headers)
    
    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
    
    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None
        
        row_data = self._data[index.row()]
        column_name = self._headers[index.column()]
        
        if role == QtCore.Qt.DisplayRole:
            if column_name == 'PV':
                return row_data.get('PV', '')
            elif column_name == 'Description':
                return row_data.get('Description', '')
            else:
                # This is a group column
                group_values = row_data.get('groups', {}).get(column_name, [])
                return ', '.join(group_values) if group_values else ''
        
        elif role == QtCore.Qt.ToolTipRole:
            if column_name == 'PV':
                return f"PV: {row_data.get('PV', '')}"
            elif column_name == 'Description':
                return f"Description: {row_data.get('Description', '')}"
            else:
                # This is a group column
                group_values = row_data.get('groups', {}).get(column_name, [])
                if group_values:
                    return f"{column_name}:\n" + '\n'.join(f"• {val}" for val in group_values)
                else:
                    return f"{column_name}: No data"
        
        elif role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
        
        elif role == QtCore.Qt.UserRole:
            # Return the full row data for further processing
            return row_data
        
        return None