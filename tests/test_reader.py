"""Unit tests for hec_dss_reader.

These tests exercise the wrapper's normalization and control flow using a
fake DSS backend, so they run without a real .dss file or the native
``hecdss`` dependency installed.
"""

from datetime import date, datetime

import pytest

from hec_dss_reader.reader import DssReader, DssRecord, _coerce_datetime


class FakeTimeSeries:
    def __init__(self, values, times, units):
        self.values = values
        self.times = times
        self.units = units


class FakeCatalog:
    def __init__(self, paths):
        self.uncondensed_paths = paths


class FakeHecDss:
    """Stand-in for hecdss.HecDss for testing."""

    def __init__(self, records):
        self._records = records
        self.closed = False

    def get_catalog(self):
        return FakeCatalog(list(self._records.keys()))

    def get(self, pathname):
        return self._records[pathname]

    def close(self):
        self.closed = True


def _reader_with(records):
    reader = DssReader("fake.dss")
    reader._dss = FakeHecDss(records)
    return reader


def test_record_summary_and_len():
    rec = DssRecord(
        pathname="/A/B/FLOW//1DAY/OBS/",
        record_type="RegularTimeSeries",
        values=[1.0, 2.0, 3.0],
        units="cfs",
    )
    assert len(rec) == 3
    assert "cfs" in rec.summary()
    assert "3 values" in rec.summary()


def test_catalog_uses_uncondensed_paths():
    reader = _reader_with({"/A/B/C//E/F/": FakeTimeSeries([1], ["t"], "cfs")})
    assert reader.catalog() == ["/A/B/C//E/F/"]


def test_read_normalizes_record():
    ts = FakeTimeSeries([10.0, 20.0], ["2020-01-01", "2020-01-02"], "m")
    reader = _reader_with({"/X/Y/Z//1DAY/OBS/": ts})
    rec = reader.read("/X/Y/Z//1DAY/OBS/")
    assert rec.values == [10.0, 20.0]
    assert rec.times == ["2020-01-01", "2020-01-02"]
    assert rec.units == "m"
    assert rec.record_type == "FakeTimeSeries"


def test_read_all_yields_error_record_on_failure():
    class Boom:
        def get(self, _):
            raise ValueError("bad record")

        def get_catalog(self):
            return FakeCatalog(["/bad/path/"])

        def close(self):
            pass

    reader = DssReader("fake.dss")
    reader._dss = Boom()
    records = list(reader.read_all())
    assert len(records) == 1
    assert records[0].record_type == "error"


def test_requires_open():
    reader = DssReader("fake.dss")
    with pytest.raises(RuntimeError):
        reader.catalog()


def test_coerce_datetime_formats():
    assert _coerce_datetime(datetime(2020, 1, 2, 3, 4)) == datetime(2020, 1, 2, 3, 4)
    assert _coerce_datetime(date(2020, 1, 2)) == datetime(2020, 1, 2)
    assert _coerce_datetime("2020-01-02") == datetime(2020, 1, 2)
    assert _coerce_datetime("2020-01-02 03:04:05") == datetime(2020, 1, 2, 3, 4, 5)
    assert _coerce_datetime("") is None
    assert _coerce_datetime("not-a-date") is None


def test_rows_filters_by_date_range():
    rec = DssRecord(
        pathname="/A/B/FLOW//1DAY/OBS/",
        record_type="RegularTimeSeries",
        values=[1.0, 2.0, 3.0, 4.0],
        times=[
            datetime(2020, 1, 1),
            datetime(2020, 1, 2),
            datetime(2020, 1, 3),
            datetime(2020, 1, 4),
        ],
        units="cfs",
    )
    rows = rec.rows(start=date(2020, 1, 2), end=date(2020, 1, 3))
    assert [v for _, v in rows] == [2.0, 3.0]


def test_rows_without_bounds_returns_all():
    rec = DssRecord(
        pathname="/A/B/C/",
        record_type="ts",
        values=[10.0, 20.0],
        times=[datetime(2021, 5, 1), datetime(2021, 6, 1)],
    )
    assert len(rec.rows()) == 2


def test_rows_without_times_are_not_filtered():
    rec = DssRecord(
        pathname="/A/B/STAGE-FLOW///PAIRED/",
        record_type="PairedData",
        values=[100.0, 200.0],
        times=[],
    )
    rows = rec.rows(start=date(2020, 1, 1), end=date(2020, 12, 31))
    assert [v for _, v in rows] == [100.0, 200.0]


def test_close_closes_backend():
    reader = _reader_with({})
    backend = reader._dss
    reader.close()
    assert backend.closed is True
    assert reader._dss is None
