"""hec_dss_reader — a small app for reading HEC-DSS files.

Wraps the official USACE ``hecdss`` library to make it easy to open a DSS
file, list its catalog of records (pathnames), and pull time-series and
paired-data records out as plain Python objects.
"""

from .reader import DssReader, DssRecord

__all__ = ["DssReader", "DssRecord"]
__version__ = "0.1.0"
