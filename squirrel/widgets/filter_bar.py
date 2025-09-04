from qtpy import QtCore, QtWidgets


class FilterRow(QtWidgets.QWidget):
    """
    A single row of filter inputs: column, operator, and input value.

    Parameters
    ----------
    column_names : list[str]
        The columns to apply filters to. Names can be dynamic, multiple filters can be applied to each.
    parent : QtWidgets.QWidget | None
        The parent widget of this object.
    """

    filter_changed = QtCore.Signal()
    filter_removed = QtCore.Signal(QtWidgets.QWidget)

    def __init__(self, column_names: list[str], parent : QtWidgets.QWidget | None = None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.column_dropdown = QtWidgets.QComboBox()
        self.column_dropdown.addItems(column_names)

        self.operator_dropdown = QtWidgets.QComboBox()
        self.operator_dropdown.addItems(["=", "!=", "<", "<=", ">", ">="])

        # The value the user types to compare against
        self.input_value = QtWidgets.QLineEdit()

        self.remove_button = QtWidgets.QToolButton()
        self.remove_button.setText("×")
        self.remove_button.setFixedWidth(24)

        layout.addWidget(self.column_dropdown)
        layout.addWidget(self.operator_dropdown)
        layout.addWidget(self.input_value)
        layout.addWidget(self.remove_button)

        # Signals
        self.column_dropdown.currentIndexChanged.connect(self.filter_changed)
        self.operator_dropdown.currentIndexChanged.connect(self.filter_changed)
        self.input_value.textChanged.connect(self.filter_changed)
        self.remove_button.clicked.connect(lambda: self.filter_removed.emit(self))

    def get_filter(self) -> dict[str, str]:
        """Return filter expression as a dictionary"""
        return {
            "column": self.column_dropdown.currentText(),
            "operator": self.operator_dropdown.currentText(),
            "value": self.input_value.text(),
        }


class FilterBar(QtWidgets.QWidget):
    """
    Container widget that can hold multiple FilterRow widgets.

    Parameters
    ----------
    column_names : list[str]
        The columns to apply filters to. Names can be dynamic, multiple filters can be applied to each.
    parent : QtWidgets.QWidget | None
        The parent widget of this object.
    """

    filters_updated = QtCore.Signal()

    def __init__(self, column_names: list[str], parent : QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.column_names = column_names

        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.row_container = QtWidgets.QVBoxLayout()
        self.row_container.setSpacing(10)

        self.add_filter_button = QtWidgets.QPushButton("+ Add")
        self.add_filter_button.clicked.connect(self.add_filter_row)

        self.main_layout.addLayout(self.row_container)

        add_button_layout = QtWidgets.QHBoxLayout()
        add_button_layout.setContentsMargins(0, 0, 0, 0)
        add_button_layout.addWidget(self.add_filter_button)
        add_button_layout.addStretch()

        self.main_layout.addLayout(add_button_layout)

        self.filter_rows = []
        self.add_filter_row()  # Always start with one empty row

    def add_filter_row(self) -> None:
        """Add a new row for filtering a column to this widget"""
        row = FilterRow(self.column_names, self)
        self.filter_rows.append(row)
        self.row_container.addWidget(row)

        row.filter_changed.connect(self.filters_updated.emit)
        row.filter_removed.connect(self.remove_filter_row)
        self.filters_updated.emit()

    def remove_filter_row(self, row: FilterRow) -> None:
        """Remove an existing row from this widget"""
        self.filter_rows.remove(row)
        self.row_container.removeWidget(row)
        row.deleteLater()
        self.filters_updated.emit()

    def get_filters(self) -> list[dict]:
        """Return all active filters"""
        return [row.get_filter() for row in self.filter_rows if row.input_value.text()]
