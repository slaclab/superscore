import logging
from typing import Generator, Iterable

import requests

from superscore.backends import SearchTermType, _Backend
from superscore.model import Entry, Parameter, Snapshot
from superscore.type_hints import TagDef

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "TAGS": "/v1/tags",
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
                    pass
                else:
                    entries = self._get_all_pvs()
        for entry in entries:
            conditions = []
            for attr, op, target in search_terms:
                if attr == "ancestor":
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
        r.raise_for_status()
        return r.json()["payload"]["id"]

    def update_tag_group(self, group_id, name="", description=""):
        body = {}
        if name:
            body["name"] = name
        if description:
            body["description"] = description
        r = requests.put(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", json=body)
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        r.raise_for_status()

    def delete_tag_group(self, group_id):
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}", params={"force": True})
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        r.raise_for_status()

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
        r.raise_for_status()

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
        r.raise_for_status()

    def delete_tag_from_group(self, group_id, tag_id):
        r = requests.delete(self.address + ENDPOINTS["TAGS"] + f"/{group_id}/tags/{tag_id}")
        logger.debug(f"{r.request.method} {r.url} with response {r.status_code} ({r.reason})")
        r.raise_for_status()

    def _get_all_pvs(self) -> Iterable[Parameter]:
        r = requests.get(self.address + "/v1/pvs")
        r.raise_for_status()
        return [
            Parameter(
                uuid=d["id"],
                pv_name=d["pvName"],
                description=d["description"],
                abs_tolerance=d["absTolerance"],
                rel_tolerance=d["relTolerance"],
                read_only=d["readOnly"],
                creation_time=d["createdDate"],
            ) for d in r.json()["payload"]
        ]

    def get_meta_pvs(self) -> Iterable[Parameter]:
        return []

    def set_meta_pvs(self, meta_pvs: Iterable[Parameter]) -> None:
        return
