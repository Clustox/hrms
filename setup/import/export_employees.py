"""Convert an employee xlsx (HR master-data format) into clean JSON for one_off_import.py.

Usage: python export_employees.py <input.xlsx> <output.json>
Needs: pandas, openpyxl (pip install pandas openpyxl)
"""
import json
import sys

import pandas as pd

SRC, OUT = sys.argv[1], sys.argv[2]

df = pd.read_excel(SRC)

DATE_COLS = ["D O B", "CNIC Expiry Date", "Joining Date", "DOC", "Confirmation Date", "Contract Expiry Date", "Date Of Joining"]


def clean(val, col):
    if pd.isna(val):
        return None
    if col in DATE_COLS:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    if col == "Bank Account No":
        s = str(val)
        return s[:-2] if s.endswith(".0") else s
    if isinstance(val, float) and val.is_integer():
        return int(val)
    if isinstance(val, str):
        return val.strip()
    return val


rows = [{col: clean(r[col], col) for col in df.columns} for _, r in df.iterrows()]

with open(OUT, "w") as f:
    json.dump(rows, f, indent=1, default=str)

print(f"wrote {len(rows)} rows to {OUT}")
for r in rows:
    print(r.get("Code"), "|", r.get("Name"), "|", r.get("Department"), "|",
          r.get("Joining Date") or r.get("Date Of Joining"))
