"""
Qt tree model and item classes for visualizing Entry dataclasses
"""

from __future__ import annotations

import logging
import time
from enum import Enum, IntEnum, auto
from functools import partial
from typing import (Any, Callable, ClassVar, Dict, Generator, List, Optional,
                    Union)
from uuid import UUID
from weakref import WeakValueDictionary

import numpy as np
import qtawesome as qta
from qtpy import QtCore, QtGui, QtWidgets

from superscore.backends.core import SearchTerm
from superscore.client import Client
from superscore.control_layers import EpicsData
from superscore.errors import EntryNotFoundError
from superscore.model import (Collection, Entry, Nestable, Parameter, Readback,
                              Root, Setpoint, Severity, Snapshot, Status)
from superscore.qt_helpers import QDataclassBridge
from superscore.widgets import ICON_MAP, get_window
from superscore.widgets.core import QtSingleton, WindowLinker

logger = logging.getLogger(__name__)


PVEntry = Union[Parameter, Setpoint, Readback]


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


class EntryItem:
    """Node representing one Entry"""
    _bridge_cache: ClassVar[
        WeakValueDictionary[int, QDataclassBridge]
    ] = WeakValueDictionary()
    bridge: QDataclassBridge
    _data: Entry

    def __init__(
        self,
        data: Entry,
        tree_parent: Optional[EntryItem] = None,
    ):
        self._data = data
        self._parent = None
        self._columncount = 2
        # Consider making children a property that looks at underlying data
        self._children: List[EntryItem] = []
        self._parent = None
        self._row = 0  # (self._row)th child of this item's parent
        if tree_parent:
            tree_parent.addChild(self)

        # Assign bridge, for updating the entry properties when data changes?
        # For this to be relevant we need to subscribe to the bridge,
        # for example to change icons on type update
        if self._data:
            try:
                self.bridge = self._bridge_cache[id(data)]
            except KeyError:
                bridge = QDataclassBridge(data)
                self._bridge_cache[id(data)] = bridge
                self.bridge = bridge

    def fill_uuids(
        self,
        client: Optional[Client] = None,
        fill_depth: int = 2
    ) -> None:
        """
        Fill this item's data if it is a uuid, using ``client``.
        By default fills to a depth of 2, to keep the tree view data loading lazy
        """
        if client is None:
            return

        if isinstance(self._data, UUID):
            search_results = client.search(SearchTerm('uuid', 'eq', self._data))
            self._data = list(search_results)[0]

        if isinstance(self._data, Nestable):
            if any(isinstance(child, UUID) for child in self._data.children):
                client.fill(self._data, fill_depth=fill_depth)

            # re-construct child EntryItems if there is a mismatch or if any
            # hold UUIDs as _data
            if (any(isinstance(e._data, UUID) for e in self._children)
                    or len(self._data.children) != self.childCount()):
                self.takeChildren()
                for child in self._data.children:
                    logger.debug(f'adding filled child: {type(child)}({child.uuid})')
                    build_tree(child, parent=self)

    def data(self, column: int) -> Any:
        """
        Return the data for the requested column.
        Column 0: name
        Column 1: description

        Parameters
        ----------
        column : int
            data column requested

        Returns
        -------
        Any
        """
        if self._data is None:
            # This should never be seen
            return '<root>'

        if column == 0:
            if isinstance(self._data, Nestable):
                return getattr(self._data, 'title', 'root')
            else:
                return getattr(self._data, 'pv_name', '<no pv>')
        elif column == 1:
            return getattr(self._data, 'description', '<no desc>')

        # TODO: something about icons

    def tooltip(self) -> str:
        """Construct the tooltip based on the stored entry"""
        return self._data.uuid

    def columnCount(self) -> int:
        """Return the item's column count"""
        return self._columncount

    def childCount(self) -> int:
        """Return the item's child count"""
        return len(self._children)

    def child(self, row: int) -> EntryItem:
        """Return the item's child"""
        if row >= 0 and row < self.childCount():
            return self._children[row]

    def get_children(self) -> Generator[EntryItem, None, None]:
        """Yield this item's children"""
        yield from self._children

    def parent(self) -> EntryItem:
        """Return the item's parent"""
        return self._parent

    def row(self) -> int:
        """Return the item's row under its parent"""
        return self._row

    def addChild(self, child: EntryItem) -> None:
        """
        Add a child to this item.

        Parameters
        ----------
        child : EntryItem
            Child EntryItem to add to this EntryItem
        """
        child._parent = self
        child._row = len(self._children)
        self._children.append(child)

    def removeChild(self, child: EntryItem) -> None:
        """Remove ``child`` from this EntryItem"""
        try:
            self._children.remove(child)
        except ValueError:
            logger.debug(f"EntryItem ({child}) is not a child of this parent ({self})")
            return
        child._parent = None
        # re-assign rows to children
        remaining_children = self.takeChildren()
        for rchild in remaining_children:
            self.addChild(rchild)

    def replaceChild(self, old_child: EntryItem, new_child: EntryItem) -> None:
        """Replace ``old_child`` with ``new_child``, maintaining order"""
        for idx in range(self.childCount()):
            if self.child(idx) is old_child:
                self._children[idx] = new_child
                new_child._parent = self
                new_child._row = idx

                # dereference old_child
                old_child._parent = None
                return

        raise IndexError('old child not found, could not replace')

    def takeChild(self, idx: int) -> EntryItem:
        """Remove and return the ``idx``-th child of this item"""
        child = self._children.pop(idx)
        child._parent = None
        # re-assign rows to children
        remaining_children = self.takeChildren()
        for rchild in remaining_children:
            self.addChild(rchild)

        return child

    def insertChild(self, idx: int, child: EntryItem) -> None:
        """Add ``child`` to this EntryItem at index ``idx``"""
        self._children.insert(idx, child)
        # re-assign rows to children
        remaining_children = self.takeChildren()
        for rchild in remaining_children:
            self.addChild(rchild)

    def takeChildren(self) -> list[EntryItem]:
        """
        Remove and return this item's children
        """
        children = self._children
        self._children = []
        for child in children:
            child._parent = None

        return children

    def icon(self):
        """return icon for this item"""
        icon_id = ICON_MAP.get(type(self._data), None)
        if icon_id is None:
            return
        return qta.icon(icon_id)


def build_tree(
    entry: Union[Entry, Root, UUID],
    parent: Optional[EntryItem] = None
) -> EntryItem:
    """
    Walk down the ``entry`` tree and create an `EntryItem` for each, linking
    them to their parents.

    Parameters
    ----------
    entry : Entry
        the top-level item to start with

    parent : EntryItem, optional
        the parent `EntryItem` of ``entry``

    Returns
    -------
    EntryItem
        the constructed `EntryItem` with parent-child linkages
    """
    # Note the base case here is when ``entry`` is a UUID, in which an EntryItem
    # is made and recursion stops.  These children need to be present to let the
    # view know that there are children in the item (that will later be filled)

    item = EntryItem(entry, tree_parent=parent)
    if isinstance(entry, Root):
        for child in entry.entries:
            build_tree(child, parent=item)
    elif isinstance(entry, Nestable):
        for child in entry.children:
            build_tree(child, parent=item)

    return item


class RootTree(QtCore.QAbstractItemModel):
    """
    Item model for the database tree-view.
    This model will query the client for entry information.
    Attempts to be lazy with its representation, only querying data when necessary.
    This model should only care about the metadata and structure of the Entry's
    it displays, not the contents (pv-names, values, links, etc)

    This model will be as lazy as the Client allows.  If the client can provide
    uuid-ified entries, this model can be modified to be more performant / lazy

    The base implementation likely does none of this
    """
    def __init__(
        self,
        *args,
        base_entry: Entry,
        client: Optional[Client] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.base_entry = base_entry
        self.root_item = build_tree(base_entry)
        self.client = client
        # ensure at least the first set of children are filled
        self.root_item.fill_uuids(self.client)
        self.headers = ['name', 'description']

    def refresh_tree(self) -> None:
        self.layoutAboutToBeChanged.emit()
        self.root_item = build_tree(self.base_entry)
        self.layoutChanged.emit()

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int
    ) -> Any:
        """
        Returns the header data for the model.
        Currently only displays horizontal header data

        Parameters
        ----------
        section : int
            section to provide header information for
        orientation : Qt.Orientation
            header orientation, Qt.Horizontal or Qt.Vertical
        role : int
            Qt role to provide header information for

        Returns
        -------
        Any
            requested header data
        """
        if role != QtCore.Qt.DisplayRole:
            return

        if orientation == QtCore.Qt.Horizontal:
            return self.headers[section]

    def index(
        self,
        row: int,
        column: int,
        parent: QtCore.QModelIndex = QtCore.QModelIndex()
    ) -> QtCore.QModelIndex:
        """
        Returns the index of the item in the model.

        In a tree view the rows are defined relative to parent item.  If an
        item is the first child under its parent, it will have row=0,
        regardless of the number of items in the tree.

        Parameters
        ----------
        row : int
            The row of the requested index.
        column : int
            The column of the requested index
        parent : QtCore.QModelIndex, optional
            The parent of the requested index, by default None

        Returns
        -------
        QtCore.QModelIndex
        """
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        parent_item = None
        if not parent or not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)

        # all else return invalid index
        return QtCore.QModelIndex()

    def index_from_item(self, item: EntryItem) -> QtCore.QModelIndex:
        return self.createIndex(item.row(), 0, item)

    def parent(self, index: QtCore.QModelIndex) -> QtCore.QModelIndex:
        """

        Parameters
        ----------
        index : QtCore.QModelIndex
            item to retrieve parent of

        Returns
        -------
        QtCore.QModelIndex
            index of the parent item
        """
        if not index.isValid():
            return QtCore.QModelIndex()
        child = index.internalPointer()
        if child is self.root_item:
            return QtCore.QModelIndex()
        parent = child.parent()
        if parent in (self.root_item, None):
            return QtCore.QModelIndex()

        return self.createIndex(parent.row(), 0, parent)

    def rowCount(self, parent: QtCore.QModelIndex) -> int:
        """
        Called by tree view to determine number of children an item has.

        Parameters
        ----------
        parent : QtCore.QModelIndex
            index of the parent item being queried

        Returns
        -------
        int
            number of children ``parent`` has
        """
        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()
        return parent_item.childCount()

    def columnCount(self, parent: QtCore.QModelIndex) -> int:
        """
        Called by tree view to determine number of columns of data ``parent`` has

        Parameters
        ----------
        parent : QtCore.QModelIndex

        Returns
        -------
        int
            number of columns ``parent`` has
        """
        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()
        return parent_item.columnCount()

    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        """
        Returns the data stored under the given ``role`` for the item
        referred to by the ``index``.  Uses and assumes ``EntryItem`` methods.

        Parameters
        ----------
        index : QtCore.QModelIndex
            index that identifies the portion of the model in question
        role : int
            the data role

        Returns
        -------
        Any
            The data to be displayed by the model
        """
        if not index.isValid():
            return None

        item: EntryItem = index.internalPointer()  # Gives original EntryItem

        # special handling for status info
        if index.column() == 1:
            if role == QtCore.Qt.DisplayRole:
                return item.data(1)
            if role == QtCore.Qt.TextAlignmentRole:
                return QtCore.Qt.AlignLeft

        if role == QtCore.Qt.ToolTipRole:
            return item.tooltip()
        if role == QtCore.Qt.DisplayRole:
            return item.data(index.column())

        if role == CustRoles.DisplayTypeRole:
            return item

        if role == QtCore.Qt.DecorationRole and index.column() == 0:
            return item.icon()

        return None

    def canFetchMore(self, parent: QtCore.QModelIndex) -> bool:
        item: EntryItem = parent.internalPointer()
        if item is None:
            return False

        data = item._data

        # Root should never need to be fetched, since we fill to depth
        # of 2 when we initialize the tree, and root is always at depth 0 if
        # present
        if isinstance(data, Nestable):
            if (
                any(isinstance(dc_child, UUID) for dc_child in data.children)
                or any(isinstance(ei_child._data, UUID) for ei_child
                       in item._children)
            ):
                return True

        return False

    def fetchMore(self, parent: QtCore.QModelIndex) -> None:
        item: EntryItem = parent.internalPointer()
        item.fill_uuids(client=self.client)

        num_children = item.childCount()
        self.beginInsertRows(parent, 0, num_children)
        self.endInsertRows()


class RootTreeView(QtWidgets.QTreeView, WindowLinker):
    """
    Tree view for displaying an Entry.
    Contains a standard context menu and action set
    """
    _model_cls = RootTree

    _model: Optional[RootTree] = None
    data_updated: ClassVar[QtCore.Signal] = QtCore.Signal()

    context_menu_options: Dict[MenuOption, bool] = {
        MenuOption.OPEN_PAGE: True,
        MenuOption.DIFF: True,
    }

    def __init__(
        self,
        *args,
        client: Optional[Client] = None,
        entry: Optional[Entry] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._client = client
        self.data = entry

        self.setup_ui()

    def setup_ui(self) -> None:
        # Configure basic settings
        self.maybe_setup_model()

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._tree_context_menu)
        self.setExpandsOnDoubleClick(False)
        self.doubleClicked.connect(self.open_index)

    @WindowLinker.client.setter
    def client(self, client: Client):
        if not isinstance(client, Client):
            raise TypeError(f"Cannot set a {type(client)} as a client")

        if client is self._client:
            return

        if not isinstance(client, Client):
            raise ValueError("Provided client is not a superscore Client")

        self._client = client
        self.maybe_setup_model()

    def set_data(self, data: Any):
        """Set the data for this view, re-setup ui"""
        if not isinstance(data, (Root, Entry)):
            raise ValueError(
                f"Attempted to set an incompatable data type ({type(data)})"
            )
        self.data = data
        self.maybe_setup_model()

    def maybe_setup_model(self):
        if self.client is None:
            logger.debug("Client not set, cannot initialize model")
            return

        if self.data is None:
            logger.debug("data not set, cannot initialize model")
            return

        self._model = self._model_cls(base_entry=self.data, client=self.client)
        self.setModel(self._model)
        self._model.dataChanged.connect(self.data_updated)

        self.data_updated.emit()

    def _tree_context_menu(self, pos: QtCore.QPoint) -> None:
        index: QtCore.QModelIndex = self.indexAt(pos)
        if index is not None and index.data() is not None:
            entry: Entry = index.internalPointer()._data
            menu = self.create_context_menu(entry)

            menu.exec_(self.mapToGlobal(pos))

    def create_context_menu(self, entry: Entry) -> QtWidgets.QMenu:
        """
        Default method for creating the context menu.
        Overload/replace this method if you would like to change this behavior
        """
        menu = QtWidgets.QMenu(self)

        # checking if window exists to attach open_page_slot to
        if self.context_menu_options[MenuOption.OPEN_PAGE]:
            MENU_OPT_ADDER_MAP[MenuOption.OPEN_PAGE](menu, entry)

        menu.addSeparator()

        if self.context_menu_options[MenuOption.DIFF]:
            MENU_OPT_ADDER_MAP[MenuOption.DIFF](menu, entry)

        return menu

    def open_index(self, index: QtCore.QModelIndex) -> None:
        entry: Entry = index.internalPointer()._data
        self.open_page(entry)

    def open_page(self, entry):
        """Simple wrapper around the open page slot"""
        if self.open_page_slot is not None:
            self.open_page_slot(entry)


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

    def icon(self, entry: Entry) -> Optional[QtGui.QIcon]:
        """return icon for this ``entry``"""
        icon_id = ICON_MAP.get(type(entry), None)
        if icon_id is None:
            return
        return qta.icon(icon_id)


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
        entries: Optional[List[PVEntry]] = None,
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
        self._data_cache = {e.pv_name: None for e in entries}
        self._poll_thread = None

        self.start_polling()

    def start_polling(self) -> None:
        """Start the polling thread"""
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

    def set_entries(self, entries: list[PVEntry]) -> None:
        """Set the entries for this table, reset data cache"""
        self.layoutAboutToBeChanged.emit()
        self.entries = entries
        self._data_cache = {e.pv_name: None for e in entries}
        self._poll_thread.data = self._data_cache
        self.dataChanged.emit(
            self.createIndex(0, 0),
            self.createIndex(self.rowCount(), self.columnCount()),
        )
        self.layoutChanged.emit()

    def remove_entry(self, entry: PVEntry) -> None:
        """Remove ``entry`` from the table model"""
        super().remove_entry(entry)
        self.layoutAboutToBeChanged.emit()
        self._data_cache = {e.pv_name: None for e in self.entries}
        self._poll_thread.data = self._data_cache
        self.layoutChanged.emit()

    def index_from_item(
        self,
        item: PVEntry,
        column: Union[str, int]
    ) -> QtCore.QModelIndex:
        """
        Create an index given a `PVEntry` and desired column.
        The column name must be an option in `LivePVHeaderEnum`, or able to be
        converted to one by swapping ' ' with '_'

        Parameters
        ----------
        item : PVEntry
            A PVEntry dataclass instance
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
        entry: PVEntry = self.entries[index.row()]
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

    def _get_live_data_field(self, entry: PVEntry, field: str) -> Any:
        """
        Helper to get field from data cache

        Parameters
        ----------
        entry : PVEntry
            The Entry to get data from
        field : str
            The field in the EpicsData to fetch (data, status, severity, timestamp)

        Returns
        -------
        Any
            The data from EpicsData(entry.pv_name).field
        """
        live_data = self.get_cache_data(entry.pv_name)
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

    def is_close(self, entry: PVEntry, data: Any) -> bool:
        """
        Determines if ``data`` is close to the value in the controls system at
        ``entry``.  Returns True if the values are close, False otherwise.
        """
        e_data = self.get_cache_data(entry.pv_name)
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
    client : superscore.client.Client
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


class BaseDataTableView(QtWidgets.QTableView, WindowLinker):
    """
    Base TableView for holding and manipulating an entry / list of entries
    """
    # signal indicating the contained has been updated
    data_updated: ClassVar[QtCore.Signal] = QtCore.Signal()
    _model: Optional[Union[LivePVTableModel, NestableTableModel]] = None
    _model_cls: Union[LivePVTableModel, NestableTableModel] = LivePVTableModel
    open_column: int = 0
    remove_column: int = 0

    context_menu_options: Dict[MenuOption, bool] = {
        MenuOption.OPEN_PAGE: True,
        MenuOption.DIFF: True,
    }

    def __init__(
        self,
        *args,
        data: Optional[Union[Entry, List[Entry]]] = None,
        **kwargs,
    ) -> None:
        """need to set open_column, close_column in subclass"""
        super().__init__(*args, **kwargs)
        self.data = data
        self.sub_entries = []
        self.model_kwargs = {}

        # only these for now, may need an update later
        self.setup_ui()

    def setup_ui(self):
        """initialize basic ui elements for this table"""
        # set delegates
        self.open_delegate = ButtonDelegate(button_text='open details')
        self.setItemDelegateForColumn(self.open_column, self.open_delegate)
        self.open_delegate.clicked.connect(self.open_row_details)

        self.remove_delegate = ButtonDelegate(button_text='remove')
        self.setItemDelegateForColumn(self.remove_column, self.remove_delegate)
        self.remove_delegate.clicked.connect(self.remove_row)

        # set context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.create_context_menu_at_pos)

    def open_row_details(self, index: QtCore.QModelIndex) -> None:
        """slot for opening row details page"""
        if self.open_page_slot:
            entry = self._model.entries[index.row()]
            self.open_page_slot(entry)

    def remove_row(self, index: QtCore.QModelIndex) -> None:
        entry = self._model.entries[index.row()]
        self._model.remove_row(index.row())

        if isinstance(self.data, list):
            self.data.remove(entry)
        elif isinstance(self.data, Nestable):
            self.data.children.remove(entry)
        # edit data held by widget
        self.data_updated.emit()

    def set_data(self, data: Any):
        """Set the data for this view, re-setup ui"""
        if not isinstance(data, (list, Entry)):
            raise ValueError(
                f"Attempted to set an incompatable data type ({type(data)})"
            )
        self.data = data
        self.maybe_setup_model()

    def maybe_setup_model(self):
        """
        Set up the model if data and client are set
        """
        if self.client is None:
            logger.debug("Client not set, cannot initialize model")
            return

        if self.data is None:
            logger.debug("data not set, cannot initialize model")
            return

        self.gather_sub_entries()

        if self._model is None:
            self._model = self._model_cls(
                client=self.client,
                entries=self.sub_entries,
                **self.model_kwargs
            )
            self.setModel(self._model)
            self._model.dataChanged.connect(self.data_updated)
        else:
            self._model.set_entries(self.sub_entries)

        self.data_updated.emit()

    def gather_sub_entries(self):
        """
        Gather entries relevant to the contained model
        and assign to self.sub_entries.  This must be implemented in a subclass.
        """
        raise NotImplementedError

    @WindowLinker.client.setter
    def client(self, client: Client):
        self._set_client(client)

    def _set_client(self, client: Client):
        if not isinstance(client, Client):
            raise TypeError(f"Cannot set a {type(client)} as a client")

        if client is self._client:
            return

        if not isinstance(client, Client):
            raise ValueError("Provided client is not a superscore Client")

        self._client = client
        self.maybe_setup_model()

    def set_editable(self, column: int, is_editable: bool) -> None:
        if not self._model:
            return
        self._model.set_editable(column, is_editable)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MiddleButton:
            index = self.indexAt(event.position().toPoint())
            text = self._model.data(index, QtCore.Qt.DisplayRole)
            clipboard = QtWidgets.QApplication.clipboard()
            if clipboard.supportsSelection():
                mode = clipboard.Selection
            else:
                mode = clipboard.Clipboard
            clipboard.setText(text, mode=mode)
            clipboard.setText(text)
        super().mousePressEvent(event)

    def create_context_menu_at_pos(self, pos: QtCore.QPoint) -> None:
        index: QtCore.QModelIndex = self.indexAt(pos)
        if index is not None and index.data() is not None:
            entry = self._model.entries[index.row()]
            menu = self.create_context_menu(entry)

            menu.exec_(self.mapToGlobal(pos))

    def create_context_menu(self, entry: Entry) -> QtWidgets.QMenu:
        """
        Default method for creating the context menu.
        Overload/replace this method if you would like to change this behavior
        """
        menu = QtWidgets.QMenu(self)
        if self.context_menu_options[MenuOption.OPEN_PAGE]:
            MENU_OPT_ADDER_MAP[MenuOption.OPEN_PAGE](menu, entry)

        menu.addSeparator()

        if self.context_menu_options[MenuOption.DIFF]:
            MENU_OPT_ADDER_MAP[MenuOption.DIFF](menu, entry)

        return menu


class LivePVTableView(BaseDataTableView):
    """
    table widget for LivePVTableModel.  Meant to provide a standard, easy-to-use
    interface for this table model, with common configuration options exposed

    compatible with list of entries or full entry
        - updates entry when changes made
        - maintains order for rebuilding of parent collections
    Configures delegates, ignoring open page slot if provided

    TO-DO:
    Column manipulation
        - re-order
    flattening of base data
        - handling of readbacks associated with base entries?
        - handling of nested nestables
    ediable stored fields if desired, updating entry
    """
    _model: Optional[LivePVTableModel]

    def __init__(self, *args, poll_period: float = 1.0, **kwargs):
        self._model_cls = LivePVTableModel
        self.open_column = LivePVHeader.OPEN
        self.remove_column = LivePVHeader.REMOVE
        super().__init__(*args, **kwargs)

        self.model_kwargs['poll_period'] = poll_period

        self.value_delegate = ValueDelegate()
        for col in [LivePVHeader.PV_NAME, LivePVHeader.STORED_VALUE,
                    LivePVHeader.STORED_STATUS, LivePVHeader.STORED_SEVERITY]:
            self.setItemDelegateForColumn(col, self.value_delegate)

    def gather_sub_entries(self):
        if isinstance(self.data, UUID):
            self.data = self.client.backend.get_entry(self.data)

        if isinstance(self.data, Nestable):
            # gather sub_nestables
            self.sub_entries = []
            for i, child in enumerate(self.data.children):
                if isinstance(child, UUID):
                    child = self._client.backend.get_entry(child)
                    self.data.children[i] = child
                else:
                    child = child

                if child is None:
                    raise EntryNotFoundError(f"{child} not found in backend, "
                                             "cannot fill with real data")

                if not isinstance(child, Nestable) and isinstance(child, Entry):
                    self.sub_entries.append(child)

        elif isinstance(self.data, (Parameter, Setpoint, Readback)):
            self.sub_entries = [self.data]

    @BaseDataTableView.client.setter
    def client(self, client: Optional[Client]):
        super()._set_client(client)
        # reset model poll thread
        if self._model is not None:
            self._model.stop_polling()
            self._model.client = self._client
            self._model.start_polling()

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        logger.debug("Stopping pv_model polling")
        self._model.stop_polling(wait_time=5000)
        super().closeEvent(a0)


class NestableHeader(HeaderEnum):
    NAME = 0
    DESCRIPTION = auto()
    CREATED = auto()
    OPEN = auto()
    REMOVE = auto()


class NestableTableModel(BaseTableEntryModel):
    # Shows simplified details (created time, description, # pvs, # child colls)
    # Open details delegate
    headers: List[str]
    _button_cols: List[NestableHeader] = [NestableHeader.OPEN, NestableHeader.REMOVE]
    _header_to_field: Dict[NestableHeader, str] = {
        NestableHeader.NAME: 'title',
        NestableHeader.DESCRIPTION: 'description',
    }

    def __init__(
        self,
        *args,
        client: Optional[Client] = None,
        entries: Optional[List[Union[Snapshot, Collection]]] = None,
        **kwargs
    ) -> None:
        super().__init__(*args, entries=entries, **kwargs)
        self.header_enum = NestableHeader
        self.headers = [h.header_name() for h in NestableHeader]
        self._editable_cols = {h.value: False for h in NestableHeader}

    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        """
        Returns the data stored under the given role for the item
        referred to by the index.

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
        entry: Entry = self.entries[index.row()]

        if role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return QtCore.QVariant()

        if index.column() == 0:  # name column
            if role == QtCore.Qt.DecorationRole:
                return self.icon(entry)
            name_text = getattr(entry, 'title')
            return name_text
        elif index.column() == 1:  # description
            return getattr(entry, 'description')
        elif index.column() == 2:  # Created
            return entry.creation_time.strftime('%Y/%m/%d %H:%M')
        elif index.column() == 3:  # Open Delegate
            return "Open"
        elif index.column() == 4:  # Remove Delegate
            return "Remove"


class NestableTableView(BaseDataTableView):
    def __init__(self, *args, **kwargs):
        self._model_cls = NestableTableModel
        self.open_column = 3
        self.remove_column = 4
        super().__init__(*args, **kwargs)

    def gather_sub_entries(self):
        if isinstance(self.data, UUID):
            self.data = self.client.backend.get_entry(self.data)

        if isinstance(self.data, Nestable):
            # gather sub_nestables
            for i, child in enumerate(self.data.children):
                if isinstance(child, UUID):
                    child = self._client.backend.get_entry(child)
                    self.data.children[i] = child
                else:
                    child = child

                if child is None:
                    raise EntryNotFoundError(f"{child} not found in backend, "
                                             "cannot fill with real data")

                if isinstance(child, Nestable) and isinstance(child, Entry):
                    self.sub_entries.append(child)


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
