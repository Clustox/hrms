"""Append Pakistan 2026 public holidays to the Clustox 2026 Holiday List.

Fixed national dates are reliable. Islamic holidays are moon-sighting based
and APPROXIMATE -- HR must confirm/adjust the starred ones.

Run: bench --site <site> execute hrms.add_holidays.run
Idempotent: skips dates already present.
"""

import frappe

HOLIDAY_LIST = "Clustox 2026"

HOLIDAYS = [
    # (date, description)  -- national fixed dates
    ("2026-02-05", "Kashmir Day"),
    ("2026-03-23", "Pakistan Day"),
    ("2026-05-01", "Labour Day"),
    ("2026-08-14", "Independence Day"),
    ("2026-12-25", "Quaid-e-Azam Day"),
    # Islamic (APPROXIMATE -- confirm with HR) *
    ("2026-03-20", "Eid ul-Fitr (approx) *"),
    ("2026-03-21", "Eid ul-Fitr (approx) *"),
    ("2026-03-22", "Eid ul-Fitr (approx) *"),
    ("2026-05-27", "Eid ul-Adha (approx) *"),
    ("2026-05-28", "Eid ul-Adha (approx) *"),
    ("2026-05-29", "Eid ul-Adha (approx) *"),
    ("2026-06-26", "Ashura 9th (approx) *"),
    ("2026-06-27", "Ashura 10th (approx) *"),
    ("2026-08-25", "Eid Milad un-Nabi (approx) *"),
]


def run():
    hl = frappe.get_doc("Holiday List", HOLIDAY_LIST)
    existing = {str(h.holiday_date) for h in hl.holidays}
    added = []
    for date, desc in HOLIDAYS:
        if date in existing:
            continue
        hl.append("holidays", {"holiday_date": date, "description": desc, "weekly_off": 0})
        added.append(f"{date}  {desc}")
    hl.save(ignore_permissions=True)
    frappe.db.commit()

    print(f"ADDED {len(added)} public holidays to {HOLIDAY_LIST}:")
    for a in added:
        print("  ", a)
    print(f"\nAUGUST 2026 holidays now: ", [str(h.holiday_date) + ' ' + (h.description or '')
          for h in frappe.get_doc('Holiday List', HOLIDAY_LIST).holidays
          if str(h.holiday_date).startswith('2026-08') and not h.weekly_off])
