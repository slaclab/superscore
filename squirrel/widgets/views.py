"""
Qt tree model and item classes for visualizing Entry dataclasses
"""

from __future__ import annotations

import logging
import time
from enum import Enum, IntEnum, auto
from functools import partial
from typing import Any, Callable, ClassVar, Dict, List, Optional, Union
from uuid import UUID

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from squirrel.client import Client
from squirrel.model import PV, EpicsData, Severity, Snapshot, Status
from squirrel.widgets import QtSingleton, get_window

logger = logging.getLogger(__name__)

Entry = Union[PV, Snapshot]


def add_open_page_to_menu(
    menu: QtWidgets.QMenu,
    entry: Entry,
) -> None:
    window = get_window()
    if window is None:
        logger.debug("No window instance found")
        return
    open_action = menu.addAction(
        f'&Open Detailed {type(entry).__name__} page'
    )
    # WeakPartialMethodSlot may not be needed, menus are transients
    open_action.triggered.connect(partial(window.open_page, entry))


# Entries for comparison
class DiffDispatcher(QtCore.QObject, metaclass=QtSingleton):
    """
    Singleton QObject holding a signal and up to two entries for comparison.
    Emits comparison_ready signal when selecting the second entry for comparison
    """
    comparison_ready: ClassVar[QtCore.Signal] = QtCore.Signal()
    l_entry: Optional[Entry] = None
    r_entry: Optional[Entry] = None

    def select_for_compare(self, entry: Entry) -> None:
        """Adds ``entry`` for comparison"""
        if not isinstance(entry, Entry):
            return

        self.l_entry = entry

    def compare_with_selected(self, entry: Entry) -> None:
        if self.l_entry is None:
            return

        self.r_entry = entry
        self.comparison_ready.emit()

    def reset(self) -> None:
        """Reset entries selected for diff"""
        self.l_entry = None
        self.r_entry = None


def add_comparison_actions_to_menu(menu: QtWidgets.QMenu, entry: Entry) -> None:
    """
    Add relevant comparison actions to the Menu.

    stashes the Entries to be compared in order to expose the right
    """
    ddisp = DiffDispatcher()
    # add select item (to L if both are none, to R otherwise)
    selected_uuids = [e.uuid for e in (ddisp.l_entry, ddisp.r_entry)
                      if isinstance(e, Entry)]
    if entry.uuid in selected_uuids:
        # add a dummy action
        menu.addAction("(Entry already selected for comparison)")
        reset_action = menu.addAction("Reset items selected for comparison")
        reset_action.triggered.connect(ddisp.reset)
        return

    add_l_action = menu.addAction("Select item for comparison")
    add_l_action.triggered.connect(partial(ddisp.select_for_compare, entry))

    if ddisp.l_entry is not None:
        # add compare to selected if L is None
        add_r_action = menu.addAction("Compare item with selected")
        add_r_action.triggered.connect(partial(ddisp.compare_with_selected, entry))

    if ddisp.l_entry or ddisp.r_entry:
        # add reset
        reset_action = menu.addAction("Reset items selected for comparison")
        reset_action.triggered.connect(ddisp.reset)


class MenuOption(Enum):
    """Supported options for context menus"""
    OPEN_PAGE = auto()
    DIFF = auto()


# TODO: change type hints to accurately reflect callables
MENU_OPT_ADDER_MAP: Dict[MenuOption,
                         Callable[[QtWidgets.QMenu, Entry], None]] = {
    MenuOption.OPEN_PAGE: add_open_page_to_menu,
    MenuOption.DIFF: add_comparison_actions_to_menu,
}


class CustRoles(IntEnum):
    DisplayTypeRole = QtCore.Qt.UserRole
    EpicsDataRole = auto()


class HeaderEnum(IntEnum):
    """
    Enum for more readable header names.  Underscores will be replaced with spaces
    """
    def header_name(self) -> str:
        return self.name.title().replace('_', ' ')

    @classmethod
    def from_header_name(cls, name: str) -> HeaderEnum:
        return cls[name.upper().replace(' ', '_')]


class BaseTableEntryModel(QtCore.QAbstractTableModel):
    """
    Common methods for table model that holds onto entries.
    To subclass this:
    - implement the `.data()` method and specify handling for your chosen columns
    and Qt display roles
    - define the header names
    - define any custom functionality

    Enables the editable flag for the last row for open-page-buttons

    Parameters
    ----------
    entries : Optional[List[Entry]], optional
        A list of Entry objects to display in the table, by default None

    """
    entries: List[Entry]
    headers: List[str]
    header_enum: HeaderEnum
    _editable_cols: Dict[int, bool] = {}
    _button_cols: List[HeaderEnum]
    _header_to_field: Dict[HeaderEnum, str]

    def __init__(
        self,
        *args,
        entries: Optional[List[Entry]] = None,
        **kwargs
    ) -> None:
        self.entries = entries or []
        super().__init__(*args, **kwargs)

    def rowCount(self, parent_index: Optional[QtCore.QModelIndex] = None):
        return len(self.entries)

    def columnCount(self, parent_index: Optional[QtCore.QModelIndex] = None):
        return len(self.headers)

    def set_entries(self, entries: List[Entry]):
        """
        Set the entries for this table.  Subclasses will need to override
        in order to encapsulate all logic between `layoutAboutToBeChanged` and
        `layoutChanged` signals.  (super().set_entries should not be called)
        """
        self.layoutAboutToBeChanged.emit()
        self.entries = entries
        self.layoutChanged.emit()

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.DisplayRole
    ) -> Any:
        """
        Returns the header data for the model.
        Currently only displays horizontal header data
        """
        if role != QtCore.Qt.DisplayRole:
            return

        if orientation == QtCore.Qt.Horizontal:
            return self.headers[section]

    def set_editable(self, col_index: int, editable: bool) -> None:
        """If a column is allowed to be editable, set it as editable"""
        if col_index not in self._editable_cols:
            return
        self._editable_cols[col_index] = editable

    def setData(self, index: QtCore.QModelIndex, value: Any, role: int) -> bool:
        """Set data"""
        entry = self.entries[index.row()]
        header_col = self.header_enum(index.column())
        if header_col in self._button_cols:
            # button columns do not actually set data, no-op
            return True

        header_field = self._header_to_field[header_col]
        if not hasattr(entry, header_field):
            # only set values on entries with the field
            return True

        self.layoutAboutToBeChanged.emit()
        try:
            setattr(entry, header_field, value)
            success = True
        except Exception as exc:
            logger.error(f"Failed to set data ({value}) ->"
                         f"({index.row()}, {index.column()}): {exc}")
            success = False

        self.layoutChanged.emit()
        self.dataChanged.emit(index, index)
        return success

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        """
        Returns the item flags for the given ``index``.  The returned
        item flag controls what behaviors the item supports.

        Parameters
        ----------
        index : QtCore.QModelIndex
            the index referring to a cell of the TableView

        Returns
        -------
        QtCore.Qt.ItemFlag
            the ItemFlag corresponding to the cell
        """
        if index.column() not in self._editable_cols:
            return QtCore.Qt.ItemIsEnabled

        if self._editable_cols[index.column()]:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable
        else:
            return QtCore.Qt.ItemIsEnabled

    def add_entry(self, entry: Entry) -> None:
        if entry in self.entries or not isinstance(entry, Entry):
            return

        self.layoutAboutToBeChanged.emit()
        self.entries.append[entry]
        self.layoutChanged.emit()

    def remove_row(self, row_index: int) -> None:
        self.remove_entry(self.entries[row_index])

    def remove_entry(self, entry: Entry) -> None:
        self.layoutAboutToBeChanged.emit()
        try:
            self.entries.remove(entry)
        except ValueError:
            logger.debug(f"Entry of type ({type(entry).__name__})"
                         "not found in table, could not remove.")
        self.layoutChanged.emit()


class DisplayType(Enum):
    """type of data displayed in tables"""
    PV_NAME = auto()
    STATUS = auto()
    SEVERITY = auto()
    EPICS_DATA = auto()


class LivePVHeader(HeaderEnum):
    PV_NAME = 0
    STORED_VALUE = auto()
    LIVE_VALUE = auto()
    TIMESTAMP = auto()
    STORED_STATUS = auto()
    LIVE_STATUS = auto()
    STORED_SEVERITY = auto()
    LIVE_SEVERITY = auto()
    OPEN = auto()
    REMOVE = auto()


class LivePVTableModel(BaseTableEntryModel):
    # Takes PV-entries
    # shows live details (current PV status, severity)
    # shows setpoints (can be blank)
    headers: List[str]
    _data_cache: Dict[str, EpicsData]
    _poll_thread: Optional[_PVPollThread]
    _button_cols: List[LivePVHeader] = [LivePVHeader.OPEN, LivePVHeader.REMOVE]
    _header_to_field: Dict[LivePVHeader, str] = {
        LivePVHeader.PV_NAME: 'pv_name',
        LivePVHeader.STORED_VALUE: 'data',
        LivePVHeader.STORED_STATUS: 'status',
        LivePVHeader.STORED_SEVERITY: 'severity',
    }

    def __init__(
        self,
        *args,
        client: Client,
        entries: Optional[List[PV]] = None,
        poll_period: float = 1.0,
        **kwargs
    ) -> None:
        super().__init__(*args, entries=entries, **kwargs)
        self.header_enum = LivePVHeader
        self.headers = [h.header_name() for h in LivePVHeader]

        self._editable_cols = {h.value: False for h in LivePVHeader}
        self._editable_cols[LivePVHeader.OPEN] = True
        self._editable_cols[LivePVHeader.REMOVE] = True

        self.client = client
        self.poll_period = poll_period
        self._data_cache = {e.setpoint: None for e in entries if e.setpoint} | {e.readback: None for e in entries if e.readback}
        self._poll_thread = None

        self.start_polling()

    def start_polling(self) -> None:
        """Start the polling thread"""
        """
        if self._poll_thread and self._poll_thread.isRunning():
            return

        self._poll_thread = _PVPollThread(
            data=self._data_cache,
            poll_period=self.poll_period,
            client=self.client,
            parent=self
        )
        self._data_cache = self._poll_thread.data
        self._poll_thread.data_ready.connect(self._data_ready)
        self._poll_thread.finished.connect(self._poll_thread_finished)

        self._poll_thread.start()
        """
        return

    def stop_polling(self, wait_time: float = 0.0) -> None:
        """
        stop the polling thread, and mark it as stopped.
        wait time in ms
        """
        if self._poll_thread is None or not self._poll_thread.isRunning():
            return

        logger.debug(f"stopping and de-referencing thread @ {id(self._poll_thread)}")
        # does not remove reference to avoid premature python garbage collection
        self._poll_thread.stop()
        if wait_time > 0.0:
            self._poll_thread.wait(wait_time)
        self._poll_thread.data = {}

    @QtCore.Slot()
    def _poll_thread_finished(self):
        """Slot: poll thread finished and returned."""
        if self._poll_thread is None:
            return

        self._poll_thread.data_ready.disconnect(self._data_ready)
        self._poll_thread.finished.disconnect(self._poll_thread_finished)

    @QtCore.Slot()
    def _data_ready(self) -> None:
        """
        Slot: initial indication from _DevicePollThread that the data dictionary is ready.
        """
        self.beginResetModel()
        self.endResetModel()

        if self._poll_thread is not None:
            self._poll_thread.data_changed.connect(self._data_changed)

    @QtCore.Slot(str)
    def _data_changed(self, pv_name: str) -> None:
        """
        Slot: data changed for the given attribute in the thread.
        Signals the entire row to update (a single PV worth of data)
        """
        try:
            row = list(self._data_cache).index(pv_name)
        except IndexError:
            ...
        else:
            self.dataChanged.emit(
                self.createIndex(row, 0),
                self.createIndex(row, self.columnCount()),
            )

    def set_entries(self, entries: list[PV]) -> None:
        """Set the entries for this table, reset data cache"""
        self.layoutAboutToBeChanged.emit()
        self.entries = entries
        self._data_cache = {e.setpoint: None for e in entries if e.setpoint} | {e.readback: None for e in entries if e.readback}
        # self._poll_thread.data = self._data_cache
        self.dataChanged.emit(
            self.createIndex(0, 0),
            self.createIndex(self.rowCount(), self.columnCount()),
        )
        self.layoutChanged.emit()

    def remove_entry(self, entry: PV) -> None:
        """Remove ``entry`` from the table model"""
        super().remove_entry(entry)
        self.layoutAboutToBeChanged.emit()
        self._data_cache.pop(entry.setpoint, None)
        self._data_cache.pop(entry.readback, None)
        self._poll_thread.data = self._data_cache
        self.layoutChanged.emit()

    def index_from_item(
        self,
        item: PV,
        column: Union[str, int]
    ) -> QtCore.QModelIndex:
        """
        Create an index given a `PV` and desired column.
        The column name must be an option in `LivePVHeaderEnum`, or able to be
        converted to one by swapping ' ' with '_'

        Parameters
        ----------
        item : PV
            A PV dataclass instance
        column : Union[str, int]
            A column name or column index

        Returns
        -------
        QtCore.QModelIndex
            The corresponding model index
        """
        row = self.entries.index(item)
        if isinstance(column, int):
            col = column
        elif isinstance(column, str):
            col = LivePVHeader.from_header_name(column).value
        return self.createIndex(row, col, item)

    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        """
        Returns the data stored under the given role for the item
        referred to by the index.

        UserRole provides data necessary to generate an edit delegate for the
        cell based on the data-type

        Parameters
        ----------
        index : QtCore.QModelIndex
            An index referring to a cell of the TableView
        role : int
            The requested data role.

        Returns
        -------
        Any
            the requested data
        """
        entry: PV = self.entries[index.row()]
        if isinstance(entry, UUID):
            entry = self.client.backend.get_entry(self.entries[index.row()])
            self.entries[index.row()] = entry

        if index.column() == LivePVHeader.PV_NAME:
            if role == QtCore.Qt.DecorationRole:
                return self.icon(entry)
            elif role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
                name_text = getattr(entry, 'pv_name')
                return name_text
            elif role == CustRoles.DisplayTypeRole:
                return DisplayType.PV_NAME

        if role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole,
                        QtCore.Qt.BackgroundRole, CustRoles.DisplayTypeRole,
                        CustRoles.EpicsDataRole):
            # Other parts of the table are read only
            return QtCore.QVariant()

        if index.column() == LivePVHeader.STORED_VALUE:
            if role == CustRoles.DisplayTypeRole:
                return DisplayType.EPICS_DATA
            cache_data = self.get_cache_data(entry.pv_name)
            if role == CustRoles.EpicsDataRole:
                return cache_data

            stored_data = getattr(entry, 'data', None)
            if stored_data is None:
                return '--'
            # do some enum data handling
            if isinstance(cache_data, EpicsData):
                if cache_data.enums and isinstance(stored_data, int):
                    return cache_data.enums[stored_data]
            return stored_data
        elif index.column() == LivePVHeader.LIVE_VALUE:
            live_value = self._get_live_data_field(entry, 'data')
            if role == QtCore.Qt.BackgroundRole:
                stored_data = getattr(entry, 'data', None)
                is_close = self.is_close(entry, stored_data)
                if stored_data is not None and not is_close:
                    return QtGui.QColor('red')
            return str(live_value)
        elif index.column() == LivePVHeader.TIMESTAMP:
            return entry.creation_time.strftime('%Y/%m/%d %H:%M')
        elif index.column() == LivePVHeader.STORED_STATUS:
            if role == CustRoles.DisplayTypeRole:
                return DisplayType.STATUS
            status = getattr(entry, 'status', '--')
            return getattr(status, 'name', status)
        elif index.column() == LivePVHeader.LIVE_STATUS:
            return self._get_live_data_field(entry, 'status')
        elif index.column() == LivePVHeader.STORED_SEVERITY:
            if role == CustRoles.DisplayTypeRole:
                return DisplayType.SEVERITY
            severity = getattr(entry, 'severity', '--')
            return getattr(severity, 'name', severity)
        elif index.column() == LivePVHeader.LIVE_SEVERITY:
            return self._get_live_data_field(entry, 'severity')
        elif index.column() == LivePVHeader.OPEN:
            return "Open"
        elif index.column() == LivePVHeader.REMOVE:
            return "Remove"

        # if nothing is found, return invalid QVariant
        return QtCore.QVariant()

    def _get_live_data_field(self, entry: PV, field: str) -> Any:
        """
        Helper to get field from data cache

        Parameters
        ----------
        entry : PV
            The Entry to get data from
        field : str
            The field in the EpicsData to fetch (data, status, severity, timestamp)

        Returns
        -------
        Any
            The data from EpicsData(entry.pv_name).field
        """
        live_data = self.get_cache_data(entry.setpoint)
        if not isinstance(live_data, EpicsData):
            # Data is probably fetching, return as is
            return live_data

        data_field = getattr(live_data, field)
        if isinstance(data_field, Enum):
            return str(getattr(data_field, 'name', data_field))
        elif live_data.enums and field == 'data':
            return live_data.enums[live_data.data]
        else:
            return data_field

    def is_close(self, entry: PV, data: Any) -> bool:
        """
        Determines if ``data`` is close to the value in the controls system at
        ``entry``.  Returns True if the values are close, False otherwise.
        """
        e_data = self.get_cache_data(entry.setpoint)
        if not isinstance(e_data, EpicsData):
            # data still fetching, don't compare
            return

        if hasattr(e_data, "enums") and e_data.enums and isinstance(data, int):
            # Unify enum representation
            r_data = e_data.enums[data]
            l_data = e_data.enums[e_data.data]
        else:
            r_data = data
            l_data = e_data.data

        try:
            return np.isclose(l_data, r_data)
        except TypeError:
            return l_data == r_data

    def get_cache_data(self, pv_name: str) -> Union[EpicsData, str]:
        """
        Get data from cache if possible.  If missing from cache, add pv_name for
        the polling thread to update.
        """
        data = self._data_cache.get(pv_name, None)

        if data is None:
            if pv_name not in self._data_cache:
                self._data_cache[pv_name] = None

            # TODO: A neat spinny icon maybe?
            return "fetching..."
        else:
            return data

    def close(self) -> None:
        logger.debug("Stopping pv_model polling")
        self.stop_polling(wait_time=5000)


class _PVPollThread(QtCore.QThread):
    """
    Polling thread for LivePVTableModel

    Emits ``data_changed(pv: str)`` when a pv has new data
    Parameters
    ----------
    client : squirrel.client.Client
        The client to communicate to PVs through

    data : dict[str, EpicsData]
        Per-PV EpicsData, potentially generated previously.

    poll_period : float
        The poll period in seconds (time between poll events). A zero or
        negative poll rate will indicate single-shot mode.  In "single shot"
        mode, the data is queried exactly once and then the thread exits.

    parent : QWidget, optional, keyword-only
        The parent widget.
    """
    data_ready: ClassVar[QtCore.Signal] = QtCore.Signal()
    data_changed: ClassVar[QtCore.Signal] = QtCore.Signal(str)
    running: bool

    data: Dict[str, EpicsData]
    poll_period: float

    def __init__(
        self,
        client: Client,
        data: Dict[str, EpicsData],
        poll_period: float,
        *,
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent=parent)
        self.data = data
        self.poll_period = poll_period
        self.client = client
        self.running = False
        self._attrs = set()

    def stop(self) -> None:
        """Stop the polling thread."""
        self.running = False

    def _update_data(self, pv_name):
        """
        Update the internal data cache with new data from EPICS.
        Emit self.data_changed signal if data has changed
        """
        try:
            val = self.client.cl.get(pv_name)
        except Exception as e:
            logger.warning(f'Unable to get data from {pv_name}: {e}')
            return

        # ControlLayer.get may return CommunicationError instead of raising
        if not isinstance(val, Exception) and self.data[pv_name] != val:
            self.data_changed.emit(pv_name)
            self.data[pv_name] = val

    def run(self):
        """The thread polling loop."""
        self.running = True

        self.data_ready.emit()

        while self.running:
            t0 = time.monotonic()
            for pv_name in self.data:
                self._update_data(pv_name)
                if not self.running:
                    break
                time.sleep(0)

            if self.poll_period <= 0.0:
                # A zero or below means "single shot" updates.
                break

            elapsed = time.monotonic() - t0
            time.sleep(max((0, self.poll_period - elapsed)))


class ButtonDelegate(QtWidgets.QStyledItemDelegate):
    clicked = QtCore.Signal(QtCore.QModelIndex)

    def __init__(self, *args, button_text: str = '', **kwargs):
        self.button_text = button_text
        super().__init__(*args, **kwargs)

    def createEditor(
        self,
        parent: QtWidgets.QWidget,
        option,
        index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        button = QtWidgets.QPushButton(self.button_text, parent)
        button.clicked.connect(
            lambda _, index=index: self.clicked.emit(index)
        )
        return button

    def updateEditorGeometry(
        self,
        editor: QtWidgets.QWidget,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex
    ) -> None:
        return editor.setGeometry(option.rect)


class ValueDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def createEditor(
        self,
        parent: QtWidgets.QWidget,
        option,
        index: QtCore.QModelIndex
    ) -> QtWidgets.QWidget:
        dtype: DisplayType = index.model().data(
            index, role=CustRoles.DisplayTypeRole
        )
        data_val = index.model().data(index, role=QtCore.Qt.DisplayRole)
        if dtype == DisplayType.PV_NAME:
            widget = QtWidgets.QLineEdit(data_val, parent)
        elif dtype == DisplayType.SEVERITY:
            widget = QtWidgets.QComboBox(parent)
            widget.addItems([sev.name for sev in Severity])
        elif dtype == DisplayType.STATUS:
            widget = QtWidgets.QComboBox(parent)
            widget.addItems([sta.name for sta in Status])
        elif dtype == DisplayType.EPICS_DATA:
            # need to fetch data for this PV, not stored data
            data_val: EpicsData = index.model().data(
                index, role=CustRoles.EpicsDataRole
            )
            if not isinstance(data_val, EpicsData):
                # not yet initialized, no-op
                return
            widget = edit_widget_from_epics_data(data_val, parent)
        else:
            logger.debug(f"datatype ({dtype}) incompatible with supported edit "
                         f"widgets: ({data_val})")
            return
        return widget

    def setModelData(
        self,
        editor: QtWidgets.QWidget,
        model: QtCore.QAbstractItemModel,
        index: QtCore.QModelIndex
    ) -> None:
        if isinstance(editor, QtWidgets.QAbstractSpinBox):
            val = editor.value()
        elif isinstance(editor, QtWidgets.QLineEdit):
            val = editor.text()
        elif isinstance(editor, QtWidgets.QComboBox):
            val = editor.currentIndex()

            dtype: DisplayType = model.data(
                index, role=CustRoles.DisplayTypeRole
            )

            if dtype == DisplayType.STATUS:
                val = Status(val)
            elif dtype == DisplayType.SEVERITY:
                val = Severity(val)
        else:
            return
        model.setData(index, val, QtCore.Qt.EditRole)

    def updateEditorGeometry(
        self,
        editor: QtWidgets.QWidget,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex
    ) -> None:
        return editor.setGeometry(option.rect)


def edit_widget_from_epics_data(
    edata: EpicsData,
    parent_widget: Optional[QtWidgets.QWidget] = None
) -> QtWidgets.QWidget:
    """
    Returns the appropriate edit widget given an EpicsData instance. Supported
    data types include:
    - string -> QLineEdit
    - integer -> QSpinBox
    - float -> QDoubleSpinBox
    - enum -> QComboBox

    When applicable, limits and enum options will be applied

    Parameters
    ----------
    edata : EpicsData
        Data to return an appropriate edit widget for
    parent_widget : QtWidgets.QWidget
        parent widget to assign to the edit widget

    Returns
    -------
    QtWidgets.QWidget
        The edit widget
    """
    if isinstance(edata.data, str):
        widget = QtWidgets.QLineEdit(edata.data, parent_widget)
    elif edata.enums:  # Catch enums before numerics, enums are ints
        widget = QtWidgets.QComboBox(parent_widget)
        widget.addItems(edata.enums)
        widget.setCurrentIndex(edata.data)
    elif isinstance(edata.data, int):
        widget = QtWidgets.QSpinBox(parent_widget)
        if edata.lower_ctrl_limit == 0 and edata.upper_ctrl_limit == 0:
            widget.setMaximum(2147483647)
            widget.setMinimum(-2147483647)
        else:
            widget.setMaximum(edata.upper_ctrl_limit)
            widget.setMinimum(edata.lower_ctrl_limit)
        widget.setValue(edata.data)
    elif isinstance(edata.data, float):
        widget = QtWidgets.QDoubleSpinBox(parent_widget)
        if edata.lower_ctrl_limit == 0 and edata.upper_ctrl_limit == 0:
            widget.setMaximum(2147483647)
            widget.setMinimum(-2147483647)
        else:
            widget.setMaximum(edata.upper_ctrl_limit)
            widget.setMinimum(edata.lower_ctrl_limit)
        widget.setDecimals(edata.precision)
        widget.setValue(edata.data)
    else:
        raise ValueError(f"data type ({edata}) not supported ")

    return widget
