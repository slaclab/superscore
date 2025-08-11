"""Classes for representing data"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional
from uuid import UUID, uuid4

from superscore.type_hints import AnyEpicsType, TagSet
from superscore.utils import utcnow

logger = logging.getLogger(__name__)


class Severity(Enum):
    NO_ALARM = 0
    MINOR = auto()
    MAJOR = auto()
    INVALID = auto()


class Status(Enum):
    NO_ALARM = 0
    READ = auto()
    WRITE = auto()
    HIHI = auto()
    HIGH = auto()
    LOLO = auto()
    LOW = auto()
    STATE = auto()
    COS = auto()
    COMM = auto()
    TIMEOUT = auto()
    HWLIMIT = auto()
    CALC = auto()
    SCAN = auto()
    LINK = auto()
    SOFT = auto()
    BAD_SUB = auto()
    UDF = auto()
    DISABLE = auto()
    SIMM = auto()
    READ_ACCESS = auto()
    WRITE_ACCESS = auto()


@dataclass
class EpicsData:
    """Unified EPICS data type for holding data and relevant metadata"""
    data: Optional[AnyEpicsType] = None
    status: Severity = Status.UDF
    severity: Status = Severity.INVALID
    timestamp: datetime = field(default_factory=utcnow)

    # Extra metadata
    units: Optional[str] = None
    precision: Optional[int] = None
    upper_ctrl_limit: Optional[float] = None
    lower_ctrl_limit: Optional[float] = None
    lower_alarm_limit: Optional[float] = None  # LOLO
    upper_alarm_limit: Optional[float] = None  # HIHI
    lower_warning_limit: Optional[float] = None  # LOW
    upper_warning_limit: Optional[float] = None  # HIGH
    enums: Optional[list[str]] = None


@dataclass
class PV:
    """"""
    uuid: UUID = field(default_factory=uuid4)
    description: str = ""
    setpoint: str = ""
    readback: str = ""
    config: str = ""
    setpoint_data: EpicsData = field(default_factory=EpicsData)
    readback_data: EpicsData = field(default_factory=EpicsData)
    config_data: EpicsData = field(default_factory=EpicsData)
    device: str = ""
    tags: TagSet = field(default_factory=dict)
    abs_tolerance: Optional[float] = None
    rel_tolerance: Optional[float] = None
    creation_time: datetime = field(default_factory=utcnow)
    # timeout: Optional[float] = None

    def __post_init__(self) -> None:
        if isinstance(self.uuid, str):
            self.uuid = UUID(self.uuid)
        return


@dataclass
class Snapshot:
    """"""
    uuid: UUID = field(default_factory=uuid4)
    description: str = ""
    title: str = ""
    pvs: List[PV] = field(default_factory=list)
    # tags: TagSet = field(default_factory=dict)
    creation_time: datetime = field(default_factory=utcnow)
    meta_pvs: List[PV] = field(default_factory=list)
