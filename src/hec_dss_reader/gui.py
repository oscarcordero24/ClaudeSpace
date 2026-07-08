"""A small Tkinter GUI for reading HEC-DSS files.

Features:
- an "Open DSS File..." button that pops a file browser,
- a dropdown to pick which record (pathname) to view,
- start/end date pickers (using ``tkcalendar`` when available, otherwise
  plain ``YYYY-MM-DD`` text entries), and
- a results table (``ttk.Treeview``) showing the time/value pairs in range.

Run it with::

    python -m hec_dss_reader.gui
    # or, after `pip install -e .`:
    hec-dss-reader-gui
"""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from .reader import DssReader, DssRecord, _coerce_datetime

# tkcalendar gives a real drop-down calendar; fall back to text entry if it
# isn't installed so the app still runs.
try:
    from tkcalendar import DateEntry  # type: ignore

    _HAS_TKCALENDAR = True
except Exception:  # pragma: no cover - depends on environment
    DateEntry = None  # type: ignore
    _HAS_TKCALENDAR = False


class _DatePicker(ttk.Frame):
    """A calendar date picker, degrading to a text entry when tkcalendar is absent."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        if _HAS_TKCALENDAR:
            self._widget = DateEntry(self, date_pattern="yyyy-mm-dd", width=12)
            self._widget.pack()
        else:
            self._var = tk.StringVar()
            self._widget = ttk.Entry(self, textvariable=self._var, width=14)
            self._widget.pack()

    def set_date(self, value: date) -> None:
        if _HAS_TKCALENDAR:
            self._widget.set_date(value)
        else:
            self._var.set(value.strftime("%Y-%m-%d"))

    def get_date(self) -> Optional[date]:
        if _HAS_TKCALENDAR:
            return self._widget.get_date()
        text = self._var.get().strip()
        if not text:
            return None
        dt = _coerce_datetime(text)
        if dt is None:
            raise ValueError(f"Could not parse date: {text!r} (use YYYY-MM-DD)")
        return dt.date()


class DssApp(ttk.Frame):
    """Main application frame."""

    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=10)
        self.master = master
        self.pack(fill=tk.BOTH, expand=True)

        self.file_path: Optional[str] = None
        self._catalog: List[str] = []

        self._build_widgets()

    # -- layout ------------------------------------------------------------

    def _build_widgets(self) -> None:
        self.master.title("HEC-DSS Reader")
        self.master.minsize(720, 480)

        # Row 1: open file
        top = ttk.Frame(self)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(top, text="Open DSS File...", command=self.open_file).pack(
            side=tk.LEFT
        )
        self.file_label = ttk.Label(top, text="No file loaded", foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=8)

        # Row 2: record picker
        record_row = ttk.Frame(self)
        record_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(record_row, text="Record:").pack(side=tk.LEFT)
        self.record_var = tk.StringVar()
        self.record_combo = ttk.Combobox(
            record_row, textvariable=self.record_var, state="readonly", width=70
        )
        self.record_combo.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        # Row 3: date range + load
        date_row = ttk.Frame(self)
        date_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(date_row, text="Start:").pack(side=tk.LEFT)
        self.start_picker = _DatePicker(date_row)
        self.start_picker.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(date_row, text="End:").pack(side=tk.LEFT)
        self.end_picker = _DatePicker(date_row)
        self.end_picker.pack(side=tk.LEFT, padx=(4, 12))
        self.start_picker.set_date(date(date.today().year, 1, 1))
        self.end_picker.set_date(date.today())
        ttk.Button(date_row, text="Load Data", command=self.load_data).pack(
            side=tk.LEFT, padx=4
        )

        if not _HAS_TKCALENDAR:
            ttk.Label(
                self,
                text="(Install 'tkcalendar' for a pop-up calendar; "
                "using YYYY-MM-DD text entry.)",
                foreground="gray",
            ).pack(anchor=tk.W, pady=(0, 4))

        # Results table
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("time", "value")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=15
        )
        self.tree.heading("time", text="Date / Time")
        self.tree.heading("value", text="Value")
        self.tree.column("time", width=260, anchor=tk.W)
        self.tree.column("value", width=140, anchor=tk.E)

        yscroll = ttk.Scrollbar(
            table_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Status bar
        self.status = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(fill=tk.X, pady=(8, 0))

    # -- actions -----------------------------------------------------------

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open HEC-DSS file",
            filetypes=[("HEC-DSS files", "*.dss"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with DssReader(path) as dss:
                self._catalog = dss.catalog()
        except ImportError as exc:
            messagebox.showerror("Missing dependency", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - report to the user
            messagebox.showerror("Could not open file", str(exc))
            return

        self.file_path = path
        self.file_label.config(text=path, foreground="black")
        self.record_combo["values"] = self._catalog
        if self._catalog:
            self.record_combo.current(0)
        self._clear_table()
        self._set_status(f"Loaded catalog: {len(self._catalog)} record(s)")

    def load_data(self) -> None:
        if not self.file_path:
            messagebox.showinfo("No file", "Open a DSS file first.")
            return
        pathname = self.record_var.get()
        if not pathname:
            messagebox.showinfo("No record", "Choose a record to load.")
            return

        try:
            start = self.start_picker.get_date()
            end = self.end_picker.get_date()
        except ValueError as exc:
            messagebox.showerror("Invalid date", str(exc))
            return
        if start and end and start > end:
            messagebox.showerror(
                "Invalid range", "Start date must be on or before the end date."
            )
            return

        try:
            with DssReader(self.file_path) as dss:
                record: DssRecord = dss.read(pathname)
        except Exception as exc:  # noqa: BLE001 - report to the user
            messagebox.showerror("Could not read record", str(exc))
            return

        self._populate_table(record, start, end)

    # -- table helpers -----------------------------------------------------

    def _clear_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _populate_table(
        self, record: DssRecord, start: Optional[date], end: Optional[date]
    ) -> None:
        self._clear_table()
        rows = record.rows(start, end)
        unit = f" ({record.units})" if record.units else ""
        self.tree.heading("value", text=f"Value{unit}")
        for stamp, value in rows:
            self.tree.insert("", tk.END, values=(self._format_time(stamp), value))
        self._set_status(
            f"{record.pathname}: showing {len(rows)} of {len(record.values)} value(s)"
        )

    @staticmethod
    def _format_time(stamp) -> str:
        if isinstance(stamp, datetime):
            return stamp.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(stamp, date):
            return stamp.strftime("%Y-%m-%d")
        return str(stamp)


def main() -> int:
    root = tk.Tk()
    DssApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
