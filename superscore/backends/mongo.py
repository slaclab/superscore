import logging
from typing import Generator, Iterable

import requests

from superscore.backends import SearchTermType, _Backend
from superscore.errors import BackendError
from superscore.model import (Entry, Parameter, Setpoint, Severity, Snapshot,
                              Status)
from superscore.type_hints import TagDef, TagSet

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "TAGS": "/v1/tags",
    "PVS": "/v1/pvs",
    "PVS_MULTI": "/v1/pvs/multi",
}


class MongoBackend(_Backend):
    """An integration layer between the Client and a MongoDB instance"""

    def __init__(self, address: str):
        super().__init__()
        self.address = address

    def search(self, *search_terms: SearchTermType) -> Generator[Entry, None, None]:
        entries = []
        for attr, op, target in search_terms:
            if attr == "entry_type":
                if target is Snapshot:
                    entries = self.get_snapshots()
                else:
                    entries = self.get_all_pvs()
        for entry in entries:
            conditions = []
            for attr, op, target in search_terms:
                if attr == "entry_type":
                    conditions.append(isinstance(entry, target))
                elif attr == "ancestor":
                    pass
                else:
                    try:
                        # check entry attribute by name
                        value = getattr(entry, attr)
                        conditions.append(self.compare(op, value, target))
                    except AttributeError:
                        conditions.append(False)
            if all(conditions):
                yield entry

    def get_tags(self) -> TagDef:
        tag_def = {}
        r = requests.get(self.address + ENDPOINTS["TAGS"])
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        if r.ok:
            for dct in r.json()["payload"]:
                idx = dct['id']
                name = dct['name']
                r = requests.get(self.address + ENDPOINTS["TAGS"] + f"/{idx}")
                logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
                if r.ok:
                    dct = r.json()["payload"][0]
                    description = dct["description"]
                    tags = {d["id"]: d["name"] for d in dct["tags"]}
                    tag_def[idx] = [name, description, tags]
        return tag_def

    def add_tag_group(self, name, description) -> int:
        body = {
            "name": name,
            "description": description,
        }
        r = requests.post(self.address + ENDPOINTS["TAGS"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)
        return r.json()["payload"]["id"]

    def update_tag_group(self, group_id, name="", description=""):
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def delete_tag_group(self, group_id):
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", params={"force": True})
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def add_tag_to_group(self, group_id: int, name, description=""):
        params = {
            "groupId": group_id,
        }
        body = {
            "name": name,
            "description": description,
        }
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags", params=params, json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def update_tag_in_group(self, group_id, tag_id, name="", description=""):
        params = {
            "groupId": group_id,
            "tagId": tag_id,
        }
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags/{tag_id}", params=params, json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def delete_tag_from_group(self, group_id, tag_id):
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags/{tag_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def add_pv(
        self,
        pv_name,
        description,
        tags: TagSet = None,
        abs_tolerance=0,
        rel_tolerance=0,
        read_only=False
    ) -> Parameter:
        body = {
            "pvName": pv_name,
            "description": description,
            "absTolerance": abs_tolerance,
            "relTolerance": rel_tolerance,
            "tags": self._pack_tags(tags) if tags else [],
            "readOnly": read_only,
        }
        r = requests.post(self.address + ENDPOINTS["PVS"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)
        pv_dict = r.json()["payload"]
        return self._unpack_pv(pv_dict)

    def add_multiple_pvs(self, pvs: Iterable[Parameter]):
        body = []
        for pv in pvs:
            body.append(
                {
                    "pvName": pv.pv_name,
                    "description": pv.description,
                    "absTolerance": pv.abs_tolerance,
                    "relTolerance": pv.rel_tolerance,
                    "tags": self._pack_tags(pv.tags),
                    "readOnly": pv.read_only,
                }
            )
        r = requests.post(self.address + ENDPOINTS["PVS_MULTI"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def update_pv(self, pv_id, pv_name="", description="", tags=None, abs_tolerance=None, rel_tolerance=None, read_only=None) -> None:
        body = {}
        if pv_name:
            body["pvName"] = pv_name
        if description:
            body["description"] = description
        if tags:
            body["tags"] = self._pack_tags(tags)
        if abs_tolerance is not None:
            body["absTolerance"] = abs_tolerance
        if rel_tolerance is not None:
            body["relTolerance"] = rel_tolerance
        if read_only is not None:
            body["readOnly"] = read_only
        r = requests.put(self.address + ENDPOINTS["PVS"] + f"/{pv_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def archive_pv(self, pv_id) -> None:
        r = requests.delete(self.address + ENDPOINTS["PVS"] + f"/{pv_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)

    def get_all_pvs(self) -> Iterable[Parameter]:
        r = requests.get(self.address + "/v1/pvs")
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)
        return [self._unpack_pv(d) for d in r.json()["payload"]]

    def add_snapshot(self, snapshot: Snapshot) -> None:
        r = requests.post(
            self.address + "/v1/snapshots",
            json=self._pack_snapshot(snapshot)
        )
        if not r.status_code == requests.codes.ok:
            pass

    def get_snapshots(self, uuid=None, title="", tags=None, meta_pvs=None) -> Iterable[Snapshot]:
        if uuid:
            r = requests.get(self.address + f"/v1/snapshots/{uuid}")
            if r.status_code == requests.codes.ok:
                snapshot_dict = r.json()["payload"]
                return self._unpack_snapshot(snapshot_dict)

        tags = tags or {}
        meta_pvs = meta_pvs or []
        r = requests.get(
            self.address + "/v1/snapshots",
            params={
                "title": title,
                "tags": tags,
                "metadataPVs": meta_pvs,
            }
        )
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise BackendError(e)
        return [self._unpack_snapshot_metadata(snapshot_dict) for snapshot_dict in r.json()["payload"]]

    def update_snapshot(self) -> None:
        raise NotImplementedError

    def get_snapshots_in_date_range(self) -> None:
        raise NotImplementedError

    def get_snapshots_in_index_range(self) -> None:
        raise NotImplementedError

    def get_meta_pvs(self) -> Iterable[Parameter]:
        return []

    def set_meta_pvs(self, meta_pvs: Iterable[Parameter]) -> None:
        return

    def _unpack_tags(self, tag_list):
        tag_def = self.get_tags()
        id_to_group = {
            tag_id: group for group, group_def in tag_def.items() for tag_id in group_def[2]
        }
        tag_set = {}
        for d in tag_list:
            group = id_to_group[d["id"]]
            if group not in tag_set:
                tag_set[group] = set()
            tag_set[group].add(d["id"])
        return tag_set

    @staticmethod
    def _pack_tags(tags: TagSet):
        return [tag for group in tags.values() for tag in group]

    def _unpack_pv(self, pv_dict):
        return Parameter(
            uuid=pv_dict["id"],
            pv_name=pv_dict["pvName"],
            description=pv_dict["description"],
            tags=self._unpack_tags(pv_dict["tags"]),
            abs_tolerance=pv_dict["absTolerance"],
            rel_tolerance=pv_dict["relTolerance"],
            read_only=pv_dict["readOnly"],
            creation_time=pv_dict["createdDate"],
        )

    @staticmethod
    def _unpack_snapshot_metadata(metadata_dict):
        return Snapshot(
            uuid=metadata_dict["id"],
            title=metadata_dict["title"],
            description=metadata_dict["description"],
            tags=metadata_dict["tags"],
            meta_pvs=[
                Setpoint(
                    pv_name=pv["pvName"],
                    data=pv["data"],
                    status=getattr(Status, pv["status"]),
                    severity=getattr(Severity, pv["severity"]),
                    creation_time=pv["createdDate"],
                ) for pv in metadata_dict["metadataPVs"]
            ],
        )

    @staticmethod
    def _unpack_snapshot(snapshot_dict) -> Snapshot:
        return Snapshot(
            uuid=snapshot_dict["id"],
            title=snapshot_dict["title"],
            description=snapshot_dict["description"],
            tags=snapshot_dict["tags"],
            children=[
                Setpoint(
                    pv_name=pv["pvName"],
                    data=pv["data"],
                    status=getattr(Status, pv["status"]),
                    severity=getattr(Severity, pv["severity"]),
                    creation_time=pv["createdDate"],
                ) for pv in snapshot_dict["data"]
            ],
            creation_time=snapshot_dict["createdDate"],
        )

    @staticmethod
    def _pack_snapshot(snapshot: Snapshot) -> dict:
        return {
            "title": snapshot.title,
            "description": snapshot.description,
            "values": [
                {
                    "pvName": pv.pv_name,
                    "status": pv.status.name,
                    "severity": pv.severity.name,
                    "data": pv.data,
                } for pv in snapshot.children
            ]
        }
