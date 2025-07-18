from typing import Any, Optional

import qtawesome as qta
from qtpy import QtCore, QtGui, QtWidgets

import superscore.color
from superscore.type_hints import TagDef, TagSet
from superscore.widgets import FlowLayout


class TagChip(QtWidgets.QFrame):
    """
    A UI element representing active tags for one tag group. TagsWidget uses multiple to
    represent a full TagSet.

    This widget display the tag group name and the name of all its active tags. If enabled,
    clicking this widget opens a popup to activate or deactivate tags, and it exposes a button
    to clear all active tags.

    Parameters
    ----------
    tag_group : int
        The index of this widget's tag group.
    choices : dict[int, str]
        A map relating tag indices and names.
    tag_name : str
        The name of this widget's tag group.
    desc : str
        The description of this widget's tag group. Only shown via tooltip.
    enabled : bool
        Whether this widget is editable or its set of active tags is frozen.
    **kwargs : Any
        Additional keyword arguments to pass to the base QWidget.
    """

    tagsChanged = QtCore.Signal(set)

    def __init__(self, tag_group: int, choices: dict[int, str], tag_name: str, desc: str = "", enabled: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.tag_group = tag_group
        self.tag_name = tag_name
        self.choices = choices
        self.tags = set()
        self.setToolTip(desc)

        self.editor = TagEditor(self.choices, self.tags, parent=self)
        self.editor.tagsChanged.connect(self.set_tags)
        self.editor.hide()

        self.button_rect = QtCore.QRect()

        self.setEnabled(enabled)
        self.adjustSize()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        margins = self.contentsMargins()
        if event.rect().width() > self.sizeHint().width():
            margins.setLeft((event.rect().width() - self.sizeHint().width()) // 2)
            margins.setRight((event.rect().width() - self.sizeHint().width()) // 2)
        if event.rect().height() > self.sizeHint().height():
            margins.setTop((event.rect().height() - self.sizeHint().height()) // 2)
            margins.setBottom((event.rect().height() - self.sizeHint().height()) // 2)
        self.setContentsMargins(margins)
        self.paint(painter)

    def paint(self, painter):
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        tag_strings = {self.choices[tag] for tag in self.tags}

        painter.setBrush(QtCore.Qt.NoBrush)
        pen = QtGui.QPen()
        pen.setWidth(2)
        pen.setStyle(QtCore.Qt.DashLine)
        pen.setColor(QtGui.QColor(superscore.color.GREY))
        painter.setPen(pen)
        rect = self.contentsRect()
        spacing = rect.height() / 4

        border_rect = self.contentsRect() - QtCore.QMargins(pen.width(), pen.width(), pen.width(), pen.width())
        painter.drawRoundedRect(border_rect, border_rect.height() / 2, border_rect.height() / 2)
        painter.translate(self.contentsRect().topLeft())

        painter.setPen(QtCore.Qt.NoPen)
        self.button_rect = QtCore.QRectF((rect.height() / 2) - spacing, (rect.height() / 2) - spacing, spacing * 2, spacing * 2)
        painter.translate(self.button_rect.left(), self.button_rect.top())
        if self.isEnabled():
            if len(tag_strings) > 0:
                icon = qta.icon("ph.x-bold", color=superscore.color.GREY)
            else:
                icon = qta.icon("ph.plus-bold", color=superscore.color.GREY)
            icon.paint(painter, QtCore.QRectF(0, 0, self.button_rect.width(), self.button_rect.height()).toRect())
            painter.translate(self.button_rect.width() + (spacing / 2), 0)
        else:
            painter.translate(spacing, 0)

        painter.setPen(QtCore.Qt.SolidLine)
        name_rect = QtCore.QRectF(0, 0, painter.font().pointSize() * len(self.tag_name), spacing * 2)
        painter.drawText(name_rect, self.tag_name)
        painter.translate(name_rect.right(), 0)

        if len(tag_strings) > 0:
            painter.drawLine(QtCore.QPointF(-painter.pen().width(), name_rect.top()), QtCore.QPointF(-painter.pen().width(), name_rect.bottom()))
            painter.translate(spacing, 0)

        pen.setColor(QtGui.QColor(superscore.color.LIGHT_BLUE))
        painter.setPen(pen)
        tags_string = ", ".join(sorted(tag_strings))
        tags_rect = QtCore.QRectF(0, 0, painter.font().pointSize() * len(tags_string), name_rect.height())
        painter.drawText(tags_rect, tags_string)

        painter.restore()
        painter.translate(rect.topRight())

    def sizeHint(self):
        metrics = QtGui.QFontMetricsF(QtGui.QFont())
        tag_strings = {self.choices[tag] for tag in self.tags}
        text = self.tag_name + ", ".join(sorted(tag_strings))
        text_size = metrics.size(QtCore.Qt.TextSingleLine, text)
        height = text_size.height() * 2
        spacing = height / 4
        spaces = 7 if len(self.tags) > 0 else 4
        spaces += int(self.isEnabled())
        return QtCore.QSizeF(text_size.width() + (spaces * spacing), height).toSize()

    def minimumSize(self):
        return self.sizeHint()

    def set_tags(self, tags: set[int]) -> None:
        """Set this widget's active tags and redraw."""
        self.tags = tags
        self.updateGeometry()
        self.tagsChanged.emit(self.tags)

    def clear(self) -> None:
        """Clear this widget's active tags."""
        self.tags = set()
        self.editor.choice_list.clearSelection()

    def mouseReleaseEvent(self, event):
        if len(self.tags) > 0 and self.button_rect.contains(event.pos()):
            self.clear()
        else:
            self.editor.show()


class TagEditor(QtWidgets.QWidget):
    """
    Popup for selecting a TagChip's active tags.

    Parameters
    ----------
    choices : dict[int, str]
        Map of tag indices to names; received from TagChip. Used to display the correct tag
        names while sending the correct tag indices back to the TagChip.
    selected : set[int]
        Set of tag indices representing active tags from the TagChip. These will be selected
        when this widget is initially shown.
    parent : QWidget
        This widget's parent; typically a TagChip. Only used for positioning, data is
        transferred via signals.

    Attributes
    ----------
    tagsChanged : QtCore.Signal(set)
        Signal emitted when the set of selected tags is changed.
    """

    tagsChanged = QtCore.Signal(set)

    def __init__(self, choices: dict[int, str], selected: set[int], parent: QtWidgets.QWidget = None) -> None:
        """
        Initialize the TagEditor widget.
        """
        super().__init__(parent=parent)
        self.setWindowFlags(QtCore.Qt.Popup)

        layout = QtWidgets.QVBoxLayout()
        layout.setObjectName("TagEditorLayout")
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.choice_list = QtWidgets.QListWidget()
        self.choice_list.setSelectionMode(self.choice_list.SelectionMode.MultiSelection)
        self.layout().addWidget(self.choice_list)
        self.set_choices(choices)

        self.choice_list.itemSelectionChanged.connect(self.emitTagsChanged)

    def emitTagsChanged(self):
        """
        Emits self.tagsChanged with the new set of selected tag indices. Needed so that
        self.tagsChanged can emit the required data despite being connected to the data-less
        QListWidget.itemSelectionChanged signal.
        """
        selected = {item.data(QtCore.Qt.UserRole) for item in self.choice_list.selectedItems()}
        self.tagsChanged.emit(selected)

    def set_choices(self, choices: dict[int, str]) -> None:
        """
        Set this widget's tag choices. Clears and then re-populates choice_list, with each
        list item containing both the tag index and name.
        """
        self.choice_list.clear()
        for tag, string in choices.items():
            self.choice_list.addItem(string)
            item = self.choice_list.item(self.choice_list.count() - 1)
            item.setData(QtCore.Qt.UserRole, tag)

    def show(self):
        corner = self.parent().rect().bottomLeft()
        global_pos = self.parent().mapToGlobal(corner)
        self.move(global_pos)
        super().show()


class TagsWidget(QtWidgets.QWidget):
    """
    A container for TagChips arranged in a flow layout.

    This widget manages a collection of tag elements, each of which manages the
    addition, removal, and display of tags in its tag group. To freeze the set
    of tags in the TagChips, set enabled to False on this widget. The tags are
    arranged using a custom FlowLayout that automatically wraps the tags when
    they reach the edge of the widget.

    Attributes
    ----------
    tag_list_layout : FlowLayout
        The layout containing the widget's tag elements.
    """

    tagSetChanged = QtCore.Signal(object)  # PySide6 is cursed

    def __init__(
        self,
        *args: Any,
        tag_groups: TagDef = {},
        enabled: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the TagsWidget.

        Parameters
        ----------
        tag_groups : TagDef
            A data structure containing tag group indices, names, and members
        *args : Any
            Additional positional arguments passed to the base QWidget.
        **kwargs : Any
            Additional keyword arguments passed to the base QWidget.
        """
        super().__init__(*args, **kwargs)

        self.setLayout(FlowLayout(margin=0, spacing=5))
        self.layout().setObjectName("TagChipFlowLayout")
        self.set_tag_groups(tag_groups)

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.setEnabled(enabled)

    def emitTagSetChanged(self) -> None:
        """Emits the tagSetChanged signal with the widget's current TagSet"""
        self.tagSetChanged.emit(self.get_tag_set())

    def set_tag_groups(self, tag_groups: TagDef) -> None:
        while self.layout().count() > 0:
            self.layout().takeAt(0)
        for tag_group, details in tag_groups.items():
            chip = TagChip(tag_group, details[2], details[0], desc=details[1], enabled=self.isEnabled())
            chip.tagsChanged.connect(self.emitTagSetChanged)
            self.layout().addWidget(chip)
        self.tag_groups = tag_groups

    def clear_tags(self) -> None:
        """Clears all tags in all TagChips"""
        chips = self.findChildren(TagChip)
        for chip in chips:
            chip.clear()

    def set_tags(self, tag_set: TagSet) -> None:
        """Sets the child TagChips according to the provided TagSet"""
        self.clear_tags()
        for tag_group, tags in tag_set.items():
            chip = self.get_group_chip(tag_group)
            if isinstance(chip, TagChip):
                chip.set_tags(tags)
                if len(tags) == 0:
                    chip.hide()
                else:
                    chip.show()

    def get_tag_set(self) -> TagSet:
        """Constructs the TagSet representation of the child TagChips"""
        tag_set = {}
        chips = self.findChildren(TagChip)
        for chip in chips:
            tag_set[chip.tag_group] = chip.tags
        return tag_set

    def get_group_chip(self, tag_group: int) -> Optional[TagChip]:
        """Returns TagChip corresponding to the desired tag group, or None if chip was not found"""
        chips = self.findChildren(TagChip)
        for chip in chips:
            if chip.tag_group == tag_group:
                return chip
        return None

    def paint(self, painter):
        painter.translate(self.layout().itemAt(0).widget().pos())
        for i in range(self.layout().count()):
            chip = self.layout().itemAt(i).widget()
            if chip.isEnabled() or len(chip.tags) > 0:
                chip.paint(painter)
        painter.resetTransform()


class TagDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, tag_def, parent=None):
        super().__init__(parent)
        self.tag_def = tag_def

    def paint(self, painter, option, index):
        tag_widget = TagsWidget(tag_groups=self.tag_def, enabled=False)
        tag_widget.set_tags(index.data())
        tag_widget.layout().setGeometry(option.rect)
        tag_widget.paint(painter)

    def sizeHint(self, option, index):
        tag_widget = TagsWidget(tag_groups=self.tag_def, enabled=False)
        tag_widget.set_tags(index.data())
        width = option.rect.width()
        height = tag_widget.heightForWidth(width)
        return QtCore.QSize(width, height)
