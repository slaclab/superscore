from qtpy import QtWidgets

from squirrel.type_hints import AnyDataclass

from .data_widget import DataWidget
from .display import Display
from .tag import TagDef, TagsWidget


class NameMixin:
    """
    Mixin class for distributing init_name
    """
    def init_name(self) -> None:
        """
        Set up the name_edit widget appropriately.
        """
        # Load starting text
        load_name = self.bridge.title.get() or ''
        self.last_name = load_name
        self.name_edit.setText(load_name)
        # Set up the saving/loading
        self.name_edit.textEdited.connect(self.update_saved_name)
        self.bridge.title.changed_value.connect(self.apply_new_name)

    def update_saved_name(self, name: str) -> None:
        """
        When the user edits the name, write to the config.
        """
        self.last_name = self.name_edit.text()
        self.bridge.title.put(name)

    def apply_new_name(self, text: str) -> None:
        """
        If the text changed in the data, update the widget.

        Only run if needed to avoid annoyance with cursor repositioning.
        """
        if text != self.last_name:
            self.name_edit.setText(text)


class NameDescTagsWidget(Display, NameMixin, DataWidget):
    """
    Widget for displaying and editing the name, description, and tags fields.

    Any of these will be automatically disabled if the data source is missing
    the corresponding field.
    """
    filename = 'name_desc_tags_widget.ui'

    name_edit: QtWidgets.QLineEdit
    name_frame: QtWidgets.QFrame
    desc_edit: QtWidgets.QPlainTextEdit
    desc_frame: QtWidgets.QFrame
    tags_widget: TagsWidget

    def __init__(self, data: AnyDataclass, **kwargs):

        tag_groups = kwargs.pop('tag_options', dict())

        super().__init__(data=data, **kwargs)
        try:
            self.bridge.title
        except AttributeError:
            self.name_frame.hide()
        else:
            self.init_name()
        try:
            self.bridge.description
        except AttributeError:
            self.desc_frame.hide()
        else:
            self.init_desc()
        try:
            self.bridge.tags
        except AttributeError:
            self.tags_widget.hide()
        else:
            self.init_tags(tag_groups)

    def init_desc(self) -> None:
        """
        Set up the desc_edit widget appropriately.
        """
        # Load starting text
        load_desc = self.bridge.description.get() or ''
        self.last_desc = load_desc
        self.desc_edit.setPlainText(load_desc)
        # Setup the saving/loading
        self.desc_edit.textChanged.connect(self.update_saved_desc)
        self.bridge.description.changed_value.connect(self.apply_new_desc)

    def update_saved_desc(self) -> None:
        """
        When the user edits the desc, write to the config.
        """
        self.last_desc = self.desc_edit.toPlainText()
        self.bridge.description.put(self.last_desc)

    def apply_new_desc(self, desc: str) -> None:
        """
        When some other widget updates the description, update it here.
        """
        if desc != self.last_desc:
            self.desc_edit.setPlainText(desc)

    def init_tags(self, tag_groups: TagDef) -> None:
        """
        Set up the tags widgets appropriately.
        """
        self.tags_widget.setObjectName("TagsWidget")
        self.tags_widget.setEnabled(True)
        self.tags_widget.set_tag_groups(tag_groups)
