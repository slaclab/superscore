"""Client for superscore.  Used for programmatic interactions with superscore"""
import configparser
import logging
import os
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Union
from uuid import UUID

from superscore.backends import get_backend
from superscore.backends.core import SearchTerm, SearchTermType, _Backend
from superscore.compare import DiffItem, EntryDiff, walk_find_diff
from superscore.control_layers import ControlLayer, EpicsData
from superscore.control_layers.status import TaskStatus
from superscore.model import (Collection, Entry, Nestable, Parameter, Readback,
                              Setpoint, Snapshot)
from superscore.utils import build_abs_path

logger = logging.getLogger(__name__)


class Client:
    backend: _Backend
    cl: ControlLayer

    def __init__(
        self,
        backend: Optional[_Backend] = None,
        control_layer: Optional[ControlLayer] = None,
    ) -> None:
        if backend is None:
            # set up a temp backend with temp file
            logger.warning('No backend specified, loading an empty test backend')
            backend = get_backend('test')()
        if control_layer is None:
            control_layer = ControlLayer()

        self.backend = backend
        self.cl = control_layer

    @classmethod
    def from_config(cls, cfg: Optional[Path] = None):
        """
        Create a client from the configuration file specification.

        Configuration file should be of an "ini" format, along the lines of:

        .. code::

            [backend]
            type = filestore
            path = ./db/filestore.json

            [control_layer]
            ca = true
            pva = true

        The ``backend`` section has one special key ("type"), and the rest of the
        settings are passed to the appropriate ``_Backend`` as keyword arguments.

        The ``control_layer`` section has a key-value pair for each available shim.
        The ``ControlLayer`` object will be created with all the valid shims with
        True values.

        Parameters
        ----------
        cfg : Path, optional
            Path to a configuration file, by default None.  If omitted,
            :meth:`.find_config` will be used to find one

        Raises
        ------
        RuntimeError
            If a configuration file cannot be found
        """
        if not cfg:
            cfg = cls.find_config()
        if not os.path.exists(cfg):
            raise RuntimeError(f"Superscore configuration file not found: {cfg}")

        cfg_parser = configparser.ConfigParser()
        cfg_parser.read(cfg)
        logger.debug(f"Loading configuration file at ({cfg})")
        return cls.from_parsed_config(cfg_parser, cfg)

    @classmethod
    def from_parsed_config(cls, cfg_parser: configparser.ConfigParser, cfg_path=""):
        """
        Initializes Client using a ConfigParser that has already read in a config.
        This method enables the caller to edit a config after parsing but before
        Client initialization.
        """
        # Gather Backend
        if 'backend' in cfg_parser.sections():
            backend_type = cfg_parser.get("backend", "type")
            kwargs = {key: value for key, value
                      in cfg_parser["backend"].items()
                      if key != "type"}
            backend_class = get_backend(backend_type)
            if 'path' in kwargs:
                kwargs['path'] = build_abs_path(Path(cfg_path).parent, kwargs['path'])
            backend = backend_class(**kwargs)
        else:
            logger.warning('No backend specified, loading an empty test backend')
            backend = get_backend('test')()

        # configure control layer and shims
        if 'control_layer' in cfg_parser.sections():
            shim_choices = [val for val, enabled
                            in cfg_parser["control_layer"].items()
                            if enabled]
            control_layer = ControlLayer(shims=shim_choices)
        else:
            logger.debug('No control layer shims specified, loading all available')
            control_layer = ControlLayer()

        return cls(backend=backend, control_layer=control_layer)

    @staticmethod
    def find_config() -> Path:
        """
        Search for a ``superscore`` configuation file.  Searches in the following
        locations in order
        - ``$SUPERSCORE_CFG`` (a full path to a config file)
        - ``$XDG_CONFIG_HOME/{superscore.cfg, .superscore.cfg}`` (either filename)
        - ``~/.config/{superscore.cfg, .superscore.cfg}``

        Returns
        -------
        path : str
            Absolute path to the configuration file

        Raises
        ------
        OSError
            If no configuration file can be found by the described methodology
        """
        # Point to with an environment variable
        if os.environ.get('SUPERSCORE_CFG', False):
            superscore_cfg = os.environ.get('SUPERSCORE_CFG')
            logger.debug("Found $SUPERSCORE_CFG specification for Client "
                         "configuration at %s", superscore_cfg)
            return superscore_cfg
        # Search in the current directory and home directory
        else:
            config_dirs = [os.environ.get('XDG_CONFIG_HOME', "."),
                           os.path.expanduser('~/.config'),]
            for directory in config_dirs:
                logger.debug('Searching for superscore config in %s', directory)
                for path in ('.superscore.cfg', 'superscore.cfg'):
                    full_path = os.path.join(directory, path)

                    if os.path.exists(full_path):
                        logger.debug("Found configuration file at %r", full_path)
                        return full_path
        # If found nothing
        default_config = os.path.join(os.path.dirname(__file__), "tests/demo.cfg")
        if os.path.isfile(default_config):
            return default_config
        else:
            raise OSError("No superscore configuration file found")

    def search(self, *post: SearchTermType) -> Generator[Entry, None, None]:
        """
        Search backend for entries matching all SearchTerms in ``post``.  Can search by any
        field, plus some special keywords. Backends support operators listed in _Backend.search.
        Some operators are supported in the UI / client and must be converted before being
        passed to the backend.
        """
        new_search_terms = []
        for search_term in post:
            if not isinstance(search_term, SearchTerm):
                search_term = SearchTerm(*search_term)
            if search_term.operator == 'isclose':
                target, rel_tol, abs_tol = search_term.value
                lower = target - target * rel_tol - abs_tol
                upper = target + target * rel_tol + abs_tol
                new_search_terms.append(SearchTerm(search_term.attr, 'gt', lower))
                new_search_terms.append(SearchTerm(search_term.attr, 'lt', upper))
            else:
                new_search_terms.append(search_term)
        return self.backend.search(*new_search_terms)

    def save(self, entry: Entry):
        """Save information in ``entry`` to database"""
        # validate entry is valid
        self.backend.save_entry(entry)

    def delete(self, entry: Entry) -> None:
        """Remove item from backend, depending on backend"""
        # check for references to ``entry`` in other objects?
        self.backend.delete_entry(entry)

    def compare(self, entry_l: Entry, entry_r: Entry) -> EntryDiff:
        """
        Compare two entries and return a diff (EntryDiff).
        Fills ``entry_l`` and ``entry_r`` before calculating the difference

        Parameters
        ----------
        entry_l : Entry
            the original (left-hand) Entry
        entry_r : Entry
            the new (right-hand) Entry

        Returns
        -------
        EntryDiff
            An EntryDiff that tracks the two comparison candidates, and a list
            of DiffItem's
        """
        # Handle the most obvious case.
        if type(entry_l) is not type(entry_r):
            diffs = DiffItem(original_value=entry_l, new_value=entry_r, path=[])
            return EntryDiff(original_entry=entry_l, new_entry=entry_r, diffs=[diffs])

        self.fill(entry_l)
        self.fill(entry_r)
        diffs = walk_find_diff(entry_l, entry_r)

        return EntryDiff(original_entry=entry_l, new_entry=entry_r, diffs=list(diffs))

    def fill(self, entry: Union[Entry, UUID], fill_depth: Optional[int] = None) -> None:
        """
        Walk through ``entry`` and replace UUIDs with corresponding Entry's.
        Does nothing if ``entry`` is a non-Nestable or UUID.
        Filling happens "in-place", modifying ``entry``.

        Parameters
        ----------
        entry : Union[Entry, UUID]
            Entry that may contain UUIDs to be filled with full Entry's
        fill_depth : Optional[int], by default None
            The depth to fill.  (value of 1 will fill just ``entry``'s children)
            If None, fill until there is no filling left
        """
        if fill_depth is not None:
            fill_depth -= 1
            if fill_depth <= 0:
                return

        if isinstance(entry, Nestable):
            new_children = []
            for child in entry.children:
                if isinstance(child, UUID):
                    search_condition = SearchTerm('uuid', 'eq', child)
                    filled_child = list(self.search(search_condition))[0]
                    self.fill(filled_child, fill_depth)
                    new_children.append(filled_child)
                else:
                    new_children.append(child)

            entry.children = new_children

    def snap(self, dest: Optional[Snapshot] = None) -> Snapshot:
        """
        Asyncronously read data for all PVs under ``entry``, and store in a
        Snapshot.  PVs that can't be read will have an exception as their value.

        Parameters
        ----------
        entry : Collection
            the Collection to save

        Returns
        -------
        Snapshot
            a Snapshot corresponding to the input Collection
        """
        logger.debug("Saving Snapshot")
        pvs = list(self.search(("entry_type", "eq", Parameter)))
        readback_pvs = [pv.readback for pv in pvs if getattr(pv, "readback", None)]
        meta_pvs = self.backend.get_meta_pvs()
        all_pvs = pvs + readback_pvs + meta_pvs
        values = self.cl.get([pv.pv_name for pv in all_pvs])
        data = {pv.pv_name: value for pv, value in zip(all_pvs, values)}

        snapshot = dest or Snapshot()

        for pv in pvs:
            if pv.readback is not None:
                value = data[pv.readback.pv_name]
                edata = self._value_or_default(value)
                readback = Readback.from_parameter(
                    pv.readback,
                    data=edata.data,
                    status=edata.status,
                    severity=edata.severity,
                )
                readback_pvs.remove(pv.readback)
            else:
                readback = None

            value = data[pv.pv_name]
            edata = self._value_or_default(value)
            if pv.read_only:
                new_entry = Readback.from_parameter(
                    pv,
                    data=edata.data,
                    status=edata.status,
                    severity=edata.severity,
                )
            else:
                new_entry = Setpoint.from_parameter(
                    pv,
                    data=edata.data,
                    status=edata.status,
                    severity=edata.severity,
                    readback=readback,
                )
            snapshot.children.append(new_entry)

        for pv in readback_pvs:
            value = data[pv.pv_name]
            edata = self._value_or_default(value)
            new_entry = Readback.from_parameter(
                pv,
                data=edata.data,
                status=edata.status,
                severity=edata.severity,
            )
            snapshot.children.append(new_entry)

        for pv in meta_pvs:
            value = data[pv.pv_name]
            edata = self._value_or_default(value)
            new_entry = Readback.from_parameter(
                pv,
                data=edata.data,
                status=edata.status,
                severity=edata.severity,
            )
            snapshot.meta_pvs.append(new_entry)

        return snapshot

    def apply(
        self,
        entry: Union[Setpoint, Snapshot],
        sequential: bool = False
    ) -> Optional[List[TaskStatus]]:
        """
        Apply settings found in ``entry``.  If no writable values found, return.
        If ``sequential`` is True, apply values in ``entry`` in sequence, blocking
        with each put request.  Else apply all values simultaneously (asynchronously)

        Parameters
        ----------
        entry : Union[Setpoint, Snapshot]
            The entry to apply values from
        sequential : bool, optional
            Whether to apply values sequentially, by default False

        Returns
        -------
        Optional[List[TaskStatus]]
            TaskStatus(es) for each value applied.
        """
        if not isinstance(entry, (Setpoint, Snapshot)):
            logger.info("Entries must be a Snapshot or Setpoint")
            return

        if isinstance(entry, Setpoint):
            return [self.cl.put(entry.pv_name, entry.data)]

        # Gather pv-value list and apply at once
        status_list = []
        pv_list, data_list = self._gather_data(entry, writable_only=True)
        if sequential:
            for pv, data in zip(pv_list, data_list):
                logger.debug(f'Putting {pv} = {data}')
                status: TaskStatus = self.cl.put(pv, data)
                if status.exception():
                    logger.warning(f"Failed to put {pv} = {data}, "
                                   "terminating put sequence")
                    return

                status_list.append(status)
        else:
            return self.cl.put(pv_list, data_list)

    def find_origin_collection(self, entry: Union[Collection, Snapshot]) -> Collection:
        """
        Return the Collection instance associated with an entry.  The entry can
        be a Collection or Snapshot.

        Raises
        ------
        ValueError
            If snapshot does not record an origin collection
        EntryNotFoundError
            From _Backend.get_entry
        """
        if isinstance(entry, Collection):
            return entry
        elif isinstance(entry, Snapshot):
            origin = entry.origin_collection
            if origin is None:
                raise ValueError(f"{entry.title} ({entry.uuid}) does not have an origin collection)")
            elif isinstance(origin, UUID):
                return self.backend.get_entry(origin)
            else:
                return origin

    def _gather_data(
        self,
        entry: Union[Entry, UUID],
        writable_only: bool = False,
    ) -> tuple[List[str], Optional[List[Any]]]:
        """
        Gather PV name - data pairs that are accessible from ``entry``.  Queries
        the backend to fill any UUIDs found.

        Parameters
        ----------
        entry : Union[Entry, UUID]
            Entry to gather data from
        writable_only : bool
            If True, only include writable data e.g. omit Readbacks; by default False

        Returns
        -------
        tuple[List[str], Optional[List[Any]]]
            the filled pv_list and data_list
        """
        entries = self._gather_leaves(entry)
        pv_list = []
        data_list = []
        for entry in entries:
            if isinstance(entry, Readback) and writable_only:
                pass
            else:  # entry is Parameter, Setpoint, or Readback
                pv_list.append(entry.pv_name)
                if hasattr(entry, "data"):
                    data_list.append(entry.data)
        return pv_list, data_list

    def _gather_leaves(
        self,
        entry: Union[Entry, UUID],
    ) -> Iterable[Entry]:
        """
        Gather all PVs reachable from Entry, including Parameters, Setpoints,
        and Readbacks. Fills UUIDs with full Entries.

        Parameters
        ----------
        entry : Union[Entry, UUID]
            Entry to gather data from

        Returns
        -------
        Iterable[Entry]
            an ordered list of all PV Entries reachable from entry
        """
        entries = []
        seen = set()
        q = [entry]
        while len(q) > 0:
            entry = q.pop()
            uuid = entry if isinstance(entry, UUID) else entry.uuid
            if uuid in seen:
                continue
            elif isinstance(entry, UUID):
                entry = self.backend.get_entry(entry)
            seen.add(entry.uuid)

            if isinstance(entry, Nestable):
                q.extend(reversed(entry.children))  # preserve execution order
            else:  # entry is Parameter, Setpoint, or Readback
                entries.append(entry)
                if getattr(entry, "readback", None) is not None:
                    q.append(entry.readback)
        return entries

    def _build_snapshot(
        self,
        coll: Collection,
        values: Dict[str, EpicsData],
        dest: Optional[Snapshot] = None,
    ) -> Snapshot:
        """
        Traverse a Collection, assembling a Snapshot using pre-fetched data
        along the way

        Parameters
        ----------
        coll : Collection
            The collection being saved
        values : Dict[str, EpicsData]
            A dictionary mapping PV names to pre-fetched values

        Returns
        -------
        Snapshot
            A Snapshot corresponding to the input Collection
        """
        snapshot = dest or Snapshot(
            title=coll.title,
            tags=coll.tags.copy(),
        )
        snapshot.origin_collection = coll

        for child in coll.children:
            if isinstance(child, UUID):
                child = self.backend.get_entry(child)
            if isinstance(child, Parameter):
                if child.readback is not None:
                    edata = self._value_or_default(
                        values.get(child.readback.pv_name, None)
                    )
                    readback = Readback(
                        pv_name=child.readback.pv_name,
                        description=child.readback.description,
                        data=edata.data,
                        status=edata.status,
                        severity=edata.severity,
                        rel_tolerance=child.readback.rel_tolerance,
                        abs_tolerance=child.readback.abs_tolerance,
                    )
                else:
                    readback = None
                edata = self._value_or_default(values.get(child.pv_name, None))
                if child.read_only:
                    # create a readback and propagate tolerances
                    new_entry = Readback(
                        pv_name=child.pv_name,
                        description=child.description,
                        data=edata.data,
                        status=edata.status,
                        severity=edata.severity,
                        rel_tolerance=child.rel_tolerance,
                        abs_tolerance=child.abs_tolerance,
                    )
                else:
                    new_entry = Setpoint(
                        pv_name=child.pv_name,
                        description=child.description,
                        data=edata.data,
                        status=edata.status,
                        severity=edata.severity,
                        readback=readback
                    )
                snapshot.children.append(new_entry)
            elif isinstance(child, Collection):
                snapshot.children.append(self._build_snapshot(child, values))

        snapshot.meta_pvs = []
        for pv in self.backend.get_meta_pvs():
            edata = self._value_or_default(values.get(pv, None))
            readback = Readback(
                pv_name=pv,
                data=edata.data,
                status=edata.status,
                severity=edata.severity,
            )
            snapshot.meta_pvs.append(readback)

        return snapshot

    def _value_or_default(self, value: Any) -> EpicsData:
        """small helper for ensuring value is an EpicsData instance"""
        if value is None or not isinstance(value, EpicsData):
            return EpicsData(data=None)
        return value

    def validate(self, entry: Entry):
        """
        Validate ``entry`` is properly formed and able to be inserted into
        the backend.  Includes checks the following:
        - dataclass is valid
        - reachable from root
        - references are not cyclical, and type-correct
        """
        raise NotImplementedError
