import logging
import operator

from qtpy import QtCore

from squirrel.errors import BackendError
from squirrel.model import Snapshot

logger = logging.getLogger(__file__)


class SnapshotTableModel(QtCore.QAbstractTableModel):
    """A table model containing all of the Snapshots available in a client"""

    HEADER = [
        "TIMESTAMP",
        "SNAPSHOT TITLE",
    ]

    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self._data = []
        self.fetch()

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        meta_pvs = self.client.backend.get_meta_pvs()
        return len(self.HEADER) + len(meta_pvs)

    def data(
        self,
        index: QtCore.QModelIndex,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ):
        column = index.column()
        if role == QtCore.Qt.DisplayRole:
            snapshot = self._data[index.row()]
            if column == 0:
                return snapshot.creation_time.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            elif column == 1:
                return snapshot.title
            else:
                try:
                    return snapshot.meta_pvs[column - len(self.HEADER)].data
                except IndexError:
                    return None
        elif role == QtCore.Qt.ToolTipRole and column >= 2:
            snapshot = self._data[index.row()]
            try:
                return snapshot.meta_pvs[column - len(self.HEADER)].pv_name
            except IndexError:
                return None
        else:
            return None

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.DisplayRole
    ):
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                try:
                    return self.HEADER[section]
                except IndexError:
                    meta_pvs = self.client.backend.get_meta_pvs()
                    return meta_pvs[section - len(self.HEADER)].description

    def fetch(self):
        """Fetch all snapshots from the backend"""
        self.beginResetModel()
        self._data = sorted(
            self.client.search(("entry_type", "eq", Snapshot)),
            key=lambda s: s.creation_time,
            reverse=True,
        )
        self.endResetModel()

    def index_to_snapshot(self, index: QtCore.QModelIndex) -> Snapshot:
        """Convert a QModelIndex to a Snapshot object."""
        if not (index and index.isValid()):
            return None
        row = index.row()
        try:
            filled_snapshot = self.client.backend.get_snapshots(uuid=self._data[row].uuid)
        except BackendError as e:
            logger.exception(e)
        else:
            self._data[row].pvs = filled_snapshot.pvs
        return self._data[row]


class SnapshotFilterModel(QtCore.QSortFilterProxyModel):
    SUPPORTED_OPERATORS = {
        "=": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFilterKeyColumn(1)
        self.since = QtCore.QDate.currentDate().addYears(-1)
        self.until = QtCore.QDate.currentDate()
        self.filters = []  # List that contains: [{column, operator, value}]

    def filterAcceptsRow(self, row: int, parent: QtCore.QModelIndex) -> bool:
        datetime = self.sourceModel()._data[row].creation_time
        date = QtCore.QDate(datetime.year, datetime.month, datetime.day)
        is_date_in_range = self.since <= date and date <= self.until

        if not is_date_in_range:
            return False

        # Meta PV filtering
        snapshot = self.sourceModel()._data[row]
        for meta_pv_filter in self.filters:
            column_name = meta_pv_filter["column"]
            input_operator = meta_pv_filter["operator"]
            input_value = meta_pv_filter["value"]

            comparison_function = self.SUPPORTED_OPERATORS.get(input_operator)

            # Retrieve the data for the corresponding meta_pv
            matching_pvs = [pv for pv in snapshot.meta_pvs if pv.description == column_name]
            pv_value = matching_pvs[0].data

            try:
                pv_value = float(pv_value)
                input_value = float(input_value)
            except (ValueError, TypeError):
                pv_value = str(pv_value)
                input_value = str(input_value)

            try:
                if not comparison_function(pv_value, input_value):
                    return False
            except Exception as e:
                print(f'Exception applying filter: {e}')
                return False

        return super().filterAcceptsRow(row, parent)

    def setDateRange(self, since: QtCore.QDate, until: QtCore.QDate):
        self.since = since
        self.until = until
        self.invalidateFilter()

    def setMetaPVFilters(self, filters: list[dict]) -> None:
        """Set the filters that will be applied to the meta pv columns"""
        self.filters = filters
        self.invalidateFilter()
