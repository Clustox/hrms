# CX360 PSA — Allocation, SOW & Commission Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SOW, Resource Allocation, and configurable Commission engine for Clustox as a new `CX360` module inside the hrms app, reusing stock ERPNext Project/Timesheet/Sales Invoice.

**Architecture:** Four custom doctypes (SOW with Deliverable + Team children, Resource Allocation, Commission Rule, Commission Run with Entry child) plus a pure-Python commission engine module. SOW governs commercials; Resource Allocation enforces ≤100% capacity and a soft hours-cap alert; Commission Rule is a data-driven screen; Commission Run reads allocations + timesheets + SOW values and emits stacked Commission Entries for review. Builds bottom-up so each layer has real data to read.

**Tech Stack:** Frappe/ERPNext v17 (develop), Python, Frappe DocType JSON, `FrappeTestCase`. Local dev bench in Docker (`docker-frappe-1`), site `hrms.localhost`.

## Global Constraints

- **Target app & module:** everything lives in the **hrms** app under a new module **`CX360`** (folder `hrms/cx360/`). This matches the existing custom modules (`hrms/leave_rules.py`, `hrms/employee_events.py`) and keeps the code bind-mounted and in git. Do **not** create a separate Frappe app.
- **Repo:** `/Users/mrmacbook/projects/hrms` (bind-mounted to container `/home/frappe/frappe-bench/apps/hrms`). The Python package root is `hrms/` inside the repo, so repo-relative paths look like `hrms/cx360/...`.
- **Run any bench command via:** `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && <cmd>'`. No sudo locally.
- **Run tests with:** `bench --site hrms.localhost run-tests --module <dotted.module.path>`. If it refuses with a test-mode error, first run `bench --site hrms.localhost set-config allow_tests true` once.
- **Register doctype/JSON or module changes with:** `bench --site hrms.localhost migrate`. For a single already-registered doctype you edited, `bench --site hrms.localhost reload-doctype "<Doctype Name>"` is faster.
- **After ANY `hooks.py` change:** `bench --site hrms.localhost clear-cache` — a restart does NOT clear Frappe's Redis hooks cache (known gotcha on this bench).
- **`STANDARD_MONTHLY_HOURS = 160`** — full-time monthly hours; capacity = allocation% × 160.
- **Trigger vocabulary is shared** between Commission Rule (`trigger`) and Commission Run (`run_type`), verbatim: `Monthly recurring`, `On project completion`, `Per deliverable completed`. Matching is a direct string compare.
- **`sow_type_scope` vocabulary** (Commission Rule): `Any`, `Sale - Time & Material`, `Sale - Deliverable`, `Internal`.
- **Standard doctype JSON wrapper** — every doctype JSON in this plan uses this shape; each task supplies only `name`, `autoname`/`naming_rule`, `field_order`, `fields`, and (for children) `"istable": 1`:
  ```json
  {
   "actions": [], "creation": "2026-10-07 00:00:00", "doctype": "DocType",
   "editable_grid": 1, "engine": "InnoDB",
   "field_order": [],
   "fields": [],
   "index_web_pages_for_search": 1, "links": [],
   "modified": "2026-10-07 00:00:00", "modified_by": "Administrator",
   "module": "CX360", "name": "",
   "owner": "Administrator",
   "permissions": [
     {"create":1,"delete":1,"email":1,"export":1,"print":1,"read":1,"report":1,"role":"System Manager","share":1,"write":1},
     {"create":1,"delete":1,"email":1,"export":1,"print":1,"read":1,"report":1,"role":"HR Manager","share":1,"write":1}
   ],
   "sort_field": "modified", "sort_order": "DESC", "states": []
  }
  ```
  Child tables (`SOW Deliverable`, `SOW Team Member`, `Commission Entry`) set `"istable": 1`, omit `permissions`/`autoname`, and keep an empty `"permissions": []`.
- **Commit attribution:** end every commit message with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Scope of this plan:** local dev bench implementation with green tests. Production deploy to A40 and real Commission Rule data entry are a separate follow-up, not tasks here.

---

### Task 1: Scaffold the CX360 module

**Files:**
- Modify: `hrms/modules.txt` (append `CX360`)
- Create: `hrms/cx360/__init__.py` (empty)
- Create: `hrms/cx360/doctype/__init__.py` (empty)

**Interfaces:**
- Produces: module `CX360` in the hrms app; a `Module Def` record named `CX360` after migrate. All later tasks place doctypes under `hrms/cx360/doctype/<snake_name>/`.

- [ ] **Step 1: Append the module to modules.txt**

Add a final line `CX360` to `hrms/modules.txt` (keep existing lines).

- [ ] **Step 2: Create the module package dirs**

Create empty files `hrms/cx360/__init__.py` and `hrms/cx360/doctype/__init__.py`.

- [ ] **Step 3: Register the module**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate'`
Expected: completes without error.

- [ ] **Step 4: Verify the Module Def exists**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost execute frappe.client.get_value --kwargs "{\"doctype\":\"Module Def\",\"filters\":{\"name\":\"CX360\"},\"fieldname\":\"name\"}"'`
Expected: returns `{'name': 'CX360'}`.

- [ ] **Step 5: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/modules.txt hrms/cx360 && \
git commit -m "feat(cx360): scaffold CX360 module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: SOW doctype (+ Deliverable & Team children)

**Files:**
- Create: `hrms/cx360/doctype/sow_deliverable/sow_deliverable.json`, `__init__.py`, `sow_deliverable.py`
- Create: `hrms/cx360/doctype/sow_team_member/sow_team_member.json`, `__init__.py`, `sow_team_member.py`
- Create: `hrms/cx360/doctype/sow/sow.json`, `__init__.py`, `sow.py`
- Test: `hrms/cx360/doctype/sow/test_sow.py`

**Interfaces:**
- Produces: DocType `SOW` with fields `customer`, `sow_type` (Sale/Internal), `billing_model` (Time & Material/Deliverable/Fixed Monthly), `status`, `start_date`, `end_date`, `monthly_hours_commitment`, `default_billing_rate`, `monthly_value`, `total_value`, child table `deliverables` (SOW Deliverable: `title`, `due_date`, `amount`, `status`, `completed_on`), child table `team` (SOW Team Member: `employee`, `employee_name`, `role`). `SOW.validate()` rolls `total_value` up from deliverable amounts when `billing_model == "Deliverable"`.

- [ ] **Step 1: Write the failing test**

Create `hrms/cx360/doctype/sow/test_sow.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


def _customer():
    if not frappe.db.exists("Customer", "CX360 Test Client"):
        frappe.get_doc({
            "doctype": "Customer", "customer_name": "CX360 Test Client",
            "customer_type": "Company", "customer_group": "All Customer Groups",
            "territory": "All Territories",
        }).insert()
    return "CX360 Test Client"


class TestSOW(FrappeTestCase):
    def test_deliverable_total_rolls_up(self):
        sow = frappe.get_doc({
            "doctype": "SOW", "title": "Deliverable SOW", "customer": _customer(),
            "sow_type": "Sale", "billing_model": "Deliverable", "status": "Active",
            "deliverables": [
                {"title": "Phase 1", "amount": 3000},
                {"title": "Phase 2", "amount": 2000},
            ],
        }).insert()
        self.assertEqual(sow.total_value, 5000)

    def test_team_and_type_persist(self):
        emp = frappe.get_all("Employee", limit=1)[0].name
        sow = frappe.get_doc({
            "doctype": "SOW", "title": "Internal SOW", "customer": _customer(),
            "sow_type": "Internal", "billing_model": "Fixed Monthly",
            "monthly_value": 8000, "status": "Active",
            "team": [{"employee": emp, "role": "Delivery Lead"}],
        }).insert()
        self.assertEqual(sow.sow_type, "Internal")
        self.assertEqual(sow.team[0].role, "Delivery Lead")
```

- [ ] **Step 2: Create the two child doctypes**

`hrms/cx360/doctype/sow_deliverable/sow_deliverable.json` — wrapper with `"istable": 1`, `"name": "SOW Deliverable"`, `"permissions": []`, no autoname:
- `field_order`: `["title","due_date","amount","status","completed_on"]`
- `fields`:
  ```json
  [
   {"fieldname":"title","fieldtype":"Data","label":"Title","in_list_view":1,"reqd":1},
   {"fieldname":"due_date","fieldtype":"Date","label":"Due Date","in_list_view":1},
   {"fieldname":"amount","fieldtype":"Currency","label":"Amount","in_list_view":1},
   {"fieldname":"status","fieldtype":"Select","label":"Status","options":"Pending\nCompleted","default":"Pending","in_list_view":1},
   {"fieldname":"completed_on","fieldtype":"Date","label":"Completed On","depends_on":"eval:doc.status=='Completed'"}
  ]
  ```
`sow_deliverable.py`:
```python
from frappe.model.document import Document


class SOWDeliverable(Document):
    pass
```

`hrms/cx360/doctype/sow_team_member/sow_team_member.json` — wrapper with `"istable": 1`, `"name": "SOW Team Member"`, `"permissions": []`:
- `field_order`: `["employee","employee_name","role"]`
- `fields`:
  ```json
  [
   {"fieldname":"employee","fieldtype":"Link","label":"Employee","options":"Employee","in_list_view":1,"reqd":1},
   {"fieldname":"employee_name","fieldtype":"Data","label":"Name","fetch_from":"employee.employee_name","read_only":1,"in_list_view":1},
   {"fieldname":"role","fieldtype":"Select","label":"Role","options":"Sales\nDelivery Lead\nPM\nOther","in_list_view":1,"reqd":1}
  ]
  ```
`sow_team_member.py`:
```python
from frappe.model.document import Document


class SOWTeamMember(Document):
    pass
```
Add empty `__init__.py` in both doctype folders.

- [ ] **Step 3: Create the SOW parent doctype**

`hrms/cx360/doctype/sow/sow.json` — wrapper with `"name": "SOW"`, `"autoname": "SOW-.#####"`, `"title_field": "title"`:
- `field_order`: `["title","customer","sow_type","billing_model","status","cb1","start_date","end_date","sec_comm","monthly_hours_commitment","default_billing_rate","monthly_value","total_value","sec_deliverables","deliverables","sec_team","team"]`
- `fields`:
  ```json
  [
   {"fieldname":"title","fieldtype":"Data","label":"Title","reqd":1},
   {"fieldname":"customer","fieldtype":"Link","label":"Customer","options":"Customer","reqd":1},
   {"fieldname":"sow_type","fieldtype":"Select","label":"SOW Type","options":"Sale\nInternal","default":"Sale","reqd":1},
   {"fieldname":"billing_model","fieldtype":"Select","label":"Billing Model","options":"Time & Material\nDeliverable\nFixed Monthly","reqd":1},
   {"fieldname":"status","fieldtype":"Select","label":"Status","options":"Draft\nActive\nClosed\nCancelled","default":"Draft"},
   {"fieldname":"cb1","fieldtype":"Column Break"},
   {"fieldname":"start_date","fieldtype":"Date","label":"Start Date"},
   {"fieldname":"end_date","fieldtype":"Date","label":"End Date"},
   {"fieldname":"sec_comm","fieldtype":"Section Break","label":"Commercials"},
   {"fieldname":"monthly_hours_commitment","fieldtype":"Int","label":"Monthly Hours Commitment","depends_on":"eval:doc.billing_model=='Time & Material'"},
   {"fieldname":"default_billing_rate","fieldtype":"Currency","label":"Default Billing Rate (per hr)","depends_on":"eval:doc.billing_model=='Time & Material'"},
   {"fieldname":"monthly_value","fieldtype":"Currency","label":"Monthly Value","depends_on":"eval:doc.billing_model=='Fixed Monthly'"},
   {"fieldname":"total_value","fieldtype":"Currency","label":"Total Value"},
   {"fieldname":"sec_deliverables","fieldtype":"Section Break","label":"Deliverables","depends_on":"eval:doc.billing_model=='Deliverable'"},
   {"fieldname":"deliverables","fieldtype":"Table","label":"Deliverables","options":"SOW Deliverable"},
   {"fieldname":"sec_team","fieldtype":"Section Break","label":"Team"},
   {"fieldname":"team","fieldtype":"Table","label":"Team","options":"SOW Team Member"}
  ]
  ```
`hrms/cx360/doctype/sow/sow.py`:
```python
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SOW(Document):
    def validate(self):
        if self.billing_model == "Deliverable":
            self.total_value = sum(flt(d.amount) for d in self.deliverables)
```
Add empty `hrms/cx360/doctype/sow/__init__.py`.

- [ ] **Step 4: Register and run the test**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.sow.test_sow'`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/doctype/sow hrms/cx360/doctype/sow_deliverable hrms/cx360/doctype/sow_team_member && \
git commit -m "feat(cx360): SOW doctype with deliverables and team

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Link Project to SOW

**Files:**
- Create: `hrms/cx360/custom/project_custom_field.json` (Custom Field fixture)
- Modify: `hrms/hooks.py` (add `fixtures` entry for the Custom Field)
- Test: `hrms/cx360/doctype/sow/test_sow.py` (add one test)

**Interfaces:**
- Produces: Custom Field `Project.custom_sow` (Link → SOW). Resource Allocation (Task 4) fetches `sow` from `project.custom_sow`.

- [ ] **Step 1: Write the failing test**

Append to `hrms/cx360/doctype/sow/test_sow.py`:

```python
    def test_project_links_to_sow(self):
        sow = frappe.get_doc({
            "doctype": "SOW", "title": "Link SOW", "customer": _customer(),
            "sow_type": "Sale", "billing_model": "Time & Material", "status": "Active",
        }).insert()
        proj = frappe.get_doc({
            "doctype": "Project", "project_name": "CX360 Link Project",
            "custom_sow": sow.name,
        }).insert()
        self.assertEqual(frappe.db.get_value("Project", proj.name, "custom_sow"), sow.name)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.sow.test_sow'`
Expected: FAIL — `custom_sow` is not a valid field of Project.

- [ ] **Step 3: Add the Custom Field as a fixture and register it**

Create `hrms/cx360/custom/project_custom_field.json`:
```json
[
 {
  "doctype": "Custom Field", "dt": "Project", "fieldname": "custom_sow",
  "label": "SOW", "fieldtype": "Link", "options": "SOW",
  "insert_after": "project_name", "module": "CX360",
  "name": "Project-custom_sow"
 }
]
```
In `hrms/hooks.py`, add (or extend) the `fixtures` list with a Custom Field export filtered to this field:
```python
fixtures = [
    {"dt": "Custom Field", "filters": [["name", "in", ["Project-custom_sow"]]]},
]
```
If a `fixtures` list already exists, append the dict instead of redeclaring.

- [ ] **Step 4: Apply the fixture, clear cache, run the test**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate && bench --site hrms.localhost clear-cache && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.sow.test_sow'`
Expected: all SOW tests PASS including `test_project_links_to_sow`.

- [ ] **Step 5: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/custom hrms/hooks.py hrms/cx360/doctype/sow/test_sow.py && \
git commit -m "feat(cx360): link Project to SOW via custom field

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Resource Allocation doctype + capacity rules

**Files:**
- Create: `hrms/cx360/doctype/resource_allocation/resource_allocation.json`, `__init__.py`, `resource_allocation.py`
- Test: `hrms/cx360/doctype/resource_allocation/test_resource_allocation.py`

**Interfaces:**
- Consumes: `Project.custom_sow` (Task 3).
- Produces: DocType `Resource Allocation` with `employee`, `project`, `sow` (fetched), `status` (Active/Closed), `allocation_percent` (Float), `start_date`, `end_date`, `project_billing_rate`, `project_cost_rate`, `monthly_capacity_hours` (read-only, computed). Module constant `STANDARD_MONTHLY_HOURS = 160`. `validate()` blocks when a person's Active allocations overlap in date and sum to > 100%, and sets `monthly_capacity_hours`.

- [ ] **Step 1: Write the failing tests**

Create `hrms/cx360/doctype/resource_allocation/test_resource_allocation.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


def _emp(idx=0):
    rows = frappe.get_all("Employee", filters={"status": "Active"}, limit=5)
    return rows[idx].name


def _project(name):
    if not frappe.db.exists("Project", name):
        frappe.get_doc({"doctype": "Project", "project_name": name}).insert()
    return name


def _alloc(emp, project, pct, start, end, status="Active"):
    return frappe.get_doc({
        "doctype": "Resource Allocation", "employee": emp, "project": project,
        "allocation_percent": pct, "start_date": start, "end_date": end, "status": status,
    })


class TestResourceAllocation(FrappeTestCase):
    def test_capacity_hours_computed(self):
        a = _alloc(_emp(), _project("RA Proj A"), 50, "2026-01-01", "2026-12-31").insert()
        self.assertEqual(a.monthly_capacity_hours, 80)

    def test_overlapping_over_100_blocked(self):
        emp = _emp(1)
        _alloc(emp, _project("RA Proj B"), 60, "2026-01-01", "2026-06-30").insert()
        with self.assertRaises(frappe.ValidationError):
            _alloc(emp, _project("RA Proj C"), 50, "2026-03-01", "2026-09-30").insert()

    def test_non_overlapping_allowed(self):
        emp = _emp(2)
        _alloc(emp, _project("RA Proj D"), 100, "2026-01-01", "2026-03-31").insert()
        a = _alloc(emp, _project("RA Proj E"), 100, "2026-04-01", "2026-06-30").insert()
        self.assertTrue(a.name)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.resource_allocation.test_resource_allocation'`
Expected: FAIL — DocType `Resource Allocation` does not exist.

- [ ] **Step 3: Create the doctype JSON**

`hrms/cx360/doctype/resource_allocation/resource_allocation.json` — wrapper with `"name": "Resource Allocation"`, `"autoname": "ALLOC-.#####"`:
- `field_order`: `["employee","employee_name","project","sow","status","allocation_percent","cb1","start_date","end_date","sec_rate","project_billing_rate","project_cost_rate","monthly_capacity_hours"]`
- `fields`:
  ```json
  [
   {"fieldname":"employee","fieldtype":"Link","label":"Employee","options":"Employee","reqd":1,"in_list_view":1},
   {"fieldname":"employee_name","fieldtype":"Data","label":"Name","fetch_from":"employee.employee_name","read_only":1},
   {"fieldname":"project","fieldtype":"Link","label":"Project","options":"Project","reqd":1,"in_list_view":1},
   {"fieldname":"sow","fieldtype":"Link","label":"SOW","options":"SOW","fetch_from":"project.custom_sow","read_only":1},
   {"fieldname":"status","fieldtype":"Select","label":"Status","options":"Active\nClosed","default":"Active","in_list_view":1},
   {"fieldname":"allocation_percent","fieldtype":"Float","label":"Allocation %","reqd":1,"in_list_view":1},
   {"fieldname":"cb1","fieldtype":"Column Break"},
   {"fieldname":"start_date","fieldtype":"Date","label":"Start Date","reqd":1},
   {"fieldname":"end_date","fieldtype":"Date","label":"End Date","reqd":1},
   {"fieldname":"sec_rate","fieldtype":"Section Break","label":"Rates"},
   {"fieldname":"project_billing_rate","fieldtype":"Currency","label":"Project Billing Rate (per hr)"},
   {"fieldname":"project_cost_rate","fieldtype":"Currency","label":"Project Cost Rate (per hr)"},
   {"fieldname":"monthly_capacity_hours","fieldtype":"Float","label":"Monthly Capacity (hrs)","read_only":1}
  ]
  ```

- [ ] **Step 4: Write the controller**

`hrms/cx360/doctype/resource_allocation/resource_allocation.py`:
```python
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

STANDARD_MONTHLY_HOURS = 160


class ResourceAllocation(Document):
    def validate(self):
        self.monthly_capacity_hours = flt(self.allocation_percent) / 100.0 * STANDARD_MONTHLY_HOURS
        self._check_total_allocation()

    def _check_total_allocation(self):
        if self.status != "Active":
            return
        others = frappe.get_all(
            "Resource Allocation",
            filters={
                "employee": self.employee, "status": "Active",
                "name": ["!=", self.name or ""],
                "start_date": ["<=", self.end_date],
                "end_date": [">=", self.start_date],
            },
            fields=["allocation_percent"],
        )
        total = flt(self.allocation_percent) + sum(flt(o.allocation_percent) for o in others)
        if total > 100:
            frappe.throw(
                _("{0} would be allocated {1}% over this period (max 100%).").format(
                    self.employee_name or self.employee, total
                )
            )
```
Add empty `hrms/cx360/doctype/resource_allocation/__init__.py`.

- [ ] **Step 5: Register and run the tests**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.resource_allocation.test_resource_allocation'`
Expected: all three tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/doctype/resource_allocation && \
git commit -m "feat(cx360): Resource Allocation with <=100% capacity block

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Timesheet hours-cap soft alert

**Files:**
- Create: `hrms/cx360/timesheet_hooks.py`
- Modify: `hrms/hooks.py` (`doc_events` for Timesheet → `validate`)
- Test: `hrms/cx360/test_timesheet_hooks.py`

**Interfaces:**
- Consumes: `Resource Allocation.monthly_capacity_hours` (Task 4).
- Produces: `check_hours_cap(doc, method=None)` — on Timesheet validate, for each (project, month) in the timesheet it compares the employee's total logged hours that month against the matching Active allocation's capacity and calls `frappe.msgprint` (indicator warning) when exceeded. **Never raises** — overtime is allowed.

- [ ] **Step 1: Write the failing test**

Create `hrms/cx360/test_timesheet_hooks.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from hrms.cx360.timesheet_hooks import check_hours_cap


class TestTimesheetHoursCap(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        if not frappe.db.exists("Project", "TS Cap Project"):
            frappe.get_doc({"doctype": "Project", "project_name": "TS Cap Project"}).insert()
        frappe.get_doc({
            "doctype": "Resource Allocation", "employee": self.emp, "project": "TS Cap Project",
            "allocation_percent": 25, "start_date": "2026-01-01", "end_date": "2026-12-31",
            "status": "Active",
        }).insert()

    def _ts(self, hours):
        doc = frappe.get_doc({
            "doctype": "Timesheet", "employee": self.emp,
            "time_logs": [{
                "activity_type": None, "hours": hours, "from_time": "2026-03-02 09:00:00",
                "to_time": "2026-03-02 17:00:00", "project": "TS Cap Project",
            }],
        })
        return doc

    def test_over_capacity_warns_not_raises(self):
        # 25% of 160 = 40 hrs cap; log 60 → warning, no exception
        doc = self._ts(60)
        doc.flags.ignore_mandatory = True
        messages_before = len(frappe.message_log or [])
        check_hours_cap(doc)
        self.assertGreater(len(frappe.message_log or []), messages_before)

    def test_under_capacity_silent(self):
        doc = self._ts(10)
        doc.flags.ignore_mandatory = True
        frappe.clear_messages()
        check_hours_cap(doc)
        self.assertEqual(len(frappe.message_log or []), 0)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.test_timesheet_hooks'`
Expected: FAIL — `hrms.cx360.timesheet_hooks` does not exist.

- [ ] **Step 3: Write the hook module**

`hrms/cx360/timesheet_hooks.py`:
```python
import frappe
from frappe import _
from frappe.utils import flt, getdate, get_first_day, get_last_day


def check_hours_cap(doc, method=None):
    """Soft alert (never blocks) when an employee's monthly hours on a project
    exceed their Resource Allocation capacity."""
    if not doc.employee:
        return
    # group logged hours by (project, month)
    buckets = {}
    for row in (doc.time_logs or []):
        if not row.project or not row.from_time:
            continue
        month_key = getdate(row.from_time).strftime("%Y-%m")
        buckets.setdefault((row.project, month_key), 0)
        buckets[(row.project, month_key)] += flt(row.hours)

    for (project, month_key), ts_hours in buckets.items():
        month_start = get_first_day(getdate(month_key + "-01"))
        month_end = get_last_day(month_start)
        alloc = frappe.get_all(
            "Resource Allocation",
            filters={
                "employee": doc.employee, "project": project, "status": "Active",
                "start_date": ["<=", month_end], "end_date": [">=", month_start],
            },
            fields=["name", "monthly_capacity_hours"], limit=1,
        )
        if not alloc:
            continue
        cap = flt(alloc[0].monthly_capacity_hours)
        existing = _logged_hours(doc.employee, project, month_start, month_end, exclude=doc.name)
        total = existing + ts_hours
        if cap and total > cap:
            frappe.msgprint(
                _("{0} has {1} hrs on {2} in {3} vs capacity {4} hrs.").format(
                    doc.employee, total, project, month_key, cap
                ),
                title=_("Over capacity"), indicator="orange",
            )


def _logged_hours(employee, project, start, end, exclude=None):
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.hours), 0)
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON ts.name = td.parent
        WHERE ts.employee=%s AND td.project=%s
          AND td.from_time BETWEEN %s AND %s
          AND ts.docstatus < 2 AND ts.name != %s
        """,
        (employee, project, start, f"{end} 23:59:59", exclude or ""),
    )
    return flt(rows[0][0]) if rows else 0.0
```

- [ ] **Step 4: Wire the doc_event and clear cache**

In `hrms/hooks.py`, add to `doc_events` (create the dict/key if absent):
```python
doc_events = {
    "Timesheet": {
        "validate": "hrms.cx360.timesheet_hooks.check_hours_cap",
    },
}
```
If `doc_events` already exists (it does — leave rules use it), add the `"Timesheet"` key alongside the existing entries without removing them.

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost clear-cache'`

- [ ] **Step 5: Run the tests**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.test_timesheet_hooks'`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/timesheet_hooks.py hrms/cx360/test_timesheet_hooks.py hrms/hooks.py && \
git commit -m "feat(cx360): soft hours-cap alert on Timesheet validate

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Commission Rule doctype

**Files:**
- Create: `hrms/cx360/doctype/commission_rule/commission_rule.json`, `__init__.py`, `commission_rule.py`
- Test: `hrms/cx360/doctype/commission_rule/test_commission_rule.py`

**Interfaces:**
- Produces: DocType `Commission Rule` with `rule_name`, `active`, `effective_from`, `effective_to`, `role` (Working Resource/Sales/Delivery Lead/PM), `sow_type_scope`, `customer_scope`, `project_scope`, `base` (Resource revenue/Project revenue/Margin/Deliverable amount/Flat amount), `rate_type` (Percent/Flat), `rate_value` (Float), `scale_by_allocation` (Check), `min_amount`, `max_amount`, `trigger`, `notes`. `validate()` requires `effective_to` ≥ `effective_from` when set.

- [ ] **Step 1: Write the failing test**

Create `hrms/cx360/doctype/commission_rule/test_commission_rule.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestCommissionRule(FrappeTestCase):
    def test_rule_inserts_with_defaults(self):
        r = frappe.get_doc({
            "doctype": "Commission Rule", "rule_name": "Resource monthly T&M",
            "role": "Working Resource", "base": "Resource revenue",
            "rate_type": "Percent", "rate_value": 10, "trigger": "Monthly recurring",
            "effective_from": "2026-01-01",
        }).insert()
        self.assertEqual(r.active, 1)
        self.assertEqual(r.sow_type_scope, "Any")

    def test_bad_date_range_blocked(self):
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc({
                "doctype": "Commission Rule", "rule_name": "Bad dates",
                "role": "Sales", "base": "Project revenue", "rate_type": "Percent",
                "rate_value": 1, "trigger": "Monthly recurring",
                "effective_from": "2026-06-01", "effective_to": "2026-01-01",
            }).insert()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.commission_rule.test_commission_rule'`
Expected: FAIL — DocType does not exist.

- [ ] **Step 3: Create the doctype JSON**

`hrms/cx360/doctype/commission_rule/commission_rule.json` — wrapper with `"name": "Commission Rule"`, `"autoname": "field:rule_name"`:
- `field_order`: `["rule_name","active","effective_from","effective_to","sec_who","role","sec_scope","sow_type_scope","customer_scope","project_scope","sec_calc","base","rate_type","rate_value","scale_by_allocation","min_amount","max_amount","sec_when","trigger","notes"]`
- `fields`:
  ```json
  [
   {"fieldname":"rule_name","fieldtype":"Data","label":"Rule Name","reqd":1,"unique":1,"in_list_view":1},
   {"fieldname":"active","fieldtype":"Check","label":"Active","default":1,"in_list_view":1},
   {"fieldname":"effective_from","fieldtype":"Date","label":"Effective From","reqd":1},
   {"fieldname":"effective_to","fieldtype":"Date","label":"Effective To"},
   {"fieldname":"sec_who","fieldtype":"Section Break","label":"Who"},
   {"fieldname":"role","fieldtype":"Select","label":"Role on Project","options":"Working Resource\nSales\nDelivery Lead\nPM","reqd":1,"in_list_view":1},
   {"fieldname":"sec_scope","fieldtype":"Section Break","label":"Scope"},
   {"fieldname":"sow_type_scope","fieldtype":"Select","label":"SOW Type Scope","options":"Any\nSale - Time & Material\nSale - Deliverable\nInternal","default":"Any"},
   {"fieldname":"customer_scope","fieldtype":"Link","label":"Customer","options":"Customer"},
   {"fieldname":"project_scope","fieldtype":"Link","label":"Project","options":"Project"},
   {"fieldname":"sec_calc","fieldtype":"Section Break","label":"Calculation"},
   {"fieldname":"base","fieldtype":"Select","label":"Base","options":"Resource revenue\nProject revenue\nMargin\nDeliverable amount\nFlat amount","reqd":1},
   {"fieldname":"rate_type","fieldtype":"Select","label":"Rate Type","options":"Percent\nFlat","default":"Percent","reqd":1},
   {"fieldname":"rate_value","fieldtype":"Float","label":"Rate Value","reqd":1},
   {"fieldname":"scale_by_allocation","fieldtype":"Check","label":"Scale by Allocation %"},
   {"fieldname":"min_amount","fieldtype":"Currency","label":"Min Amount"},
   {"fieldname":"max_amount","fieldtype":"Currency","label":"Max Amount"},
   {"fieldname":"sec_when","fieldtype":"Section Break","label":"When"},
   {"fieldname":"trigger","fieldtype":"Select","label":"Trigger","options":"Monthly recurring\nOn project completion\nPer deliverable completed","reqd":1},
   {"fieldname":"notes","fieldtype":"Small Text","label":"Notes"}
  ]
  ```
`hrms/cx360/doctype/commission_rule/commission_rule.py`:
```python
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class CommissionRule(Document):
    def validate(self):
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw(_("Effective To cannot be before Effective From."))
```
Add empty `hrms/cx360/doctype/commission_rule/__init__.py`.

- [ ] **Step 4: Register and run the tests**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.commission_rule.test_commission_rule'`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/doctype/commission_rule && \
git commit -m "feat(cx360): Commission Rule configuration doctype

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Commission engine (pure functions)

**Files:**
- Create: `hrms/cx360/commission_engine.py`
- Test: `hrms/cx360/test_commission_engine.py`

**Interfaces:**
- Consumes: Timesheet Detail fields `billing_amount`, `costing_amount`, `hours`, `project`, `from_time`; `Commission Rule` fields.
- Produces:
  - `resource_revenue(employee, project, start, end) -> float` — Σ `billing_amount`.
  - `resource_cost(employee, project, start, end) -> float` — Σ `costing_amount`.
  - `margin(employee, project, start, end) -> float` — revenue − cost.
  - `project_invoiced(project, start, end) -> float` — Σ submitted Sales Invoice Item `base_net_amount` for the project in period.
  - `scope_matches(rule, sow_type, billing_model) -> bool`.
  - `compute_commission(base_amount, rule, allocation_percent) -> float` — applies rate_type/value, optional allocation scaling, min/max clamp; returns 2-dp float.

- [ ] **Step 1: Write the failing tests**

Create `hrms/cx360/test_commission_engine.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from types import SimpleNamespace
from hrms.cx360 import commission_engine as ce


class TestComputeCommission(FrappeTestCase):
    def test_percent(self):
        rule = SimpleNamespace(rate_type="Percent", rate_value=10,
                               scale_by_allocation=0, min_amount=0, max_amount=0)
        self.assertEqual(ce.compute_commission(1000, rule, 100), 100.0)

    def test_flat_scaled_by_allocation(self):
        rule = SimpleNamespace(rate_type="Flat", rate_value=5000,
                               scale_by_allocation=1, min_amount=0, max_amount=0)
        self.assertEqual(ce.compute_commission(0, rule, 50), 2500.0)

    def test_max_cap(self):
        rule = SimpleNamespace(rate_type="Percent", rate_value=50,
                               scale_by_allocation=0, min_amount=0, max_amount=300)
        self.assertEqual(ce.compute_commission(1000, rule, 100), 300.0)


class TestScopeMatches(FrappeTestCase):
    def test_any_matches_all(self):
        rule = SimpleNamespace(sow_type_scope="Any", customer_scope=None, project_scope=None)
        self.assertTrue(ce.scope_matches(rule, "Internal", "Fixed Monthly"))

    def test_tm_scope(self):
        rule = SimpleNamespace(sow_type_scope="Sale - Time & Material",
                               customer_scope=None, project_scope=None)
        self.assertTrue(ce.scope_matches(rule, "Sale", "Time & Material"))
        self.assertFalse(ce.scope_matches(rule, "Sale", "Deliverable"))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.test_commission_engine'`
Expected: FAIL — `commission_engine` has no such attributes.

- [ ] **Step 3: Write the engine module**

`hrms/cx360/commission_engine.py`:
```python
import frappe
from frappe.utils import flt

SCOPE_MAP = {
    "Sale - Time & Material": ("Sale", "Time & Material"),
    "Sale - Deliverable": ("Sale", "Deliverable"),
    "Internal": ("Internal", None),
}


def resource_revenue(employee, project, start, end):
    return _sum_timesheet("billing_amount", employee, project, start, end)


def resource_cost(employee, project, start, end):
    return _sum_timesheet("costing_amount", employee, project, start, end)


def margin(employee, project, start, end):
    return resource_revenue(employee, project, start, end) - resource_cost(
        employee, project, start, end
    )


def _sum_timesheet(column, employee, project, start, end):
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(td.{col}), 0)
        FROM `tabTimesheet Detail` td
        JOIN `tabTimesheet` ts ON ts.name = td.parent
        WHERE ts.employee=%s AND td.project=%s
          AND td.from_time BETWEEN %s AND %s AND ts.docstatus < 2
        """.format(col=column),
        (employee, project, start, f"{end} 23:59:59"),
    )
    return flt(rows[0][0]) if rows else 0.0


def project_invoiced(project, start, end):
    rows = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sii.base_net_amount), 0)
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.project=%s AND si.docstatus=1
          AND si.posting_date BETWEEN %s AND %s
        """,
        (project, start, end),
    )
    return flt(rows[0][0]) if rows else 0.0


def scope_matches(rule, sow_type, billing_model):
    scope = rule.sow_type_scope or "Any"
    if scope != "Any":
        want_type, want_model = SCOPE_MAP[scope]
        if sow_type != want_type:
            return False
        if want_model and billing_model != want_model:
            return False
    return True


def compute_commission(base_amount, rule, allocation_percent):
    if (rule.rate_type or "Percent") == "Percent":
        amt = flt(base_amount) * flt(rule.rate_value) / 100.0
    else:
        amt = flt(rule.rate_value)
    if getattr(rule, "scale_by_allocation", 0) and allocation_percent:
        amt = amt * (flt(allocation_percent) / 100.0)
    if flt(rule.min_amount) and amt < flt(rule.min_amount):
        amt = flt(rule.min_amount)
    if flt(rule.max_amount) and amt > flt(rule.max_amount):
        amt = flt(rule.max_amount)
    return flt(amt, 2)
```

- [ ] **Step 4: Run the tests**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.test_commission_engine'`
Expected: all five tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/commission_engine.py hrms/cx360/test_commission_engine.py && \
git commit -m "feat(cx360): commission engine base + compute helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Commission Run doctype + generate()

**Files:**
- Create: `hrms/cx360/doctype/commission_entry/commission_entry.json`, `__init__.py`, `commission_entry.py`
- Create: `hrms/cx360/doctype/commission_run/commission_run.json`, `__init__.py`, `commission_run.py`
- Test: `hrms/cx360/doctype/commission_run/test_commission_run.py`

**Interfaces:**
- Consumes: `commission_engine` (Task 7), `Resource Allocation` (Task 4), `SOW` + team (Task 2), `Commission Rule` (Task 6).
- Produces: DocType `Commission Run` (`run_type`, `period_start`, `period_end`, `project`, `status`, child `entries`, `total_commission`) with method `generate()` that clears `entries`, builds them from matching allocations/SOW-team × rules for the run's `run_type` and period, and sets `total_commission`. Child `Commission Entry` holds one computed line.

- [ ] **Step 1: Write the failing test**

Create `hrms/cx360/doctype/commission_run/test_commission_run.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestCommissionRun(FrappeTestCase):
    def setUp(self):
        self.emp = frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name
        if not frappe.db.exists("Customer", "CRun Client"):
            frappe.get_doc({"doctype": "Customer", "customer_name": "CRun Client",
                            "customer_type": "Company", "customer_group": "All Customer Groups",
                            "territory": "All Territories"}).insert()
        self.sow = frappe.get_doc({
            "doctype": "SOW", "title": "CRun SOW", "customer": "CRun Client",
            "sow_type": "Sale", "billing_model": "Time & Material", "status": "Active",
        }).insert()
        if not frappe.db.exists("Project", "CRun Project"):
            frappe.get_doc({"doctype": "Project", "project_name": "CRun Project",
                            "custom_sow": self.sow.name}).insert()
        frappe.get_doc({
            "doctype": "Resource Allocation", "employee": self.emp, "project": "CRun Project",
            "allocation_percent": 50, "start_date": "2026-03-01", "end_date": "2026-03-31",
            "status": "Active",
        }).insert()
        # 1000 of billable revenue in March
        frappe.get_doc({
            "doctype": "Timesheet", "employee": self.emp,
            "time_logs": [{"hours": 10, "is_billable": 1, "billing_hours": 10,
                           "billing_rate": 100, "from_time": "2026-03-10 09:00:00",
                           "to_time": "2026-03-10 19:00:00", "project": "CRun Project"}],
        }).insert()
        frappe.get_doc({
            "doctype": "Commission Rule", "rule_name": "CRun Resource 10pct",
            "role": "Working Resource", "base": "Resource revenue", "rate_type": "Percent",
            "rate_value": 10, "trigger": "Monthly recurring", "effective_from": "2026-01-01",
        }).insert()

    def test_generate_produces_entry(self):
        run = frappe.get_doc({
            "doctype": "Commission Run", "run_type": "Monthly recurring",
            "period_start": "2026-03-01", "period_end": "2026-03-31",
        })
        run.generate()
        mine = [e for e in run.entries if e.employee == self.emp]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].commission_amount, 100.0)  # 10% of 1000
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.commission_run.test_commission_run'`
Expected: FAIL — DocType `Commission Run` does not exist.

- [ ] **Step 3: Create the Commission Entry child doctype**

`hrms/cx360/doctype/commission_entry/commission_entry.json` — wrapper with `"istable": 1`, `"name": "Commission Entry"`, `"permissions": []`:
- `field_order`: `["employee","employee_name","role","project","sow","rule","base","base_amount","rate","commission_amount","remarks"]`
- `fields`:
  ```json
  [
   {"fieldname":"employee","fieldtype":"Link","label":"Employee","options":"Employee","in_list_view":1},
   {"fieldname":"employee_name","fieldtype":"Data","label":"Name","read_only":1},
   {"fieldname":"role","fieldtype":"Data","label":"Role","in_list_view":1},
   {"fieldname":"project","fieldtype":"Link","label":"Project","options":"Project","in_list_view":1},
   {"fieldname":"sow","fieldtype":"Link","label":"SOW","options":"SOW"},
   {"fieldname":"rule","fieldtype":"Link","label":"Rule","options":"Commission Rule","in_list_view":1},
   {"fieldname":"base","fieldtype":"Data","label":"Base"},
   {"fieldname":"base_amount","fieldtype":"Currency","label":"Base Amount"},
   {"fieldname":"rate","fieldtype":"Data","label":"Rate"},
   {"fieldname":"commission_amount","fieldtype":"Currency","label":"Commission","in_list_view":1},
   {"fieldname":"remarks","fieldtype":"Small Text","label":"Remarks"}
  ]
  ```
`commission_entry.py`:
```python
from frappe.model.document import Document


class CommissionEntry(Document):
    pass
```
Add empty `__init__.py`.

- [ ] **Step 4: Create the Commission Run doctype JSON**

`hrms/cx360/doctype/commission_run/commission_run.json` — wrapper with `"name": "Commission Run"`, `"autoname": "CRUN-.#####"`:
- `field_order`: `["run_type","period_start","period_end","project","status","total_commission","sec_entries","entries"]`
- `fields`:
  ```json
  [
   {"fieldname":"run_type","fieldtype":"Select","label":"Run Type","options":"Monthly recurring\nOn project completion\nPer deliverable completed","reqd":1,"in_list_view":1},
   {"fieldname":"period_start","fieldtype":"Date","label":"Period Start","depends_on":"eval:doc.run_type=='Monthly recurring'"},
   {"fieldname":"period_end","fieldtype":"Date","label":"Period End","depends_on":"eval:doc.run_type=='Monthly recurring'"},
   {"fieldname":"project","fieldtype":"Link","label":"Project (filter)","options":"Project"},
   {"fieldname":"status","fieldtype":"Select","label":"Status","options":"Draft\nReviewed\nPosted","default":"Draft","in_list_view":1},
   {"fieldname":"total_commission","fieldtype":"Currency","label":"Total Commission","read_only":1,"in_list_view":1},
   {"fieldname":"sec_entries","fieldtype":"Section Break","label":"Entries"},
   {"fieldname":"entries","fieldtype":"Table","label":"Entries","options":"Commission Entry"}
  ]
  ```

- [ ] **Step 5: Write the Commission Run controller**

`hrms/cx360/doctype/commission_run/commission_run.py`:
```python
import frappe
from frappe.model.document import Document
from frappe.utils import flt
from hrms.cx360 import commission_engine as ce


class CommissionRun(Document):
    def validate(self):
        self.total_commission = sum(flt(e.commission_amount) for e in self.entries)

    @frappe.whitelist()
    def generate(self):
        self.entries = []
        rules = _active_rules(self.run_type)
        if not rules:
            self.total_commission = 0
            return
        self._working_resource_entries(rules)
        self._team_role_entries(rules)
        self.total_commission = sum(flt(e.commission_amount) for e in self.entries)

    # --- working resources come from Resource Allocation ---
    def _working_resource_entries(self, rules):
        filters = {"status": "Active"}
        if self.project:
            filters["project"] = self.project
        if self.run_type == "Monthly recurring":
            filters["start_date"] = ["<=", self.period_end]
            filters["end_date"] = [">=", self.period_start]
        allocs = frappe.get_all(
            "Resource Allocation", filters=filters,
            fields=["employee", "employee_name", "project", "sow", "allocation_percent"],
        )
        for a in allocs:
            sow_type, billing_model = _sow_type_model(a.sow)
            for rule in rules:
                if rule.role != "Working Resource":
                    continue
                if not ce.scope_matches(rule, sow_type, billing_model):
                    continue
                if rule.customer_scope and _sow_customer(a.sow) != rule.customer_scope:
                    continue
                if rule.project_scope and a.project != rule.project_scope:
                    continue
                base_amount = self._base_amount(rule, a.employee, a.project, a.sow)
                amt = ce.compute_commission(base_amount, rule, a.allocation_percent)
                self._add_entry(a.employee, a.employee_name, "Working Resource",
                                a.project, a.sow, rule, base_amount, amt)

    # --- Sales / Delivery Lead / PM come from SOW team ---
    def _team_role_entries(self, rules):
        team_rules = [r for r in rules if r.role in ("Sales", "Delivery Lead", "PM")]
        if not team_rules:
            return
        sow_filters = {}
        sows = frappe.get_all("SOW", filters=sow_filters,
                              fields=["name", "sow_type", "billing_model", "customer"])
        for sow in sows:
            members = frappe.get_all(
                "SOW Team Member", filters={"parent": sow.name},
                fields=["employee", "employee_name", "role"],
            )
            project = frappe.db.get_value("Project", {"custom_sow": sow.name}, "name")
            if self.project and project != self.project:
                continue
            for member in members:
                for rule in team_rules:
                    if rule.role != member.role:
                        continue
                    if not ce.scope_matches(rule, sow.sow_type, sow.billing_model):
                        continue
                    if rule.customer_scope and sow.customer != rule.customer_scope:
                        continue
                    if rule.project_scope and project != rule.project_scope:
                        continue
                    base_amount = self._base_amount(rule, member.employee, project, sow.name)
                    amt = ce.compute_commission(base_amount, rule, 0)
                    self._add_entry(member.employee, member.employee_name, member.role,
                                    project, sow.name, rule, base_amount, amt)

    def _base_amount(self, rule, employee, project, sow):
        s, e = self.period_start, self.period_end
        if rule.base == "Resource revenue":
            return ce.resource_revenue(employee, project, s, e)
        if rule.base == "Margin":
            return ce.margin(employee, project, s, e)
        if rule.base == "Project revenue":
            invoiced = ce.project_invoiced(project, s, e) if (project and s and e) else 0
            if invoiced:
                return invoiced
            return _configured_value(sow, self.run_type)
        if rule.base == "Flat amount":
            return 0  # Flat rate_type uses rate_value directly
        return 0  # Deliverable amount handled by per-deliverable runs (future extension)

    def _add_entry(self, employee, employee_name, role, project, sow, rule, base_amount, amt):
        self.append("entries", {
            "employee": employee, "employee_name": employee_name, "role": role,
            "project": project, "sow": sow, "rule": rule.name, "base": rule.base,
            "base_amount": base_amount,
            "rate": f"{rule.rate_value}{'%' if rule.rate_type == 'Percent' else ''}",
            "commission_amount": amt,
        })


def _active_rules(run_type):
    return frappe.get_all(
        "Commission Rule", filters={"active": 1, "trigger": run_type},
        fields=["name", "role", "sow_type_scope", "customer_scope", "project_scope",
                "base", "rate_type", "rate_value", "scale_by_allocation",
                "min_amount", "max_amount"],
    )


def _sow_type_model(sow):
    if not sow:
        return (None, None)
    row = frappe.db.get_value("SOW", sow, ["sow_type", "billing_model"], as_dict=True)
    return (row.sow_type, row.billing_model) if row else (None, None)


def _sow_customer(sow):
    return frappe.db.get_value("SOW", sow, "customer") if sow else None


def _configured_value(sow, run_type):
    if not sow:
        return 0
    row = frappe.db.get_value("SOW", sow, ["monthly_value", "total_value"], as_dict=True)
    if not row:
        return 0
    return flt(row.monthly_value) if run_type == "Monthly recurring" else flt(row.total_value)
```
Each `rule` from `_active_rules` is a dict; access via attribute works because `frappe.get_all` returns `frappe._dict`. Add empty `hrms/cx360/doctype/commission_run/__init__.py`.

- [ ] **Step 6: Register and run the test**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost migrate && bench --site hrms.localhost run-tests --module hrms.cx360.doctype.commission_run.test_commission_run'`
Expected: test PASSES (one entry, commission 100.0).

- [ ] **Step 7: Full module regression**

Run: `docker exec docker-frappe-1 bash -lc 'cd /home/frappe/frappe-bench && bench --site hrms.localhost run-tests --app hrms --module hrms.cx360'`
(If `--module hrms.cx360` doesn't recurse, run each `test_*` module in turn.)
Expected: all CX360 tests PASS.

- [ ] **Step 8: Commit**

```bash
cd /Users/mrmacbook/projects/hrms && git add hrms/cx360/doctype/commission_run hrms/cx360/doctype/commission_entry && \
git commit -m "feat(cx360): Commission Run engine generating stacked entries

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage**
- SOW (Sale/Internal, 3 billing models, deliverables, team) → Task 2. ✓
- Internal pays commission via configured value → engine `_configured_value` / `_base_amount` (Task 8) + `scope_matches` Internal (Task 7). ✓
- Project↔SOW link → Task 3. ✓
- Resource Allocation, ≤100% hard block, capacity hours → Task 4. ✓
- Hours-cap soft alert → Task 5. ✓
- Commission Rule configurable screen (role, scope, base, rate, scale, trigger, guards) → Task 6. ✓
- Commission engine bases (resource revenue, margin, project revenue, flat) + compute/scope → Task 7. ✓
- Commission Run stacking + review (Draft status) → Task 8. ✓
- Reuse Project/Timesheet/Sales Invoice → Tasks 5,7,8 read them, no new revenue doctype. ✓
- Statement-only posting (no payroll push) → Commission Run stops at Draft/Reviewed/Posted status, no payroll integration. ✓

**Known deferrals (match spec non-goals / open items):**
- `Deliverable amount` base and `Per deliverable completed` / `On project completion` runs are scaffolded in the vocabulary and scope but `_base_amount` returns the configured/zero value for them — full per-deliverable iteration is a follow-up, consistent with the spec's "build bottom-up" and leaving deliverable payout detail to a later pass. Flagged here so it is not mistaken for complete.
- Posting a run to payroll is out of scope (statement-only), per spec §6/§9.

**Placeholder scan:** no TBD/TODO; every code step has real code; test code is concrete.

**Type consistency:** trigger strings identical across Commission Rule, Commission Run, and `_active_rules` filter; `scope_matches`/`compute_commission`/`resource_revenue` signatures match their call sites in Task 8; `monthly_capacity_hours` name consistent across Task 4 and Task 5.
