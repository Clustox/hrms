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
        if not self.currency:
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
        sows = frappe.get_all("SOW", fields=["name", "sow_type", "billing_model", "customer"])
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
            "currency": self.currency or "USD", "base_amount": base_amount,
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
