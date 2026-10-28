"""Cost-sheet costing: distribute an employee's monthly cost across their planned
Resource Allocations, per working day. Cost source = Employee Rate Card."""

import calendar
from datetime import date as _date

import frappe
from frappe.utils import flt, getdate

STANDARD_MONTHLY_HOURS = 160


def working_days_in_month(any_date) -> int:
    """Mon-Fri count in the calendar month of `any_date`."""
    d = getdate(any_date)
    _, ndays = calendar.monthrange(d.year, d.month)
    return sum(1 for day in range(1, ndays + 1) if _date(d.year, d.month, day).weekday() < 5)


def is_working_day(any_date) -> bool:
    return getdate(any_date).weekday() < 5


def employee_monthly_cost(employee: str, on_date) -> float:
    """Latest Employee Rate Card monthly cost effective on or before `on_date`."""
    rows = frappe.get_all(
        "Employee Rate Card",
        filters={"employee": employee, "effective_from": ["<=", getdate(on_date)]},
        fields=["monthly_cost"],
        order_by="effective_from desc",
        limit=1,
    )
    return flt(rows[0].monthly_cost) if rows else 0.0


def employee_daily_cost(employee: str, on_date) -> float:
    """Monthly cost spread over the working days of that month."""
    wd = working_days_in_month(on_date)
    if not wd:
        return 0.0
    return flt(employee_monthly_cost(employee, on_date)) / wd


def employee_hourly_cost(employee: str, on_date) -> float:
    """Monthly cost over the standard 160-hour month (for per-hour allocation rates)."""
    return flt(employee_monthly_cost(employee, on_date)) / STANDARD_MONTHLY_HOURS
