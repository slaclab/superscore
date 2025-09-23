from __future__ import annotations

from pathlib import Path

from pcdsutils.qt.designer_display import DesignerDisplay

from squirrel.utils import SQUIRREL_SOURCE_PATH


class Display(DesignerDisplay):
    """Helper class for loading designer .ui files and adding logic"""

    ui_dir: Path = SQUIRREL_SOURCE_PATH / 'pages/ui'
