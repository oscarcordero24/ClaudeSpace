"""Unit tests for hec_dss_reader.

These tests exercise the wrapper's normalization and control flow using a
fake DSS backend, so they run without a real .dss file or the native
``hecdss`` dependency installed.
"""

import pytest

from hec_dss_reader.reader import DssReader, DssRecord


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


def test_close_closes_backend():
    reader = _reader_with({})
    backend = reader._dss
    reader.close()
    assert backend.closed is True
    assert reader._dss is None
