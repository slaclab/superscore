from qtpy import QtCore, QtWidgets


class DateRangeWidget(QtWidgets.QWidget):
    """A widget for selecting a date range.  The range is stored as two dates,
    which are set using a QCalendarWidget or the setRange method."""

    FORMAT = "yyyy-MM-dd"
    rangeChanged = QtCore.Signal(QtCore.QDate, QtCore.QDate)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setLayout(QtWidgets.QVBoxLayout())

        self.since = QtWidgets.QPushButton()
        self.until = QtWidgets.QPushButton()

        self.since.setFlat(True)
        self.until.setFlat(True)

        self.since.clicked.connect(self.open_calendar)
        self.until.clicked.connect(self.open_calendar)

        layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel()
        label.setText("Since: ")
        layout.addWidget(label)
        layout.addWidget(self.since)
        self.layout().addLayout(layout)
        layout = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel()
        label.setText("Until: ")
        layout.addWidget(label)
        layout.addWidget(self.until)
        self.layout().addLayout(layout)

        self.calendar = QtWidgets.QCalendarWidget()
        self.calendar.setWindowModality(QtCore.Qt.ApplicationModal)

    @QtCore.Slot()
    def open_calendar(self):
        target = self.sender()
        try:
            self.calendar.selectionChanged.disconnect()
        except TypeError:
            pass
        self.calendar.selectionChanged.connect(
            lambda: target.setText(self.calendar.selectedDate().toString(self.FORMAT))
        )
        self.calendar.selectionChanged.connect(self.calendar.hide)
        self.calendar.selectionChanged.connect(self.emitRangeChanged)
        self.calendar.show()

    def emitRangeChanged(self):
        self.rangeChanged.emit(
            QtCore.QDate.fromString(self.since.text(), self.FORMAT),
            QtCore.QDate.fromString(self.until.text(), self.FORMAT)
        )

    def setRange(self, since: QtCore.QDate, until: QtCore.QDate):
        self.since.setText(since.toString(self.FORMAT))
        self.until.setText(until.toString(self.FORMAT))
        self.emitRangeChanged()
