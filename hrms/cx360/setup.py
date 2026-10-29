import frappe

# The CX360 workspace is shipped from the hrms app (module CX360) so Frappe's
# workspace sync keeps it (declaring app=erpnext in the file would make the sync
# treat it as an orphan and delete it). But functionally it belongs next to
# Projects in the ERPNext app, so we re-place it after every migrate.
CX360_WORKSPACE_APP = "erpnext"
CX360_WORKSPACE_SEQUENCE = 11.5  # Projects=11.0, Support=12.0


def place_cx360_workspace():
    if not frappe.db.exists("Workspace", "CX360"):
        return
    frappe.db.set_value(
        "Workspace", "CX360",
        {"app": CX360_WORKSPACE_APP, "sequence_id": CX360_WORKSPACE_SEQUENCE},
        update_modified=False,
    )
    frappe.db.commit()
