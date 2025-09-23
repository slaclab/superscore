from enum import Enum, auto
from typing import Any
from uuid import UUID

import numpy as np
from qtpy import QtCore, QtGui

import squirrel.color
from squirrel.widgets import SEVERITY_ICONS

NO_DATA = "--"


class COMPARE_HEADER(Enum):
    CHECKBOX = 0
    SEVERITY = auto()
    COMPARE_SEVERITY = auto()
    DEVICE = auto()
    PV = auto()
    SETPOINT = auto()
    COMPARE_SETPOINT = auto()
    READBACK = auto()
    COMPARE_READBACK = auto()

    def display_string(self) -> str:
        return self._strings[self]

    def is_compare_column(self) -> bool:
        return self in (self.COMPARE_SEVERITY, self.COMPARE_SETPOINT,
                        self.COMPARE_READBACK)


COMPARE_HEADER._strings = {
    COMPARE_HEADER.CHECKBOX: "",
    COMPARE_HEADER.SEVERITY: "Severity",
    COMPARE_HEADER.COMPARE_SEVERITY: "Comparison Severity",
    COMPARE_HEADER.DEVICE: "Device",
    COMPARE_HEADER.PV: "PV Name",
    COMPARE_HEADER.SETPOINT: "Saved Value",
    COMPARE_HEADER.COMPARE_SETPOINT: "Comparison Value",
    COMPARE_HEADER.READBACK: "Saved Readback",
    COMPARE_HEADER.COMPARE_READBACK: "Comparison Readback",
}


class SnapshotComparisonTableModel(QtCore.QAbstractTableModel):
    """
    A table model for representing PV data within a Snapshot. Includes live data and checkboxes
    for selecting rows.
    """
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self._data = []
        self._checked = set()

        self.main_snapshot = None
        self.comparison_snapshot = None

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(COMPARE_HEADER)

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ) -> str:
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                return COMPARE_HEADER(section).display_string()
        return None

    def flags(self, index) -> QtCore.Qt.ItemFlags:
        column = COMPARE_HEADER(index.column())
        if column == COMPARE_HEADER.CHECKBOX:
            return QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
        else:
            return super().flags(index)

    def data(
        self,
        index: QtCore.QModelIndex,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ):
        column = COMPARE_HEADER(index.column())
        is_compare_column = column.is_compare_column()

        # Get the entry and compare objects, swapping them if necessary
        entry, compare = self._data[index.row()]
        if is_compare_column:
            entry, compare = compare, entry

        # Handle different roles
        if role == QtCore.Qt.TextAlignmentRole:
            if column not in (COMPARE_HEADER.DEVICE, COMPARE_HEADER.PV):
                return QtCore.Qt.AlignCenter
        elif role == QtCore.Qt.CheckStateRole:
            if column == COMPARE_HEADER.CHECKBOX:
                return QtCore.Qt.Checked if index.row() in self._checked else QtCore.Qt.Unchecked
        elif role == QtCore.Qt.BackgroundRole:
            if column == COMPARE_HEADER.COMPARE_SETPOINT:
                try:
                    is_close = np.isclose(entry.setpoint_data.data, compare.setpoint_data.data)
                except AttributeError:
                    return None
                except TypeError:
                    is_close = entry.setpoint_data.data == compare.setpoint_data.data
                if compare.setpoint_data.data is not None and not is_close:
                    return QtGui.QColor(squirrel.color.RED)
            elif column == COMPARE_HEADER.COMPARE_READBACK:
                try:
                    is_close = np.isclose(entry.readback_data.data, compare.readback_data.data)
                except TypeError:
                    is_close = entry.readback_data.data == compare.readback_data.data
                except AttributeError:
                    return None
                if compare.readback_data.data is not None and not is_close:
                    return QtGui.QColor(squirrel.color.RED)
        elif role == QtCore.Qt.ToolTipRole:
            if column in [COMPARE_HEADER.PV, COMPARE_HEADER.SETPOINT, COMPARE_HEADER.COMPARE_SETPOINT]:
                try:
                    return entry.setpoint
                except AttributeError:
                    return compare.setpoint
            elif column in [COMPARE_HEADER.READBACK, COMPARE_HEADER.COMPARE_READBACK]:
                try:
                    return entry.readback
                except AttributeError:
                    return compare.readback
        elif role == QtCore.Qt.DecorationRole:
            if column in (COMPARE_HEADER.SEVERITY, COMPARE_HEADER.COMPARE_SEVERITY):
                if entry is None:
                    return None
                icon = SEVERITY_ICONS[entry.severity]
                if icon is None:
                    icon = SEVERITY_ICONS[entry.status]
                return icon
        elif role == QtCore.Qt.DisplayRole:
            try:
                if column in (COMPARE_HEADER.SEVERITY, COMPARE_HEADER.COMPARE_SEVERITY):
                    # Return NO_DATA if only one entry is present
                    if entry is None:
                        return NO_DATA
                elif column == COMPARE_HEADER.DEVICE:
                    return NO_DATA
                elif column == COMPARE_HEADER.PV:
                    return entry.setpoint if entry else compare.setpoint
                elif column in (COMPARE_HEADER.SETPOINT, COMPARE_HEADER.COMPARE_SETPOINT):
                    return entry.setpoint_data.data
                elif column in (COMPARE_HEADER.READBACK, COMPARE_HEADER.COMPARE_READBACK):
                    return entry.readback_data.data
            except AttributeError:
                return NO_DATA
        # Default case
        return None

    def setData(self, index: QtCore.QModelIndex, value: Any, role: QtCore.Qt.ItemDataRole) -> bool:
        """Set the data for a given index. Only checkboxes are editable."""
        column = COMPARE_HEADER(index.column())
        if role == QtCore.Qt.CheckStateRole and column == COMPARE_HEADER.CHECKBOX:
            if value == QtCore.Qt.Checked:
                self._checked.add(index.row())
            elif value == QtCore.Qt.Unchecked:
                self._checked.remove(index.row())
            self.dataChanged.emit(index, index)
        return True

    def ready_for_comparison(self) -> bool:
        """Check if the model is ready for comparison."""
        has_main = self.main_snapshot is not None
        has_comp = self.comparison_snapshot is not None
        main_is_comp = self.main_snapshot == self.comparison_snapshot
        return has_main and has_comp and not main_is_comp

    def collate_pvs(self) -> None:
        """Get all PVs for the snapshots to be compared."""
        if not self.ready_for_comparison():
            return

        self.beginResetModel()
        self._data = []
        pvs = self.client.backend.get_snapshots(uuid=self.comparison_snapshot.uuid).pvs
        secondary_pvs = {(pv.setpoint, pv.readback): pv for pv in tuple(pvs)}
        # for each PV in primary snapshot, find partner in secondary snapshot
        pvs = self.client.backend.get_snapshots(uuid=self.main_snapshot.uuid).pvs
        for primary in tuple(pvs):
            secondary = secondary_pvs.pop((primary.setpoint, primary.readback), None)
            self._data.append((primary, secondary))
        # for each PV in secondary with no partner in primary, add row with 'None' partner
        for secondary in secondary_pvs.values():
            self._data.append((None, secondary))
        self.endResetModel()

    def set_main_snapshot(self, main_snapshot: UUID) -> None:
        """Set the main snapshot and update the model."""
        self.main_snapshot = main_snapshot
        self.collate_pvs()

    def set_comparison_snapshot(self, comparison_snapshot: UUID) -> None:
        """Set the comparison snapshot and update the model."""
        self.comparison_snapshot = comparison_snapshot
        self.collate_pvs()
