"""Pipeline stage rules shared by pipeline templates and per-job pipelines."""

import frappe
from frappe import _

STAGE_TYPES = ("Active", "Hired", "Rejected")

# Applicant status (the legacy HRMS field) that a stage maps to unless set explicitly.
DEFAULT_STATUS_BY_TYPE = {"Hired": "Accepted", "Rejected": "Rejected"}

DEFAULT_TEMPLATE_NAME = "Default Hiring Pipeline"

# (name, type, status, visible_to_guests). Order follows the reference screenshots:
# the two "Rejected after ..." stages sit before "Ready to Offer".
DEFAULT_STAGES = [
	("New Candidates", "Active", "Open", 0),
	("Technical Profile Review", "Active", "Open", 0),
	("Shortlisted (Phone Screening)", "Active", "Shortlisted", 1),
	("Technical Assessment", "Active", "Shortlisted", 1),
	("1st Technical Interview", "Active", "Shortlisted", 1),
	("2nd Technical Interview", "Active", "Shortlisted", 1),
	("Final Interview", "Active", "Shortlisted", 1),
	("Rejected after Technical Interview", "Rejected", "Rejected", 0),
	("Rejected after Final Interview", "Rejected", "Rejected", 0),
	# Ready to Offer / Offer Placed map to Accepted so the existing Job Offer and
	# onboarding flow (gated on Accepted) keeps working before the offer is accepted.
	("Ready to Offer", "Active", "Accepted", 0),
	("Offer Placed", "Active", "Accepted", 0),
	("Offer Accepted", "Hired", "Accepted", 0),
	("Offer Rejected", "Rejected", "Rejected", 0),
]


def validate_stages(stages) -> None:
	"""Validate and normalise a list of stage rows (template or job pipeline)."""
	if not stages:
		frappe.throw(_("A pipeline needs at least one stage."))

	seen = set()
	for idx, row in enumerate(stages):
		name = (row.stage_name or "").strip()
		if not name:
			frappe.throw(_("Row {0}: Stage Name is required.").format(idx + 1))
		row.stage_name = name

		key = name.lower()
		if key in seen:
			frappe.throw(_("Row {0}: Stage {1} is listed more than once.").format(idx + 1, frappe.bold(name)))
		seen.add(key)

		if row.stage_type not in STAGE_TYPES:
			row.stage_type = "Active"

		validate_required_fields(row)

		if not row.maps_to_status:
			if row.stage_type in DEFAULT_STATUS_BY_TYPE:
				row.maps_to_status = DEFAULT_STATUS_BY_TYPE[row.stage_type]
			else:
				row.maps_to_status = "Open" if idx == 0 else "Shortlisted"

	if stages[0].stage_type != "Active":
		frappe.throw(_("The first stage must be an Active stage, because new candidates start there."))


def parse_required_fields(text: str | None) -> list[str]:
	"""Field names from a comma or new-line separated list."""
	return [f.strip() for f in (text or "").replace(chr(10), ",").split(",") if f.strip()]


def validate_required_fields(row) -> None:
	"""Every named field must be a real Job Applicant field."""
	meta = frappe.get_meta("Job Applicant")
	for fieldname in parse_required_fields(row.get("required_fields")):
		if not meta.get_field(fieldname):
			frappe.throw(
				_("Stage {0}: {1} is not a Job Applicant field.").format(frappe.bold(row.stage_name), frappe.bold(fieldname))
			)


def check_required_fields(doc, stage) -> None:
	"""Block a move into a stage while any of its required fields is empty."""
	if doc.flags.get("ats_skip_required_fields"):
		return  # system-driven move (offer accepted, employee created): the decision is already made
	meta = frappe.get_meta("Job Applicant")
	missing = [
		_(meta.get_field(f).label or f)
		for f in parse_required_fields(stage.get("required_fields"))
		if meta.get_field(f) and not doc.get(f)
	]
	if missing:
		frappe.throw(
			_("Fill in {0} before moving {1} to {2}.").format(
				frappe.bold(", ".join(missing)), doc.applicant_name or doc.name, frappe.bold(stage.stage_name)
			),
			title=_("Missing Information"),
		)


def default_stage_rows() -> list[dict]:
	return [
		{
			"stage_name": name,
			"stage_type": stage_type,
			"maps_to_status": status,
			"visible_to_guests": visible,
		}
		for name, stage_type, status, visible in DEFAULT_STAGES
	]


STAGE_COPY_FIELDS = (
	"stage_name",
	"stage_type",
	"maps_to_status",
	"visible_to_guests",
	"color",
	"auto_email_template",
	"required_fields",
)


def copy_template_stages(template_name: str) -> list[dict]:
	"""Stage rows of a template, as plain dicts that can be appended to a job."""
	template = frappe.get_doc("ATS Pipeline Template", template_name)
	return [{field: row.get(field) for field in STAGE_COPY_FIELDS} for row in template.stages]


def setup_job_pipeline(doc, method=None):
	"""Job Opening validate hook.

	A job with no stages gets a copy of its pipeline template (or the default template).
	The copy is independent: editing the template later never changes a live job.
	A job that already has stages keeps them and they are validated.
	"""
	if not doc.get("pipeline_stages"):
		template = doc.get("pipeline_template") or DEFAULT_TEMPLATE_NAME
		if not frappe.db.exists("ATS Pipeline Template", template):
			return  # nothing to copy (e.g. before the default template is seeded)
		for row in copy_template_stages(template):
			doc.append("pipeline_stages", row)

	if doc.get("pipeline_stages"):
		validate_stages(doc.pipeline_stages)


def log_stage_change(applicant: str, from_stage: str | None, to_stage: str | None, source: str = "Manual", reason: str | None = None):
	"""Append one row to the applicant's stage history."""
	job_opening = frappe.db.get_value("Job Applicant", applicant, "job_title")
	return frappe.get_doc(
		{
			"doctype": "Applicant Stage Log",
			"job_applicant": applicant,
			"job_opening": job_opening,
			"from_stage": from_stage,
			"to_stage": to_stage,
			"trigger_source": source,
			"reason": reason,
		}
	).insert(ignore_permissions=True)


def delete_applicant_stage_log(doc, method=None):
	"""Job Applicant on_trash hook: the history is removed together with its applicant."""
	frappe.flags.ats_allow_log_delete = True
	try:
		for name in frappe.get_all("Applicant Stage Log", filters={"job_applicant": doc.name}, pluck="name"):
			frappe.delete_doc("Applicant Stage Log", name, force=True, ignore_permissions=True)
	finally:
		frappe.flags.ats_allow_log_delete = False


DEFAULT_REJECT_REASON = "Rejected by recruiter"

# Statuses written by older code (Desk buttons, Interview, Job Offer, Employee) that should move
# the stage. Open, Replied and Hold never move a candidate.
RECONCILED_STATUSES = ("Shortlisted", "Accepted", "Rejected")


def get_job_stages(job: str):
	"""Stage rows of a job in pipeline order."""
	return frappe.get_all(
		"Job Pipeline Stage",
		filters={"parent": job, "parenttype": "Job Opening"},
		fields=[
			"stage_name",
			"stage_type",
			"maps_to_status",
			"visible_to_guests",
			"required_fields",
			"auto_email_template",
			"idx",
		],
		order_by="idx asc",
	)


def stage_for_status(stages, status: str | None):
	"""The pipeline stage an applicant with this legacy status belongs in."""
	first = stages[0]
	if status == "Accepted":
		return next((s for s in stages if s.stage_type == "Hired"), first)
	if status == "Shortlisted":
		return next((s for s in stages if s.stage_type == "Active" and s.maps_to_status == "Shortlisted"), first)
	return first  # Open, Replied, Hold and Rejected start at the first stage


def _source(doc) -> str:
	if doc.flags.get("ats_source"):
		return doc.flags.ats_source
	return "Board" if "kanban_board" in (frappe.form_dict.get("cmd") or "") else "Manual"


def validate_applicant(doc, method=None):
	"""Job Applicant validate hook: keep stage and status in step, then check dropping."""
	sync_stage_and_status(doc)
	validate_drop(doc)


def sync_stage_and_status(doc):
	"""Place a new applicant, apply a stage move to the status, or turn an older status write
	(Shortlist button, Job Offer, Employee hook...) into the matching stage move."""
	if not doc.get("job_title"):
		return
	stages = get_job_stages(doc.job_title)
	if not stages:
		return  # a job from before the ATS: leave it alone
	by_name = {s.stage_name: s for s in stages}
	now = frappe.utils.now_datetime()

	if doc.is_new():
		if not doc.pipeline_stage:
			doc.pipeline_stage = stage_for_status(stages, doc.status).stage_name
		elif doc.pipeline_stage not in by_name:
			frappe.throw(_("Stage {0} is not part of this job's pipeline.").format(frappe.bold(doc.pipeline_stage)))
		doc.stage_entered_on = now
		doc.flags.ats_stage_change = (None, doc.pipeline_stage, "System")
		return

	before = doc.get_doc_before_save()
	if not before:
		return
	old_stage, old_status = before.get("pipeline_stage"), before.get("status")

	if doc.pipeline_stage != old_stage:
		if doc.pipeline_stage not in by_name:
			frappe.throw(_("Stage {0} is not part of this job's pipeline.").format(frappe.bold(doc.pipeline_stage)))
		check_required_fields(doc, by_name[doc.pipeline_stage])
		doc.stage_entered_on = now
		doc.status = by_name[doc.pipeline_stage].maps_to_status or doc.status
		doc.flags.ats_stage_change = (old_stage, doc.pipeline_stage, _source(doc))
		return

	if doc.status != old_status and doc.status in RECONCILED_STATUSES:
		reconcile_status(doc, stages, by_name)


def reconcile_status(doc, stages, by_name):
	"""An older status write happened with no stage change: move the stage to match."""
	if doc.status == "Rejected":
		declined_offer = doc.flags.get("ats_source") == "Offer"
		last_rejected = next((s for s in reversed(stages) if s.stage_type == "Rejected"), None)
		if declined_offer and last_rejected:
			move(doc, last_rejected.stage_name, "Offer", stages)  # an offer turned down ends in the last rejected stage
		elif not doc.is_dropped:
			doc.is_dropped = 1
			doc.drop_reason = doc.drop_reason or DEFAULT_REJECT_REASON
		return

	current = by_name.get(doc.pipeline_stage)
	if current and current.maps_to_status == doc.status:
		return  # the current stage already stands for this status
	target = stage_for_status(stages, doc.status)
	if target.stage_name != doc.pipeline_stage:
		move(doc, target.stage_name, doc.flags.get("ats_source") or "System", stages)


def move(doc, to_stage: str, source: str, stages=None):
	if stages:
		target = next((s for s in stages if s.stage_name == to_stage), None)
		if target:
			check_required_fields(doc, target)
	doc.flags.ats_stage_change = (doc.pipeline_stage, to_stage, source)
	doc.pipeline_stage = to_stage
	doc.stage_entered_on = frappe.utils.now_datetime()


def log_pending_stage_change(doc, method=None):
	"""Job Applicant on_update hook: write the stage history row for a move made in validate."""
	change = doc.flags.pop("ats_stage_change", None)
	if change:
		from_stage, to_stage, source = change
		log_stage_change(doc.name, from_stage, to_stage, source=source)
		send_stage_email(doc, to_stage)


def send_stage_email(doc, stage_name: str) -> bool:
	"""Email the candidate when they enter a stage that has an email template.

	A failure here is logged and never stops the stage move.
	"""
	if doc.flags.get("ats_skip_email") or not doc.get("email_id"):
		return False
	template_name = frappe.db.get_value(
		"Job Pipeline Stage",
		{"parent": doc.job_title, "parenttype": "Job Opening", "stage_name": stage_name},
		"auto_email_template",
	)
	if not template_name:
		return False

	try:
		template = frappe.get_doc("Email Template", template_name)
		context = {
			**doc.as_dict(),
			"candidate_name": doc.applicant_name,
			"job_name": frappe.db.get_value("Job Opening", doc.job_title, "job_title"),
			"stage_name": stage_name,
		}
		email = template.get_formatted_email(context)
		frappe.sendmail(
			recipients=[doc.email_id],
			sender=frappe.db.get_single_value("HR Settings", "hiring_sender_email") or None,
			subject=email["subject"],
			message=email["message"],
			reference_doctype=doc.doctype,
			reference_name=doc.name,
			delayed=True,
		)
		return True
	except Exception:
		frappe.log_error(title=f"ATS stage email failed ({doc.name}, {stage_name})")
		return False


def validate_drop(doc, method=None):
	"""Job Applicant validate hook: a dropped candidate needs a reason; restoring clears it."""
	if doc.get("is_dropped"):
		if not doc.get("drop_reason"):
			frappe.throw(_("Drop Reason is required to drop a candidate."), frappe.MandatoryError)
		if not doc.get("dropped_at_stage"):
			doc.dropped_at_stage = doc.get("pipeline_stage")
	else:
		doc.drop_reason = None
		doc.dropped_at_stage = None


@frappe.whitelist()
def drop_applicant(job_applicant: str, reason: str) -> str:
	"""Drop a candidate from the pipeline. They keep their stage and show in its dropped count."""
	doc = frappe.get_doc("Job Applicant", job_applicant)
	doc.check_permission("write")
	if doc.is_dropped:
		frappe.throw(_("{0} is already dropped.").format(doc.applicant_name or doc.name))
	if not reason:
		frappe.throw(_("Select a reason for dropping the candidate."), frappe.MandatoryError)

	doc.is_dropped = 1
	doc.drop_reason = reason
	doc.dropped_at_stage = doc.pipeline_stage
	doc.save()
	log_stage_change(doc.name, doc.pipeline_stage, doc.pipeline_stage, source="Manual", reason=f"Dropped: {reason}")
	return doc.name


@frappe.whitelist()
def restore_applicant(job_applicant: str) -> str:
	"""Bring a dropped candidate back into the pipeline at the stage they were dropped from."""
	doc = frappe.get_doc("Job Applicant", job_applicant)
	doc.check_permission("write")
	if not doc.is_dropped:
		frappe.throw(_("{0} is not dropped.").format(doc.applicant_name or doc.name))

	previous_reason = doc.drop_reason
	doc.is_dropped = 0
	doc.save()
	log_stage_change(doc.name, doc.pipeline_stage, doc.pipeline_stage, source="Manual", reason=f"Restored (was dropped: {previous_reason})")
	return doc.name


def set_applicant_status(job_applicant: str, status: str, source: str = "System"):
	"""Set an applicant's status from code outside the pipeline (Job Offer, Employee creation).

	The change goes through a normal save, so the stage follows the status and the move
	is logged. An accepted offer or a created employee always ends in the hired stage, and a
	declined offer in the last rejected stage, even when the applicant's current stage
	already maps to the same status (Offer Placed maps to Accepted). Required-field rules
	are skipped because the decision has already been made.
	"""
	doc = frappe.get_doc("Job Applicant", job_applicant)
	stages = get_job_stages(doc.job_title) if doc.job_title else []

	target = None
	if status == "Accepted":
		target = next((s for s in stages if s.stage_type == "Hired"), None)
	elif status == "Rejected" and source == "Offer":
		target = next((s for s in reversed(stages) if s.stage_type == "Rejected"), None)

	if target and doc.pipeline_stage != target.stage_name:
		doc.pipeline_stage = target.stage_name  # the stage move sets the status and writes the history
	elif doc.status != status:
		doc.status = status
	else:
		return doc

	doc.flags.ats_source = source
	doc.flags.ats_skip_required_fields = True
	doc.save(ignore_permissions=True)
	return doc


@frappe.whitelist()
def advance_applicant(job_applicant: str, source: str = "Manual") -> str:
	"""Move a candidate to the next active stage of their job's pipeline."""
	doc = frappe.get_doc("Job Applicant", job_applicant)
	doc.check_permission("write")
	if doc.is_dropped:
		frappe.throw(_("Restore {0} before moving them.").format(doc.applicant_name or doc.name))

	stages = get_job_stages(doc.job_title) if doc.job_title else []
	current = next((s for s in stages if s.stage_name == doc.pipeline_stage), None)
	if not current:
		frappe.throw(_("{0} is not in a pipeline stage.").format(doc.applicant_name or doc.name))

	target = next((s for s in stages if s.idx > current.idx and s.stage_type == "Active"), None)
	if not target:
		frappe.throw(
			_("{0} is already in the last active stage. Use the Job Offer to finish the hire.").format(
				doc.applicant_name or doc.name
			)
		)

	doc.pipeline_stage = target.stage_name
	doc.flags.ats_source = source
	doc.save()
	return target.stage_name

