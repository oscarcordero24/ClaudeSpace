"""Command-line interface for hec_dss_reader.

Examples::

    python -m hec_dss_reader path/to/file.dss              # list the catalog
    python -m hec_dss_reader path/to/file.dss --path "/A/B/C//E/F/"  # dump one record
    python -m hec_dss_reader path/to/file.dss --all        # dump every record
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .reader import DssReader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hec-dss-reader",
        description="Read records from a HEC-DSS file.",
    )
    parser.add_argument("file", help="Path to the .dss file to read.")
    parser.add_argument(
        "--path",
        "-p",
        help="Read and print a single record by its DSS pathname.",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Read and summarize every record in the file.",
    )
    parser.add_argument(
        "--values",
        action="store_true",
        help="When printing a record, also print its values.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _print_record(rec, show_values: bool) -> None:
    print(rec.summary())
    if show_values:
        for i, value in enumerate(rec.values):
            stamp = rec.times[i] if i < len(rec.times) else ""
            if stamp != "":
                print(f"  {stamp}\t{value}")
            else:
                print(f"  {value}")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    try:
        with DssReader(args.file) as dss:
            if args.path:
                _print_record(dss.read(args.path), args.values)
            elif args.all:
                for rec in dss.read_all():
                    _print_record(rec, args.values)
            else:
                paths = dss.catalog()
                print(f"{len(paths)} record(s) in {args.file}:")
                for path in paths:
                    print(f"  {path}")
    except FileNotFoundError:
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the user
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
