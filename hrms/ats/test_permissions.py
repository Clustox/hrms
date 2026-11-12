# Copyright (c) 2026, Clustox and contributors
# See license.txt

import frappe
from frappe.client import get as client_get
from frappe.client import get_count as client_get_count
from frappe.client import get_list as client_get_list
from frappe.desk.form.load import getdoc
from frappe.desk.notifications import get_open_count
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from hrms.ats.guest_access import grant_access, invite_guest, revoke_access
from hrms.ats.permissions import is_restricted_guest
from hrms.ats.pipeline import drop_applicant, restore_applicant
from hrms.ats.roles import GUEST, RECRUITER
from hrms.ats.test_pipeline import make_job
from hrms.ats.test_stage_logic import move_stage, new_applicant


def unique_email(prefix="perm"):
	return f"{prefix}.{frappe.generate_hash(length=8)}@example.com"


def make_user(*roles):
	return frappe.get_doc(
		{"doctype": "User", "email": unique_email("staff"), "first_name": "Staff", "send_welcome_email": 0, "enabled": 1, "roles": [{"role": r} for r in roles]}
	).insert(ignore_permissions=True).name


def as_user(user, fn, *args, **kwargs):
	frappe.set_user(user)
	try:
		return fn(*args, **kwargs)
	finally:
		frappe.set_user("Administrator")


def names(user, doctype, **kwargs):
	return sorted(as_user(user, frappe.get_list, doctype, pluck="name", limit_page_length=0, **kwargs))


def names_or_denied(user, doctype, **kwargs):
	"""Names a user can list, or [] when the list request is refused outright (no role for it)."""
	try:
		return names(user, doctype, **kwargs)
	except frappe.PermissionError:
		return []


def can_read(user, doctype, name):
	return bool(as_user(user, frappe.has_permission, doctype, "read", doc=name))


def make_interview(applicant, job, *interviewers):
	if not frappe.db.exists("Skill", "_Test Perm Skill"):
		frappe.get_doc({"doctype": "Skill", "skill_name": "_Test Perm Skill"}).insert()
	if not frappe.db.exists("Interview Type", "_Test Perm Round"):
		frappe.get_doc({"doctype": "Interview Type", "interview_type_name": "_Test Perm Round", "expected_skill_set": [{"skill": "_Test Perm Skill"}]}).insert()
	return frappe.get_doc(
		{
			"doctype": "Interview",
			"job_applicant": applicant,
			"job_opening": job,
			"interview_type": "_Test Perm Round",
			"scheduled_on": add_days(nowdate(), 3),
			"from_time": "10:00:00",
			"to_time": "11:00:00",
			"interview_details": [{"interviewer": i} for i in interviewers],
		}
	).insert().name


class GuestFixture(IntegrationTestCase):
	"""Two jobs. The guest has job A. Applicants in A are in a visible stage, a hidden stage, a rejected
	stage, or dropped; one applicant is in job B."""

	def setUp(self):
		self.job_a = make_job("_Test Perm A").insert()
		self.job_b = make_job("_Test Perm B").insert()
		self.guest = unique_email("guest")
		invite_guest(self.guest, "Guest", [self.job_a.name], send_invite=0)

		def applicant(job, stage=None):
			name = new_applicant(job, unique_email("app")).name
			if stage:
				move_stage(name, stage)
			return name

		self.visible = applicant(self.job_a, "Technical Assessment")  # stage ticked for guests
		self.hidden_stage = applicant(self.job_a)  # New Candidates: not ticked
		self.rejected = applicant(self.job_a, "On Hold")  # a stage that is not ticked for guests
		self.dropped = applicant(self.job_a, "Final Interview")
		drop_applicant(self.dropped, "Candidate withdrew")
		self.other_job = applicant(self.job_b, "Final Interview")

	def candidate(self, applicant):
		return frappe.db.get_value("Job Applicant", applicant, "candidate")


class TestGuestSeesOnlyWhatIsShared(GuestFixture):
	def test_is_a_restricted_guest(self):
		self.assertTrue(is_restricted_guest(self.guest))
		self.assertFalse(is_restricted_guest("Administrator"))
		self.assertFalse(is_restricted_guest(make_user("HR User")))
		self.assertFalse(is_restricted_guest(make_user(GUEST, "HR User")))  # staff wins

	def test_only_the_shared_job_is_listed(self):
		self.assertEqual(names(self.guest, "Job Opening"), [self.job_a.name])

	def test_only_applicants_in_a_visible_stage_and_not_dropped(self):
		self.assertEqual(names(self.guest, "Job Applicant"), [self.visible])

	def test_only_candidates_with_a_visible_application(self):
		self.assertEqual(names(self.guest, "Candidate"), [self.candidate(self.visible)])

	def test_each_hidden_record_is_refused_when_opened_directly(self):
		for hidden in (self.hidden_stage, self.rejected, self.dropped, self.other_job):
			self.assertFalse(can_read(self.guest, "Job Applicant", hidden), hidden)
			self.assertFalse(can_read(self.guest, "Candidate", self.candidate(hidden)), hidden)
		self.assertFalse(can_read(self.guest, "Job Opening", self.job_b.name))
		self.assertTrue(can_read(self.guest, "Job Applicant", self.visible))
		self.assertTrue(can_read(self.guest, "Job Opening", self.job_a.name))

	def test_staff_still_see_everything(self):
		everyone = sorted([self.visible, self.hidden_stage, self.rejected, self.dropped, self.other_job])
		for role in ("HR User", "HR Manager", RECRUITER):
			user = make_user(role)
			seen = names(user, "Job Applicant", filters={"name": ["in", everyone]})
			self.assertEqual(seen, everyone, role)
			self.assertEqual(len(names(user, "Job Opening", filters={"name": ["in", [self.job_a.name, self.job_b.name]]})), 2, role)

	def test_a_user_with_staff_roles_plus_guest_is_not_restricted(self):
		user = make_user(GUEST, RECRUITER)
		self.assertEqual(len(names(user, "Job Applicant", filters={"name": ["in", [self.hidden_stage, self.other_job]]})), 2)


class TestEveryAccessPath(GuestFixture):
	"""The same rule must hold however the record is asked for, not only in the list."""

	def test_client_get_list(self):
		rows = as_user(self.guest, client_get_list, "Job Applicant", fields=["name"], limit_page_length=0)
		self.assertEqual([r["name"] for r in rows], [self.visible])

	def test_client_get_of_a_hidden_record(self):
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, client_get, "Job Applicant", self.hidden_stage)
		self.assertEqual(as_user(self.guest, client_get, "Job Applicant", self.visible).name, self.visible)

	def test_form_load_of_a_hidden_record(self):
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, getdoc, "Job Applicant", self.other_job)
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, getdoc, "Job Opening", self.job_b.name)

	def test_counts_only_count_what_the_guest_may_see(self):
		self.assertEqual(as_user(self.guest, client_get_count, "Job Applicant"), 1)
		self.assertEqual(as_user(self.guest, client_get_count, "Job Opening"), 1)

	def test_link_search_only_offers_visible_records(self):
		from frappe.desk.search import search_link

		found = as_user(self.guest, search_link, "Job Opening", "_Test Perm")
		self.assertEqual([r["value"] for r in found], [self.job_a.name])

	def test_a_guest_cannot_change_anything(self):
		doc = frappe.get_doc("Job Applicant", self.visible)
		for action in ("save", "delete"):
			with self.assertRaises(frappe.PermissionError):
				as_user(self.guest, lambda: (doc.save() if action == "save" else frappe.delete_doc("Job Applicant", self.visible)))
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, frappe.set_value, "Job Applicant", self.visible, "pipeline_stage", "Final Interview")

	def test_kanban_boards_are_closed_to_guests(self):
		board = frappe.get_doc(
			{"doctype": "Kanban Board", "kanban_board_name": "_Test Perm Board", "reference_doctype": "Job Applicant", "field_name": "pipeline_stage", "private": 0, "columns": [{"column_name": "New Candidates"}]}
		).insert()
		self.assertFalse(can_read(self.guest, "Kanban Board", board.name))
		self.assertEqual(names(self.guest, "Kanban Board", filters={"name": board.name}), [])
		self.assertTrue(can_read(make_user(RECRUITER), "Kanban Board", board.name))

	def test_internal_records_are_not_readable(self):
		self.assertFalse(can_read(self.guest, "Applicant Stage Log", frappe.get_all("Applicant Stage Log", pluck="name", limit=1)[0]))
		self.assertFalse(frappe.has_permission("Job Guest Access", "read", user=self.guest))
		self.assertFalse(frappe.has_permission("Job Offer", "read", user=self.guest))


class TestVisibilityFollowsTheCandidate(GuestFixture):
	def test_a_candidate_moving_into_a_visible_stage_appears(self):
		move_stage(self.hidden_stage, "Final Interview")
		self.assertIn(self.hidden_stage, names(self.guest, "Job Applicant"))
		self.assertTrue(can_read(self.guest, "Candidate", self.candidate(self.hidden_stage)))

	def test_a_candidate_rejected_after_being_visible_disappears(self):
		self.assertIn(self.visible, names(self.guest, "Job Applicant"))
		drop_applicant(self.visible, "Rejected by recruiter")
		self.assertNotIn(self.visible, names(self.guest, "Job Applicant"))
		self.assertFalse(can_read(self.guest, "Job Applicant", self.visible))
		self.assertEqual(names(self.guest, "Candidate"), [])

	def test_dropping_hides_and_restoring_shows_again(self):
		drop_applicant(self.visible, "Candidate withdrew")
		self.assertEqual(names(self.guest, "Job Applicant"), [])
		restore_applicant(self.visible)
		self.assertEqual(names(self.guest, "Job Applicant"), [self.visible])

	def test_untick_the_stage_and_the_candidate_is_hidden_at_once(self):
		row = next(r for r in self.job_a.pipeline_stages if r.stage_name == "Technical Assessment")
		row.visible_to_guests = 0
		self.job_a.save()
		self.assertEqual(names(self.guest, "Job Applicant"), [])

	def test_tick_another_stage_and_its_candidates_appear(self):
		row = next(r for r in self.job_a.pipeline_stages if r.stage_name == "New Candidates")
		row.visible_to_guests = 1
		self.job_a.save()
		self.assertIn(self.hidden_stage, names(self.guest, "Job Applicant"))

	def test_a_candidate_with_two_applications_is_visible_through_either(self):
		same_person = frappe.db.get_value("Job Applicant", self.hidden_stage, "email_id")
		# the same person also applied to job B, where they are in a visible stage the guest cannot reach
		other = new_applicant(self.job_b, same_person).name
		move_stage(other, "Final Interview")
		self.assertEqual(self.candidate(other), self.candidate(self.hidden_stage))
		self.assertFalse(can_read(self.guest, "Candidate", self.candidate(self.hidden_stage)))  # job B is not shared
		grant_access(self.guest, self.job_b.name)
		self.assertTrue(can_read(self.guest, "Candidate", self.candidate(self.hidden_stage)))


class TestRevokeAndExpiry(GuestFixture):
	def test_revoking_shuts_the_door_at_once(self):
		self.assertEqual(names(self.guest, "Job Opening"), [self.job_a.name])
		revoke_access(self.guest, self.job_a.name)
		for doctype in ("Job Opening", "Job Applicant", "Candidate"):
			self.assertEqual(names_or_denied(self.guest, doctype), [], doctype)  # the guest role is gone as well

	def test_an_expired_grant_stops_working_without_waiting_for_the_daily_job(self):
		grant = frappe.get_all("Job Guest Access", filters={"user": self.guest}, pluck="name")[0]
		frappe.db.set_value("Job Guest Access", grant, "expires_on", add_days(nowdate(), -1))
		self.assertEqual(names(self.guest, "Job Applicant"), [])
		self.assertFalse(can_read(self.guest, "Job Opening", self.job_a.name))

	def test_sharing_a_second_job_adds_its_visible_applicants(self):
		grant_access(self.guest, self.job_b.name)
		self.assertEqual(names(self.guest, "Job Applicant"), sorted([self.visible, self.other_job]))

	def test_a_grant_for_one_guest_does_not_help_another(self):
		other_guest = unique_email("guest2")
		invite_guest(other_guest, "Other", [self.job_b.name], send_invite=0)
		self.assertEqual(names(other_guest, "Job Applicant"), [self.other_job])
		self.assertEqual(names(self.guest, "Job Applicant"), [self.visible])


class TestInterviews(GuestFixture):
	def test_a_guest_sees_only_interviews_they_are_assigned_to(self):
		mine = make_interview(self.visible, self.job_a.name, self.guest)
		someone_elses = make_interview(self.hidden_stage, self.job_a.name, "Administrator")
		self.assertEqual(names(self.guest, "Interview"), [mine])
		self.assertTrue(can_read(self.guest, "Interview", mine))
		self.assertFalse(can_read(self.guest, "Interview", someone_elses))

	def test_an_interview_in_an_unshared_job_is_hidden_even_if_assigned(self):
		other = make_interview(self.other_job, self.job_b.name, self.guest)
		self.assertEqual(names(self.guest, "Interview"), [])
		self.assertFalse(can_read(self.guest, "Interview", other))

	def test_revoking_hides_the_interview_too(self):
		mine = make_interview(self.visible, self.job_a.name, self.guest)
		revoke_access(self.guest, self.job_a.name)
		self.assertEqual(names_or_denied(self.guest, "Interview"), [])
		self.assertFalse(can_read(self.guest, "Interview", mine))

	def test_staff_see_every_interview(self):
		a = make_interview(self.visible, self.job_a.name, self.guest)
		b = make_interview(self.other_job, self.job_b.name, "Administrator")
		self.assertEqual(names(make_user(RECRUITER), "Interview", filters={"name": ["in", [a, b]]}), sorted([a, b]))


class TestFilesAndComments(GuestFixture):
	def attach(self, applicant):
		return frappe.get_doc(
			{"doctype": "File", "file_name": f"cv-{frappe.generate_hash(length=6)}.txt", "content": b"resume", "is_private": 1, "attached_to_doctype": "Job Applicant", "attached_to_name": applicant}
		).insert(ignore_permissions=True)

	def test_a_resume_of_a_visible_candidate_can_be_opened(self):
		file = self.attach(self.visible)
		self.assertTrue(as_user(self.guest, frappe.has_permission, "File", "read", doc=file))

	def test_a_resume_of_a_hidden_candidate_cannot(self):
		for hidden in (self.hidden_stage, self.dropped, self.other_job):
			file = self.attach(hidden)
			self.assertFalse(as_user(self.guest, frappe.has_permission, "File", "read", doc=file), hidden)

	def comments_on_form(self, user, applicant):
		"""The notes a user receives when they open the applicant's form."""
		frappe.set_user(user)
		try:
			frappe.response.docs, frappe.response.docinfo = [], None
			getdoc("Job Applicant", applicant)
			return [c["content"] for c in frappe.response.docinfo.comments]
		finally:
			frappe.set_user("Administrator")

	def test_comments_cannot_be_listed_directly_by_a_guest(self):
		frappe.get_doc("Job Applicant", self.hidden_stage).add_comment("Comment", "internal note: salary too high")
		with self.assertRaises(frappe.PermissionError):
			as_user(self.guest, frappe.get_list, "Comment", filters={"reference_doctype": "Job Applicant", "reference_name": self.hidden_stage}, pluck="name")

	def test_notes_on_a_hidden_candidate_cannot_be_read_through_the_form(self):
		frappe.get_doc("Job Applicant", self.hidden_stage).add_comment("Comment", "internal note: salary too high")
		with self.assertRaises(frappe.PermissionError):
			self.comments_on_form(self.guest, self.hidden_stage)

	def test_a_guest_reads_the_notes_on_a_visible_candidate(self):
		frappe.get_doc("Job Applicant", self.visible).add_comment("Comment", "good communicator")
		notes = self.comments_on_form(self.guest, self.visible)
		self.assertEqual(len(notes), 1)
		self.assertIn("good communicator", notes[0])  # stored as HTML


class TestNoCountsLeakToGuests(GuestFixture):
	"""Totals count every candidate, including the ones a guest may not see, so a guest never gets them."""

	def job_payload(self, user):
		frappe.set_user(user)
		try:
			frappe.response.docs = []
			getdoc("Job Opening", self.job_a.name)
			return frappe.response.docs[0].as_dict()
		finally:
			frappe.set_user("Administrator")

	def connections(self, user, doctype, name):
		frappe.set_user(user)
		try:
			return [(row["doctype"], row["count"]) for row in get_open_count(doctype, name)["count"]["external_links_found"]]
		finally:
			frappe.set_user("Administrator")

	def test_the_job_counters_are_hidden_from_a_guest(self):
		# the job has four live applicants (visible, hidden stage, rejected, dropped); the guest may see one
		payload = self.job_payload(self.guest)
		for fieldname in ("hired_count", "in_pipeline_count", "dropped_count"):
			self.assertFalse(payload.get(fieldname), fieldname)
		self.assertNotIn("-", payload.get("headcount") or "")

	def test_staff_still_get_the_counters(self):
		for role in ("HR User", "HR Manager", RECRUITER):
			payload = self.job_payload(make_user(role))
			self.assertGreater(payload.in_pipeline_count + payload.dropped_count, 0, role)
			self.assertRegex(payload.headcount, r"^\d+ - \d+$", role)

	def test_a_guest_gets_no_connection_counts(self):
		self.assertEqual(self.connections(self.guest, "Job Opening", self.job_a.name), [])
		self.assertEqual(self.connections(self.guest, "Job Applicant", self.visible), [])
		self.assertEqual(self.connections(self.guest, "Candidate", self.candidate(self.visible)), [])

	def test_staff_still_get_connection_counts(self):
		counts = dict(self.connections(make_user(RECRUITER), "Job Opening", self.job_a.name))
		self.assertEqual(counts["Job Applicant"], 4)

	def test_the_applicant_connections_of_staff_include_the_offer(self):
		doctypes = [d for d, _count in self.connections(make_user("HR User"), "Job Applicant", self.visible)]
		self.assertIn("Job Offer", doctypes)
