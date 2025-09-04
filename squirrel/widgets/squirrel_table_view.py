from qtpy import QtCore, QtGui, QtWidgets

import squirrel.color


class SquirrelTableView(QtWidgets.QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setShowGrid(False)
        self.setItemDelegate(SquirrelTableGridDelegate())
        self.verticalHeader().hide()
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self.copy_address(self.indexAt(event.position().toPoint()))
        else:
            super().mousePressEvent(event)

    def copy_address(self, index):
        text = self.model().data(index, QtCore.Qt.ToolTipRole)
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard.supportsSelection():
            mode = clipboard.Mode.Selection
        else:
            mode = clipboard.Mode.Clipboard
        clipboard.setText(text, mode=mode)


class SquirrelTableGridDelegate(QtWidgets.QStyledItemDelegate):
    """Styled Item Delegate for showing the horizontal grid lines in a
    table view. To be used by the SquirrelTableView class.
    """
    def paint(self, painter, option, index):
        # Draw the default item
        super().paint(painter, option, index)

        # Construct the QPen for the grid lines
        grid_color = QtGui.QColor(squirrel.color.TABLE_GRID)
        border_pen = QtGui.QPen(grid_color)
        painter.setPen(border_pen)

        # Draw the top & bottom borders
        painter.drawLine(option.rect.topLeft(), option.rect.topRight())
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
