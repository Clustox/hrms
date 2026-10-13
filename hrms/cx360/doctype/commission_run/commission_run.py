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
        # Commissions are always computed in USD (the client-billing currency).
        # Forced here because Frappe's global default for a "currency" field is the
        # company currency (PKR), which would otherwise override the field default.
        self.currency = "USD"
        rules = _active_rules(self.run_type)
        if not rules:
            self.total_commission = 0
            return
        self._working_resource_entries(rules)
        self._team_role_entries(rules)
        self.total_commission = sum(flt(e.commission_amount) for e in self.entries)

    @frappe.whitelist()
    def run_generation(self):
        """Rebuild entries from current allocations/timesheets/rules and persist.
        Called by the 'Generate' button on a saved (Draft) run."""
        self.generate()
        self.save()
        return len(self.entries)

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
            fields=["employee", "employee_name", "project", "allocation_percent"],
        )
        for a in allocs:
            eng_type, billing_model = _project_type_model(a.project)
            customer = _project_customer(a.project)
            for rule in rules:
                if rule.role != "Working Resource":
                    continue
                if not ce.scope_matches(rule, eng_type, billing_model):
                    continue
                if rule.customer_scope and customer != rule.customer_scope:
                    continue
                if rule.project_scope and a.project != rule.project_scope:
                    continue
                override = (rule.get("overrides_map") or {}).get(a.employee)
                eff_rate = override if override is not None else rule.rate_value
                base_amount = self._base_amount(rule, a.employee, a.project)
                amt = ce.compute_commission(base_amount, rule, a.allocation_percent,
                                            override_rate=override)
                self._add_entry(a.employee, a.employee_name, "Working Resource",
                                a.project, rule, base_amount, amt, eff_rate)

    # --- Sales / Delivery Lead / Team Lead / PM / Referrer come from the Project team ---
    def _team_role_entries(self, rules):
        team_rules = [r for r in rules if r.role != "Working Resource"]
        if not team_rules:
            return
        projects = set(frappe.get_all("Project Team Member", fields=["parent"], pluck="parent"))
        if self.project:
            projects = projects & {self.project}
        for project in projects:
            eng_type, billing_model = _project_type_model(project)
            customer = _project_customer(project)
            members = frappe.get_all(
                "Project Team Member", filters={"parent": project},
                fields=["employee", "employee_name", "role"],
            )
            for member in members:
                for rule in team_rules:
                    if rule.role != member.role:
                        continue
                    if not ce.scope_matches(rule, eng_type, billing_model):
                        continue
                    if rule.customer_scope and customer != rule.customer_scope:
                        continue
                    if rule.project_scope and project != rule.project_scope:
                        continue
                    override = (rule.get("overrides_map") or {}).get(member.employee)
                    eff_rate = override if override is not None else rule.rate_value
                    base_amount = self._base_amount(rule, member.employee, project)
                    amt = ce.compute_commission(base_amount, rule, 0, override_rate=override)
                    self._add_entry(member.employee, member.employee_name, member.role,
                                    project, rule, base_amount, amt, eff_rate)

    def _base_amount(self, rule, employee, project):
        # widen to all-time for completion/deliverable runs that carry no period
        s = self.period_start or "1900-01-01"
        e = self.period_end or "2999-12-31"
        if rule.base == "Resource revenue":
            return ce.resource_revenue(employee, project, s, e)
        if rule.base == "Total project revenue":
            return ce.project_timesheet_revenue(project, s, e) if project else 0
        if rule.base == "Project value":
            return ce.project_sales_order_value(project)
        if rule.base == "Project cost":
            return ce.project_timesheet_cost(project, s, e) if project else 0
        if rule.base == "Project profit":
            if not project:
                return 0
            return ce.project_timesheet_revenue(project, s, e) - ce.project_timesheet_cost(project, s, e)
        if rule.base == "Margin":
            return ce.margin(employee, project, s, e)
        if rule.base == "Project revenue":
            return ce.project_invoiced(project, s, e) if project else 0
        if rule.base == "Flat amount":
            return 0  # Flat rate_type uses rate_value directly
        return 0  # Deliverable amount handled by per-deliverable runs (future extension)

    def _add_entry(self, employee, employee_name, role, project, rule, base_amount, amt, eff_rate):
        self.append("entries", {
            "employee": employee, "employee_name": employee_name, "role": role,
            "project": project, "rule": rule.name, "base": rule.base,
            "currency": self.currency or "USD", "base_amount": base_amount,
            "rate": f"{eff_rate}{'%' if rule.rate_type == 'Percent' else ''}",
            "commission_amount": amt,
        })


def _active_rules(run_type):
    rules = frappe.get_all(
        "Commission Rule", filters={"active": 1, "trigger": run_type},
        fields=["name", "role", "sow_type_scope", "customer_scope", "project_scope",
                "base", "rate_type", "rate_value", "scale_by_allocation",
                "min_amount", "max_amount"],
    )
    for r in rules:
        r["overrides_map"] = {
            o.employee: o.rate_value
            for o in frappe.get_all("Commission Rule Override",
                                    filters={"parent": r.name},
                                    fields=["employee", "rate_value"])
        }
    return rules


def _project_type_model(project):
    if not project:
        return (None, None)
    row = frappe.db.get_value(
        "Project", project, ["custom_engagement_type", "custom_billing_model"], as_dict=True)
    return (row.custom_engagement_type, row.custom_billing_model) if row else (None, None)


def _project_customer(project):
    return frappe.db.get_value("Project", project, "customer") if project else None
