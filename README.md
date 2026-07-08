# hec-dss-reader

A small Python app for reading **HEC-DSS** files (the Hydrologic Engineering
Center Data Storage System used by HEC-HMS, HEC-RAS, HEC-ResSim, and other
USACE tools).

It wraps the official [`hecdss`](https://pypi.org/project/hecdss/) library
published by the U.S. Army Corps of Engineers and gives you a clean API and a
command-line tool to:

- open a `.dss` file,
- list its catalog of record pathnames, and
- read time-series and paired-data records as plain Python objects.

## Project layout

```
.
├── src/hec_dss_reader/
│   ├── __init__.py       # package exports
│   ├── reader.py         # DssReader / DssRecord — the core API
│   ├── cli.py            # command-line interface
│   └── __main__.py       # enables `python -m hec_dss_reader`
├── tests/
│   └── test_reader.py    # unit tests (run with a fake backend)
├── pyproject.toml        # packaging + entry point
├── requirements.txt
└── README.md
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or install the package itself (which also registers the `hec-dss-reader`
command):

```bash
pip install -e .
```

> **Note:** `hecdss` ships the native HEC-DSS libraries as prebuilt wheels for
> common platforms. If a wheel isn't available for your platform, see the
> [hecdss project page](https://pypi.org/project/hecdss/) for build options.

## Usage

### Command line

```bash
# List every pathname in the file
python -m hec_dss_reader path/to/file.dss

# Read one record by pathname
python -m hec_dss_reader path/to/file.dss --path "/BASIN/GAGE/FLOW//1DAY/OBS/"

# Read one record and print its values
python -m hec_dss_reader path/to/file.dss --path "/BASIN/GAGE/FLOW//1DAY/OBS/" --values

# Summarize every record in the file
python -m hec_dss_reader path/to/file.dss --all
```

If you installed the package, the same commands are available via the
`hec-dss-reader` script.

### As a library

```python
from hec_dss_reader import DssReader

with DssReader("model.dss") as dss:
    # Browse the catalog
    for pathname in dss.catalog():
        print(pathname)

    # Read a single record
    record = dss.read("/BASIN/GAGE/FLOW//1DAY/OBS/")
    print(record.summary())
    for time, value in zip(record.times, record.values):
        print(time, value)
```

## Development

Run the test suite (no real `.dss` file needed — the tests use a fake backend):

```bash
pip install -r requirements.txt
pytest
```

## License

MIT
