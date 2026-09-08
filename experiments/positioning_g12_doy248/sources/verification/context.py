"""Explicit target and GPST calendar context; no orbital target state."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
import re


@dataclass(frozen=True)
class Context:
    target: str
    date_gpst: str
    start_s: int = 0
    samples: int = 11
    step_s: int = 30

    def __post_init__(self):
        if not re.fullmatch(r"G(?:0[1-9]|[12][0-9]|3[0-2])", self.target):
            raise ValueError("supported target is a GPS PRN G01 through G32")
        date.fromisoformat(self.date_gpst)
        if self.samples < 7 or self.samples % 2 != 1 or self.step_s <= 0 or self.start_s < 0:
            raise ValueError("invalid observation window")
        if self.start_s + (self.samples - 1) * self.step_s >= 86400:
            raise ValueError("one observation file may not cross its GPST day")

    @property
    def day(self):
        # UTC tzinfo is a calendar arithmetic carrier here, NOT a GPST->UTC
        # conversion. Values are always labelled GPST in scientific outputs.
        d = date.fromisoformat(self.date_gpst)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    @property
    def gps_week(self):
        return (self.day - datetime(1980, 1, 6, tzinfo=timezone.utc)).days // 7

    @property
    def sow_midnight(self):
        return ((self.day - datetime(1980, 1, 6, tzinfo=timezone.utc)).days % 7) * 86400

    @property
    def times(self):
        return tuple(self.start_s + i * self.step_s for i in range(self.samples))

    @property
    def central_s(self):
        return self.times[self.samples // 2]
