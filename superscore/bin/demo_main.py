"""
`superscore demo` opens the graphical user interface for superscore with a demo
database pre-loaded

Function components are separated from the arg parser to defer heavy imports
"""
import configparser
from pathlib import Path
from typing import Callable, Iterable, Union

import superscore.tests.conftest_data
from superscore.backends import _Backend
from superscore.bin.demo_parser import DEMO_CONFIG
from superscore.bin.ui_parser import main as ui_main
from superscore.client import Client
from superscore.model import PV
from superscore.tests.ioc import IOCFactory
from superscore.utils import build_abs_path


def populate_backend(backend: _Backend, sources: Iterable[Union[Callable, str]]) -> None:
    """
    Utility for quickly filling test backends with data. Supports a mix of many
    types of sources:
    * Roots
    * Entries
    * Callables that return Roots or Entries
    * strings that search for test data callables, but critically not fixtures
    """
    for source in sources:
        if isinstance(source, Callable):
            data = source()
        elif isinstance(source, str):
            func = getattr(superscore.tests.conftest_data, source, False)
            data = func()
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")
        backend.save_entry(data)


def main(*args, db_path=None, **kwargs):
    parser = configparser.ConfigParser()
    parser.read(DEMO_CONFIG)
    if db_path is not None:
        db_path = Path(db_path)
        parser.set('backend', 'path', build_abs_path(Path.cwd(), db_path))
    client = Client.from_parsed_config(parser)
    # start with clean demo database
    client.backend.reset()
    # write data from the sources to the backend
    source_names = parser.get("demo", "fixtures").split()
    populate_backend(client.backend, source_names)
    # IOCFactory needs the Entries with data
    filled = list(client.search(("entry_type", "eq", PV)))
    with IOCFactory.from_entries(filled, client)(prefix=''):
        ui_main(cfg_path=DEMO_CONFIG)
