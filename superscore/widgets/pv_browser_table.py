import logging
from enum import Enum, auto
from typing import Any, Dict, Iterable, List

import qtawesome as qta
from qtpy import QtCore

from superscore.model import PV
from superscore.type_hints import TagSet

logger = logging.getLogger(__name__)

NO_DATA = "--"


class PV_BROWSER_HEADER(Enum):
    DEVICE = 0
    PV = auto()
    READBACK = auto()
    TAGS = auto()
    DELETE = auto()

    def display_string(self) -> str:
        return self._strings[self]


# Must be added outside class def to avoid processing as an enum member
PV_BROWSER_HEADER._strings = {
    PV_BROWSER_HEADER.DEVICE: "Device",
    PV_BROWSER_HEADER.PV: "PV Name",
    PV_BROWSER_HEADER.READBACK: "Readback",
    PV_BROWSER_HEADER.TAGS: "Tags",
    PV_BROWSER_HEADER.DELETE: "",
}


class PVBrowserTableModel(QtCore.QAbstractTableModel):
    def __init__(self, client, parent=None):
        super().__init__(parent=parent)
        self.client = client
        self._data = list(self.client.search(
            ("entry_type", "eq", PV),
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
                return entry.setpoint
            elif column == PV_BROWSER_HEADER.READBACK and entry.readback is not None:
                return entry.readback
        elif role == QtCore.Qt.DisplayRole:
            entry = self._data[index.row()]
            if column == PV_BROWSER_HEADER.DEVICE:
                return None
            elif column == PV_BROWSER_HEADER.PV:
                return entry.setpoint
            elif column == PV_BROWSER_HEADER.READBACK:
                return entry.readback or NO_DATA
            elif column == PV_BROWSER_HEADER.TAGS:
                return entry.tags if entry.tags else {}
        elif role == QtCore.Qt.DecorationRole:
            if column == PV_BROWSER_HEADER.DELETE:
                return qta.icon("msc.trash")
        elif role == QtCore.Qt.UserRole:
            # Return the full entry object for further processing
            entry = self._data[index.row()]
            return entry
        return None

    def add_pv(self, pv: PV):
        i = len(self._data)
        self.beginInsertRows(QtCore.QModelIndex(), i, i)
        self._data.append(pv)
        self.endInsertRows()

    def add_pvs(self, pvs: Iterable[PV]):
        start = len(self._data)
        self.beginInsertRows(QtCore.QModelIndex(), start, len(pvs))
        self._data.extend(pvs)
        self.endInsertRows()

    def removeRow(self, row, parent=None):
        index = self.index(row, PV_BROWSER_HEADER.PV.value)
        pv = self.data(index, QtCore.Qt.UserRole)
        try:
            self.client.backend.archive_pv(pv.uuid)
        except Exception as e:
            logger.exception(e)
        else:
            parent = parent or QtCore.QModelIndex()
            self.beginRemoveRows(parent, row, row)
            del self._data[row]
            self.endRemoveRows()

    def refetch_row(self, row):
        index = self.index(row, PV_BROWSER_HEADER.PV.value)
        pv_id = self.data(index, QtCore.Qt.UserRole).uuid
        pv = list(
            self.client.search(
                ("entry_type", "eq", PV),
                ("uuid", "eq", pv_id),
            )
        )[0]
        self._data[row] = pv
        self.dataChanged.emit(index, index)


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
    def __init__(self, csv_data: List[Dict[str, Any]], backend_tag_def=None, parent=None):
        super().__init__(parent=parent)
        self._data = csv_data
        self.backend_tag_def = backend_tag_def or {}
        self.tag_def = self._filter_to_existing_backend_groups()
        self._headers = self._build_headers()

        self.rejected_groups = []
        self.rejected_values = {}
        self.validation_summary = self._create_validation_summary()

    def _build_headers(self) -> List[str]:
        """Build headers from the first row of data"""
        if not self._data:
            return []
        headers = ['Setpoint', 'Readback', 'Description', 'Tags']
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
            if column_name == 'Setpoint':
                return row_data.get('Setpoint', '')
            elif column_name == 'Readback':
                return row_data.get('Readback', '')
            elif column_name == 'Description':
                return row_data.get('Description', '')
            elif column_name == 'Tags':
                return self._convert_groups_to_tagset(row_data.get('groups', {}))
        elif role == QtCore.Qt.ToolTipRole:
            if column_name == 'Setpoint':
                return f"Setpoint: {row_data.get('Setpoint', '')}"
            elif column_name == 'Readback':
                return f"Readback: {row_data.get('Readback', '')}"
            elif column_name == 'Description':
                return f"Description: {row_data.get('Description', '')}"
            elif column_name == 'Tags':
                groups = row_data.get('groups', {})
                tooltip_text = "Tags:\n"
                for group_name, values in groups.items():
                    if values:
                        tooltip_text += f"{group_name}: {', '.join(values)}\n"
                return tooltip_text.strip()
        elif role == QtCore.Qt.UserRole:
            return row_data

        return None

    def _filter_to_existing_backend_groups(self) -> Dict:
        """Only include CSV groups that exist in backend"""
        if not self._data or not self.backend_tag_def:
            return {}

        csv_groups = {}
        for row in self._data:
            for group_name, values in row.get('groups', {}).items():
                if group_name not in csv_groups:
                    csv_groups[group_name] = set()
                csv_groups[group_name].update(values)

        backend_group_names = {details[0]: tag_group_id for tag_group_id, details in self.backend_tag_def.items()}

        filtered_tag_def = {}
        self.rejected_groups = []

        for csv_group_name in csv_groups.keys():
            if csv_group_name in backend_group_names:
                backend_id = backend_group_names[csv_group_name]
                filtered_tag_def[backend_id] = self.backend_tag_def[backend_id]
                logger.debug(f"Accepted CSV group '{csv_group_name}' -> backend group_id {backend_id}")
            else:
                self.rejected_groups.append(csv_group_name)
                logger.warn(f"Rejected CSV group '{csv_group_name}' - not found in backend")

        return filtered_tag_def

    def _convert_groups_to_tagset(self, csv_groups: Dict[str, List[str]]) -> Dict[int, set]:
        """Convert CSV groups to TagSet format with value-level validation"""
        tagset = {}
        row_rejected_values = {}

        for tag_group_id, (group_name, desc, choices) in self.tag_def.items():
            csv_group_values = csv_groups.get(group_name, [])
            tag_ids = set()
            rejected_values_for_group = []

            backend_values = set(choices.values())

            # Validate each CSV value against backend choices
            for csv_value in csv_group_values:
                if csv_value in backend_values:
                    for tag_id, tag_name in choices.items():
                        if tag_name == csv_value:
                            tag_ids.add(tag_id)
                            logger.debug(f"Accepted value '{csv_value}' -> tag_id {tag_id}")
                            break
                else:
                    rejected_values_for_group.append(csv_value)
                    logger.warn(f"Rejected value '{csv_value}' (not in backend choices)")

            if rejected_values_for_group:
                if group_name not in self.rejected_values:
                    self.rejected_values[group_name] = set()
                self.rejected_values[group_name].update(rejected_values_for_group)
                row_rejected_values[group_name] = rejected_values_for_group

            tagset[tag_group_id] = tag_ids

        if row_rejected_values:
            logger.debug(f"Row rejected values: {row_rejected_values}")

        return tagset

    def _create_validation_summary(self) -> str:
        """Create a summary of validation results"""
        summary_parts = []

        if self.rejected_groups:
            summary_parts.append(f"Rejected groups: {', '.join(self.rejected_groups)}")

        if self.rejected_values:
            value_parts = []
            for group_name, rejected_vals in self.rejected_values.items():
                value_parts.append(f"{group_name}: {', '.join(sorted(rejected_vals))}")
            summary_parts.append(f"Rejected values: {' | '.join(value_parts)}")

        return " • ".join(summary_parts) if summary_parts else "All groups and values are valid"

    def get_validation_results(self) -> Dict:
        """Return comprehensive validation results"""
        return {
            'rejected_groups': self.rejected_groups,
            'rejected_values': dict(self.rejected_values),
            'summary': self.validation_summary
        }
