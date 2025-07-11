from uuid import UUID

import pytest

from superscore.backends.core import SearchTerm, _Backend
from superscore.backends.directory import DirectoryBackend
from superscore.backends.filestore import FilestoreBackend
from superscore.backends.test import TestBackend
from superscore.errors import (BackendError, EntryExistsError,
                               EntryNotFoundError)
from superscore.model import Collection, Parameter, Snapshot
from superscore.tests.conftest import setup_test_stack


class TestTestBackend:
    def test_retrieve(self, linac_backend):
        assert linac_backend.get_entry("5544c58f-88b6-40aa-9076-f180a44908f5") is not None  # Parameter
        assert linac_backend.get_entry("06282731-33ea-4270-ba14-098872e627dc") is not None  # Snapshot
        assert linac_backend.get_entry("4bffe9a5-f198-41d8-90ab-870d1b5a325b") is not None  # Setpoint
        with pytest.raises(EntryNotFoundError):
            linac_backend.get_entry("d3589b21-2f77-462d-9280-bb4d4e48d93b")  # Doesn't exist

    def test_create(self, linac_backend):
        collision_entry = Parameter(uuid="5ec33c74-7f4c-4905-a106-44fbfe138140")
        with pytest.raises(EntryExistsError):
            linac_backend.save_entry(collision_entry)

        new_entry = Parameter(uuid="8913b7af-830d-4e32-bebe-b34a4616ce79")
        linac_backend.save_entry(new_entry)
        assert linac_backend.get_entry("8913b7af-830d-4e32-bebe-b34a4616ce79") is not None

    def test_update(self, linac_backend):
        modified_entry = Parameter(uuid="030786df-153b-4d29-bc1f-66deeb116724", description="This is the new description")
        linac_backend.update_entry(modified_entry)
        assert linac_backend.get_entry(modified_entry.uuid) == modified_entry

        missing_entry = Parameter(uuid="d3589b21-2f77-462d-9280-bb4d4e48d93b")
        with pytest.raises(EntryNotFoundError):
            linac_backend.update_entry(missing_entry)

    def test_delete(self, linac_backend):
        entry = linac_backend.get_entry("502d9fc3-455a-47ea-8c48-e1a26d4d3350")
        linac_backend.delete_entry(entry)
        with pytest.raises(EntryNotFoundError):
            linac_backend.get_entry("502d9fc3-455a-47ea-8c48-e1a26d4d3350")

        entry = linac_backend.get_entry("930b137f-5ae2-470e-8b82-c4b4eb7e639e")
        # need new instance because editing entry would automatically sync to the backend
        unsynced = Parameter(**entry.__dict__)
        unsynced.description = "I haven't been synced with the backend"
        with pytest.raises(BackendError):
            linac_backend.delete_entry(unsynced)


@setup_test_stack(backend_type=[FilestoreBackend, DirectoryBackend, TestBackend])
def test_save_entry(test_backend: _Backend):
    new_entry = Parameter()

    test_backend.save_entry(new_entry)
    found_entry = test_backend.get_entry(new_entry.uuid)
    assert found_entry == new_entry

    # Cannot save an entry that already exists.
    with pytest.raises(EntryExistsError):
        test_backend.save_entry(new_entry)


@setup_test_stack(
    sources=["db/filestore.json"], backend_type=[FilestoreBackend, DirectoryBackend, TestBackend]
)
def test_delete_entry(test_backend: _Backend):
    entry = test_backend.root.entries[0]
    test_backend.delete_entry(entry)

    with pytest.raises(EntryNotFoundError):
        test_backend.get_entry(entry.uuid)


@setup_test_stack(
    sources=["db/filestore.json"], backend_type=[FilestoreBackend, DirectoryBackend, TestBackend]
)
def test_search_entry(test_backend: _Backend):
    # Given an entry we know is in the backend
    results = test_backend.search(
        SearchTerm('description', 'eq', 'collection 1 defining some motor fields')
    )
    assert len(list(results)) == 1
    # Search by field name
    results = test_backend.search(
        SearchTerm('uuid', 'eq', UUID('ffd668d3-57d9-404e-8366-0778af7aee61'))
    )
    assert len(list(results)) == 1
    # Search by field name
    results = test_backend.search(
        SearchTerm('data', 'eq', 2)
    )
    assert len(list(results)) == 3
    # Search by field name
    results = test_backend.search(
        SearchTerm('uuid', 'eq', UUID('ecb42cdb-b703-4562-86e1-45bd67a2ab1a')),
        SearchTerm('data', 'eq', 2)
    )
    assert len(list(results)) == 1

    results = test_backend.search(
        SearchTerm('entry_type', 'eq', Snapshot)
    )
    assert len(list(results)) == 1

    results = test_backend.search(
        SearchTerm('entry_type', 'in', (Snapshot, Collection))
    )
    assert len(list(results)) == 2

    results = test_backend.search(
        SearchTerm('data', 'lt', 3)
    )
    assert len(list(results)) == 3

    results = test_backend.search(
        SearchTerm('data', 'gt', 3)
    )
    assert len(list(results)) == 1


@setup_test_stack(
    sources=["db/filestore.json"], backend_type=[FilestoreBackend, DirectoryBackend, TestBackend]
)
def test_fuzzy_search(test_backend: _Backend):
    results = list(test_backend.search(
        SearchTerm('description', 'like', 'motor'))
    )
    assert len(results) == 4

    results = list(test_backend.search(
        SearchTerm('description', 'like', 'motor field (?!PREC)'))
    )
    assert len(results) == 2

    results = list(test_backend.search(
        SearchTerm('uuid', 'like', '17cc6ebf'))
    )
    assert len(results) == 1


@setup_test_stack(
    sources=["db/filestore.json"], backend_type=[FilestoreBackend, DirectoryBackend, TestBackend]
)
def test_tag_search(test_backend: _Backend):
    entry_count = len(list(test_backend.search()))
    results = list(test_backend.search(
        SearchTerm('tags', 'gt', {})
    ))
    assert len(results) == entry_count

    smaller_tag_set = {0: {0}}
    bigger_tag_set = {0: {0, 1}}

    results[0].tags = smaller_tag_set
    results[1].tags = bigger_tag_set
    test_backend.update_entry(results[0])
    test_backend.update_entry(results[1])

    results = list(test_backend.search(
        SearchTerm('tags', 'gt', smaller_tag_set)
    ))
    assert len(results) == 2

    results = list(test_backend.search(
        SearchTerm('tags', 'gt', bigger_tag_set)
    ))
    assert len(results) == 1


@setup_test_stack(
    sources=["db/filestore.json"], backend_type=[FilestoreBackend, DirectoryBackend, TestBackend]
)
def test_search_error(test_backend: _Backend):
    with pytest.raises(TypeError):
        results = test_backend.search(
            SearchTerm('data', 'like', 5)
        )
        list(results)
    with pytest.raises(ValueError):
        results = test_backend.search(
            SearchTerm('data', 'near', 5)
        )
        list(results)


@setup_test_stack(
    sources=["db/filestore.json"], backend_type=[FilestoreBackend, DirectoryBackend, TestBackend]
)
def test_update_entry(test_backend: _Backend):
    # grab an entry from the database and modify it.
    entry = list(test_backend.search(
        SearchTerm('description', 'eq', 'collection 1 defining some motor fields')
    ))[0]
    old_uuid = entry.uuid

    entry.description = 'new_description'
    test_backend.update_entry(entry)
    new_entry = list(test_backend.search(
        SearchTerm('description', 'eq', 'new_description')
    ))[0]
    new_uuid = new_entry.uuid

    assert old_uuid == new_uuid

    # fail if we try to modify with a new entry
    p1 = Parameter()
    with pytest.raises(BackendError):
        test_backend.update_entry(p1)


# TODO: Assess if _gather_reachable should be upstreamed to _Backend
@setup_test_stack(
    sources=["linac_data"], backend_type=[FilestoreBackend, DirectoryBackend]
)
def test_gather_reachable(test_backend: _Backend):
    # snapshot
    reachable = test_backend._gather_reachable(UUID("06282731-33ea-4270-ba14-098872e627dc"))
    assert len(reachable) == 13
    assert UUID("927ef6cb-e45f-4175-aa5f-6c6eec1f3ae4") in reachable

    # works with UUID or Entry
    entry = test_backend.get_entry(UUID("06282731-33ea-4270-ba14-098872e627dc"))
    reachable = test_backend._gather_reachable(entry)
    assert len(reachable) == 13
    assert UUID("927ef6cb-e45f-4175-aa5f-6c6eec1f3ae4") in reachable


@setup_test_stack(
    sources=["linac_data"], backend_type=[TestBackend, FilestoreBackend],
)
def test_tags(test_backend: _Backend):
    tag_groups = test_backend.get_tags()
    dest_tags = {0: "SXR", 1: "HXR"}
    assert tag_groups[3][0] == 'Destination'
    assert tag_groups[3][2] == dest_tags

    new_tags = {0: "SXR-2", 1: "HXR", 2: "BSYD"}
    tag_groups[3][2] = new_tags
    test_backend.set_tags(tag_groups)
    assert test_backend.get_tags()[3][2] == new_tags
