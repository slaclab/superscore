import logging
from datetime import UTC, datetime, timedelta
from typing import Iterable

import requests

from superscore.backends import SearchTermType, _Backend
from superscore.errors import BackendError
from superscore.model import PV, EpicsData, Severity, Snapshot, Status
from superscore.type_hints import TagDef, TagSet

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "TAGS": "/v1/tags",
    "PVS": "/v1/pvs",
}


class MongoBackend(_Backend):
    """An integration layer between the Client and a MongoDB instance"""

    def __init__(self, address: str):
        super().__init__()
        self.address = address
        self._tag_cache = {}
        self._last_tag_fetch = datetime.now() - timedelta(minutes=1)

    def search(self, *search_terms: SearchTermType):
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
        if datetime.now() - self._last_tag_fetch > timedelta(minutes=1):
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
                        description = dct.get("description", "")
                        tags = {d["id"]: d["name"] for d in dct["tags"]}
                        tag_def[idx] = [name, description, tags]
            self._tag_cache = tag_def
            self._last_tag_fetch = datetime.now()
        return self._tag_cache

    def add_tag_group(self, name, description) -> int:
        body = {
            "name": name,
            "description": description,
        }
        r = requests.post(self.address + ENDPOINTS["TAGS"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)
        return r.json()["payload"]["id"]

    def update_tag_group(self, group_id, name="", description=""):
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def delete_tag_group(self, group_id):
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", params={"force": True})
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

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
        self._raise_for_status(r)

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
        self._raise_for_status(r)

    def delete_tag_from_group(self, group_id, tag_id):
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags/{tag_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def add_pv(
        self,
        setpoint,
        readback,
        description,
        tags: TagSet = None,
        abs_tolerance=0,
        rel_tolerance=0,
        config_address=None,
    ) -> PV:
        body = {
            "setpointAddress": setpoint,
            "readbackAddress": readback,
            "configAddress": config_address,
            "description": description,
            "absTolerance": abs_tolerance,
            "relTolerance": rel_tolerance,
            "tags": self._pack_tags(tags) if tags else [],
            "readOnly": False,
        }
        r = requests.post(self.address + ENDPOINTS["PVS"], json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)
        pv_dict = r.json()["payload"]
        return self._unpack_pv(pv_dict)

    def update_pv(self, pv_id, setpoint="", description="", tags=None, abs_tolerance=None, rel_tolerance=None) -> None:
        body = {}
        if setpoint:
            body["setpointAddress"] = setpoint
        if description:
            body["description"] = description
        if tags:
            body["tags"] = self._pack_tags(tags)
        if abs_tolerance is not None:
            body["absTolerance"] = abs_tolerance
        if rel_tolerance is not None:
            body["relTolerance"] = rel_tolerance
        body["readOnly"] = False
        r = requests.put(self.address + ENDPOINTS["PVS"] + f"/{pv_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def archive_pv(self, pv_id) -> None:
        r = requests.delete(self.address + ENDPOINTS["PVS"] + f"/{pv_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        self._raise_for_status(r)

    def get_all_pvs(self) -> Iterable[PV]:
        r = requests.get(self.address + "/v1/pvs")
        self._raise_for_status(r)
        return [self._unpack_pv(d) for d in r.json()["payload"]]

    def add_snapshot(self, snapshot: Snapshot) -> None:
        r = requests.post(
            self.address + "/v1/snapshots",
            json=self._pack_snapshot(snapshot)
        )
        self._raise_for_status(r)

    def get_snapshots(self, uuid=None, title="", tags=None, meta_pvs=None) -> Iterable[Snapshot]:
        if uuid:
            r = requests.get(self.address + f"/v1/snapshots/{uuid}")
            self._raise_for_status(r)
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
        self._raise_for_status(r)
        return [self._unpack_snapshot_metadata(snapshot_dict) for snapshot_dict in r.json()["payload"]]

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        r = requests.delete(
            self.address + f"/v1/snapshots/{snapshot.uuid}",
            params={
                "deleteData": False,
            }
        )
        self._raise_for_status(r)

    def get_snapshots_in_date_range(self) -> None:
        raise NotImplementedError

    def get_snapshots_in_index_range(self) -> None:
        raise NotImplementedError

    def get_meta_pvs(self) -> Iterable[PV]:
        return []

    def set_meta_pvs(self, meta_pvs: Iterable[PV]) -> None:
        return

    @staticmethod
    def _raise_for_status(response):
        """Wraps response errors from the requests package in an
        app-specific error class"""
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # server response can have "errorMessage" or "message" key depending on error
            message = response.json().get("errorMessage", "") or response.json().get("message", e)
            raise BackendError(message)

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
        return PV(
            uuid=pv_dict["id"],
            setpoint=pv_dict.get("setpointAddress"),
            readback=pv_dict.get("readbackAddress"),
            config=pv_dict.get("configAddress"),
            description=pv_dict["description"],
            tags=self._unpack_tags(pv_dict["tags"]),
            abs_tolerance=pv_dict["absTolerance"],
            rel_tolerance=pv_dict["relTolerance"],
            creation_time=datetime.fromisoformat(pv_dict["createdDate"]).replace(tzinfo=UTC),
        )

    @staticmethod
    def _unpack_snapshot_metadata(metadata_dict):
        return Snapshot(
            uuid=metadata_dict["id"],
            title=metadata_dict["title"],
            description=metadata_dict["description"],
            # tags=metadata_dict["tags"],
            meta_pvs=[
                PV(
                    setpoint=pv["setpointAddress"],
                    data=pv["data"],
                    status=getattr(Status, pv["status"]),
                    severity=getattr(Severity, pv["severity"]),
                    creation_time=datetime.fromisoformat(pv["createdDate"]).replace(tzinfo=UTC),
                ) for pv in metadata_dict["metadataPVs"]
            ],
            creation_time=datetime.fromisoformat(metadata_dict["createdDate"]).replace(tzinfo=UTC),
        )

    @staticmethod
    def _unpack_snapshot(snapshot_dict) -> Snapshot:
        return Snapshot(
            uuid=snapshot_dict["id"],
            title=snapshot_dict["title"],
            description=snapshot_dict["description"],
            # tags=snapshot_dict["tags"],
            pvs=[
                PV(
                    setpoint=pv["pvName"],
                    setpoint_data=EpicsData(
                        data=pv.get("data", None),
                        status=getattr(Status, pv["status"]),
                        severity=getattr(Severity, pv["severity"]),
                        timestamp=datetime.fromisoformat(pv["createdDate"]).replace(tzinfo=UTC),
                    )
                ) for pv in snapshot_dict["data"]
            ],
            creation_time=datetime.fromisoformat(snapshot_dict["createdDate"]).replace(tzinfo=UTC),
        )

    @staticmethod
    def _pack_snapshot(snapshot: Snapshot) -> dict:
        return {
            "title": snapshot.title,
            "description": snapshot.description,
            "values": [
                {
                    "pvName": pv.setpoint,
                    "status": pv.setpoint_data.status.name,
                    "severity": pv.setpoint_data.severity.name,
                    "data": pv.setpoint_data.data,
                } for pv in snapshot.pvs
            ],
        }
