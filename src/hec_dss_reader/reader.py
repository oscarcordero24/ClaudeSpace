"""Read records out of a HEC-DSS file.

This module is a thin, friendly wrapper around the official ``hecdss``
package published by the U.S. Army Corps of Engineers (USACE). It focuses on
the read side: opening a file, browsing its catalog, and returning records as
simple dataclasses that are easy to print, iterate, or convert to other
formats.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterator, List, Optional, Tuple


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """Best-effort conversion of a DSS time stamp into a ``datetime``.

    Handles ``datetime``/``date`` objects and a few common string formats.
    Returns ``None`` when the value can't be interpreted as a time.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d%b%Y %H:%M:%S",
        "%d%b%Y:%H%M",
        "%d %b %Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@dataclass
class DssRecord:
    """A single record read from a DSS file.

    Attributes:
        pathname: The full DSS pathname, e.g. ``/A/B/C/D/E/F/``.
        record_type: A short label describing the record ("regular-time-series",
            "paired-data", ...).
        values: The primary numeric values for the record.
        times: Time stamps for time-series records (empty otherwise).
        units: The unit string reported by DSS, if any.
        raw: The underlying object returned by ``hecdss`` for callers who need
            access to fields this wrapper does not surface.
    """

    pathname: str
    record_type: str
    values: List[float] = field(default_factory=list)
    times: List[Any] = field(default_factory=list)
    units: Optional[str] = None
    raw: Any = None

    def __len__(self) -> int:
        return len(self.values)

    def summary(self) -> str:
        """Return a one-line, human-readable summary of the record."""
        unit = f" [{self.units}]" if self.units else ""
        return (
            f"{self.pathname}  ({self.record_type}, "
            f"{len(self.values)} values{unit})"
        )

    def rows(
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> List[Tuple[Any, Any]]:
        """Return ``(time, value)`` pairs, optionally filtered by date range.

        ``start`` and ``end`` may be ``date`` or ``datetime`` objects. A pair is
        kept when its (coerced) time stamp falls on/after ``start`` and
        on/before ``end``; either bound may be omitted. Records without usable
        time stamps (e.g. paired data) are returned unfiltered, pairing each
        value with its raw time entry (or index when there are no times).
        """
        start_dt = _coerce_datetime(start) if start is not None else None
        end_dt = _coerce_datetime(end) if end is not None else None

        pairs: List[Tuple[Any, Any]] = []
        for i, value in enumerate(self.values):
            stamp = self.times[i] if i < len(self.times) else None
            ts = _coerce_datetime(stamp)
            if ts is not None:
                if start_dt is not None and ts < start_dt:
                    continue
                if end_dt is not None and ts > end_dt:
                    continue
                pairs.append((stamp, value))
            else:
                # No usable time stamp: keep the value, don't date-filter it.
                pairs.append((stamp if stamp is not None else i, value))
        return pairs


class DssReader(AbstractContextManager):
    """Open a HEC-DSS file for reading.

    Usage::

        with DssReader("model.dss") as dss:
            for path in dss.catalog():
                print(path)
            rec = dss.read("/BASIN/GAGE/FLOW//1DAY/OBS/")
            print(rec.summary())
    """

    def __init__(self, path: str):
        self.path = path
        self._dss = None

    # -- lifecycle ---------------------------------------------------------

    def open(self) -> "DssReader":
        """Open the underlying DSS file. Returns self for chaining."""
        try:
            from hecdss import HecDss
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ImportError(
                "The 'hecdss' package is required to read DSS files. "
                "Install it with 'pip install hecdss'."
            ) from exc

        self._dss = HecDss(self.path)
        return self

    def close(self) -> None:
        """Close the underlying DSS file if it is open."""
        if self._dss is not None:
            close = getattr(self._dss, "close", None)
            if callable(close):
                close()
            self._dss = None

    def __enter__(self) -> "DssReader":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- reading -----------------------------------------------------------

    def _require_open(self):
        if self._dss is None:
            raise RuntimeError(
                "DSS file is not open. Use 'with DssReader(path) as dss:' "
                "or call .open() first."
            )
        return self._dss

    def catalog(self) -> List[str]:
        """Return the list of pathnames stored in the file."""
        dss = self._require_open()
        cat = dss.get_catalog()
        # hecdss returns a Catalog object; its pathnames are iterable.
        uncondensed = getattr(cat, "uncondensed_paths", None)
        if uncondensed is not None:
            return list(uncondensed)
        return [str(p) for p in cat]

    def read(self, pathname: str) -> DssRecord:
        """Read a single record by its pathname."""
        dss = self._require_open()
        obj = dss.get(pathname)
        return self._to_record(pathname, obj)

    def read_all(self) -> Iterator[DssRecord]:
        """Yield every record in the file in catalog order."""
        for pathname in self.catalog():
            try:
                yield self.read(pathname)
            except Exception as exc:  # noqa: BLE001 - keep iterating on bad records
                yield DssRecord(
                    pathname=pathname,
                    record_type="error",
                    values=[],
                    raw=exc,
                )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _to_record(pathname: str, obj: Any) -> DssRecord:
        """Normalize a hecdss return object into a DssRecord."""
        values = getattr(obj, "values", None)
        times = getattr(obj, "times", None)
        units = getattr(obj, "units", None)

        record_type = type(obj).__name__ or "unknown"

        def _listify(seq):
            if seq is None:
                return []
            try:
                return list(seq)
            except TypeError:
                return [seq]

        return DssRecord(
            pathname=pathname,
            record_type=record_type,
            values=_listify(values),
            times=_listify(times),
            units=units,
            raw=obj,
        )
