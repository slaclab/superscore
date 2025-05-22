"""
`superscore ui` opens the graphical user interface for superscore

Function components are separated from the arg parser to defer heavy imports
"""
import os
import sys
from typing import Optional

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication

from superscore.client import Client
from superscore.widgets.window import Window

DEFAULT_WIDTH = 1400
DEFAULT_HEIGHT = 800


def main(cfg_path: Optional[str] = None):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    if cfg_path:
        client = Client.from_config(cfg_path)
    else:
        client = None
    main_window = Window(client=client)

    palette = QPalette()

    palette.setColor(QPalette.Window, QColor("#f0f0f0"))
    palette.setColor(QPalette.WindowText, QColor("#333333"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f7f7f7"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#333333"))
    palette.setColor(QPalette.Text, QColor("#333333"))
    palette.setColor(QPalette.Button, QColor("#e7e7e7"))
    palette.setColor(QPalette.ButtonText, QColor("#333333"))
    palette.setColor(QPalette.BrightText, QColor("#000000"))
    palette.setColor(QPalette.Highlight, QColor("#4a86e8"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))

    app.setPalette(palette)

    app.setStyle("Fusion")
    stylesheet_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "squirrel_dark.qss")

    if os.path.exists(stylesheet_path):
        with open(stylesheet_path, "r") as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {stylesheet_path}")

    primary_screen = app.screens()[0]
    center = primary_screen.geometry().center()
    # move window rather creating a QRect because we want to include the frame geometry
    main_window.setGeometry(0, 0, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    delta = main_window.geometry().center()
    main_window.move(center - delta)
    main_window.show()
    app.exec()
