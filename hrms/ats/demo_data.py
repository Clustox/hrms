"""Demo recruitment data for local development.

    bench --site <site> execute hrms.ats.demo_data.create_demo_data
    bench --site <site> execute hrms.ats.demo_data.delete_demo_data

Everything is tagged so it can be removed again: job titles start with "[Demo]" and
applicant emails end with "@demo.ats.test". Re-running is safe (existing rows are skipped).
"""

import random

import frappe
from frappe.utils import add_days, getdate, nowdate

DEMO_TAG = "[Demo]"
DEMO_DOMAIN = "@demo.ats.test"

# Department tree (name, parent, is_group), as on the reference Department list.
# Names get the company suffix ("Development - Clustox") like the rest of the site.
DEPARTMENTS = [
	("Professional Services", "All Departments", 1),
	("Corporate Services", "All Departments", 1),
	("Sales & Marketing", "All Departments", 1),
	("Multimedia & Graphics", "All Departments", 1),
	("Marketing", "Sales & Marketing", 0),
	("Sales", "Sales & Marketing", 0),
	("PreSales", "Sales & Marketing", 0),
	("Human Resources", "Corporate Services", 0),
	("Accounts & Finance", "Corporate Services", 0),
	("Administration", "Corporate Services", 0),
	("Network & Operations", "Corporate Services", 0),
	("Management", "Professional Services", 0),
	("Development", "Professional Services", 0),
	("Project Management", "Professional Services", 0),
	("Quality Assurance", "Professional Services", 0),
	("Dev Ops", "Professional Services", 0),
	("Business Analysis", "Professional Services", 0),
	("UI/UX", "Multimedia & Graphics", 0),
]

# (title, department name, location, vacancies, salary range or None for negotiable, status, designation)
JOBS = [
	("Associate Software Engineer", "Development", "Lahore", 3, (120000, 180000), "Open", "Engineer"),
	("Associate SQA Engineer", "Quality Assurance", "Lahore", 2, (90000, 140000), "Open", "Analyst"),
	("Business Analyst", "Business Analysis", "Lahore", 1, (150000, 220000), "Open", "Business Analyst"),
	("Assistant Manager HR", "Human Resources", "Lahore", 1, None, "Open", "Manager"),
	("Associate Sales Executive", "Sales", "Lahore", 4, (70000, 110000), "Open", "Executive"),
	("Digital Marketing Executive", "Marketing", "Lahore", 2, None, "Open", "Executive"),
	("Admin Officer", "Administration", "Lahore", 1, (60000, 90000), "Open", "Administrative Officer"),
	("Accounts Officer", "Accounts & Finance", "Lahore", 1, (80000, 120000), "Closed", "Accountant"),
]

FIRST = [
	"Ayesha", "Bilal", "Hira", "Usman", "Sana", "Hamza", "Maryam", "Talha", "Zainab", "Faizan",
	"Noor", "Daniyal", "Iqra", "Saad", "Mahnoor", "Arslan", "Fatima", "Umair", "Laiba", "Hassan",
]
LAST = ["Khan", "Ahmed", "Malik", "Raza", "Siddiqui", "Butt", "Sheikh", "Iqbal", "Chaudhry", "Ali"]
EMPLOYERS = ["Systems Ltd", "10Pearls", "Arbisoft", "Devsinc", "NetSol", "Folio3", "Afiniti", "Careem"]
ROLES = ["Software Engineer Intern", "QA Engineer", "Business Analyst", "Sales Executive", "HR Executive", "Accountant"]

# Applicant status spread: mostly new, some progressed, a few rejected / accepted
STATUS_WEIGHTS = [("Open", 8), ("Replied", 3), ("Shortlisted", 4), ("Hold", 1), ("Rejected", 3), ("Accepted", 1)]

INTERVIEW_TYPES = ["1st Technical Interview", "2nd Technical Interview", "Final Interview"]


def create_demo_data(applicants_per_job: int = 8):
	random.seed(7)  # same data every run
	frappe.set_user("Administrator")
	company = frappe.db.get_value("Company", {}, "name")

	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
		pluck="name",
		limit=4,
	)
	departments = _ensure_departments(company, users)

	interviewer_types = _ensure_interview_types(users)

	created = {"jobs": 0, "applicants": 0, "interviews": 0}
	for title, dept_key, location, vacancies, salary, status, desig in JOBS:
		job, is_new = _ensure_job(company, departments, title, dept_key, location, vacancies, salary, desig, users)
		if not is_new:
			continue  # already seeded: skip its applicants too, so re-runs change nothing
		created["jobs"] += 1

		for i in range(applicants_per_job):
			if _ensure_applicant(job, i, desig):
				created["applicants"] += 1

		if status == "Closed":
			frappe.db.set_value("Job Opening", job, {"status": "Closed", "closed_on": add_days(nowdate(), -10)})

	created["interviews"] = _ensure_interviews(interviewer_types, users)
	frappe.db.commit()
	print(f"Demo data ready: {created}")
	return created


def _ensure_departments(company, users):
	"""Create/align the department tree. Existing departments keep their records and only get
	the parent/group flag from the reference tree. Returns {short name: full department id}."""
	from erpnext.setup.doctype.department.department import get_abbreviated_name

	ids = {}
	for name, parent, is_group in DEPARTMENTS:
		dept_id = get_abbreviated_name(name, company)
		parent_id = parent if parent == "All Departments" else get_abbreviated_name(parent, company)
		if frappe.db.exists("Department", dept_id):
			doc = frappe.get_doc("Department", dept_id)
		else:
			doc = frappe.new_doc("Department")
			doc.department_name = name
			doc.company = company
		doc.parent_department = parent_id
		doc.is_group = is_group
		if users and not is_group and not doc.get("department_owner"):
			doc.department_owner = users[0]
		doc.save(ignore_permissions=True) if doc.get("name") else doc.insert(ignore_permissions=True)
		ids[name] = doc.name
	return ids


def _ensure_skills():
	for skill in ("Problem Solving", "Communication", "Technical Knowledge"):
		if not frappe.db.exists("Skill", skill):
			frappe.get_doc({"doctype": "Skill", "skill_name": skill}).insert(ignore_permissions=True)
	return ["Problem Solving", "Communication", "Technical Knowledge"]


def _ensure_interview_types(users):
	skills = _ensure_skills()
	for name in INTERVIEW_TYPES:
		if frappe.db.exists("Interview Type", name):
			continue
		doc = frappe.new_doc("Interview Type")
		doc.interview_type_name = name
		for user in users[:2]:
			doc.append("interviewers", {"user": user})
		for skill in skills:
			doc.append("expected_skill_set", {"skill": skill})
		doc.insert(ignore_permissions=True)
	return INTERVIEW_TYPES


def _ensure_job(company, departments, title, dept_key, location, vacancies, salary, desig, users):
	job_title = f"{DEMO_TAG} {title}"
	department = departments.get(dept_key)
	existing = frappe.db.get_value("Job Opening", {"job_title": job_title}, "name")
	if existing:
		frappe.db.set_value("Job Opening", existing, "department", department)
		return existing, False

	designation = _ensure_designation(desig)

	doc = frappe.new_doc("Job Opening")
	doc.job_title = job_title
	doc.company = company
	doc.designation = designation
	doc.department = department
	doc.status = "Open"
	doc.vacancies = vacancies
	doc.posted_on = add_days(nowdate(), -random.randint(5, 60))
	doc.employment_type = "Full-time" if frappe.db.exists("Employment Type", "Full-time") else None
	doc.description = f"<p>We are hiring a {title} to join our team in {location}.</p>"
	doc.currency = "PKR"
	if salary:
		doc.lower_range, doc.upper_range = salary
		doc.salary_per = "Month"
	else:
		doc.salary_negotiable = 1
	if users:
		doc.job_owner = users[0]
		for user in users[1:3]:
			doc.append("job_team", {"user": user, "team_role": "Recruiter"})
	doc.insert(ignore_permissions=True)
	return doc.name, True


def _ensure_designation(name):
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)
	return name


def _pick_status():
	names, weights = zip(*STATUS_WEIGHTS, strict=True)
	return random.choices(names, weights=weights, k=1)[0]


def _ensure_applicant(job, index, designation):
	first, last = random.choice(FIRST), random.choice(LAST)
	email = f"{first}.{last}.{job[-4:]}{index}{DEMO_DOMAIN}".lower()
	if frappe.db.exists("Job Applicant", {"email_id": email}):
		return False

	doc = frappe.new_doc("Job Applicant")
	doc.applicant_name = f"{first} {last}"
	doc.email_id = email
	doc.phone_number = f"+92 3{random.randint(0, 4)}{random.randint(10000000, 99999999)}"
	doc.job_title = job
	doc.designation = designation
	doc.source = random.choice(["Website Listing", "Walk In", "Employee Referral", "Campaign"])
	doc.status = _pick_status()
	doc.applicant_rating = random.choice([0, 0.4, 0.6, 0.8, 1])
	doc.cover_letter = (
		f"Currently working as {random.choice(ROLES)} at {random.choice(EMPLOYERS)}. "
		"Looking for a role with more ownership."
	)
	doc.insert(ignore_permissions=True)
	frappe.db.set_value("Job Applicant", doc.name, "creation", add_days(nowdate(), -random.randint(1, 45)))
	return True


def _ensure_interviews(interview_types, users):
	"""Schedule interviews for a few shortlisted demo applicants."""
	shortlisted = frappe.get_all(
		"Job Applicant",
		filters={"email_id": ["like", f"%{DEMO_DOMAIN}"], "status": ["in", ["Shortlisted", "Accepted"]]},
		fields=["name", "designation"],
		limit=8,
	)
	count = 0
	for idx, applicant in enumerate(shortlisted):
		interview_type = interview_types[idx % len(interview_types)]
		if frappe.db.exists("Interview", {"job_applicant": applicant.name, "interview_type": interview_type}):
			continue
		doc = frappe.new_doc("Interview")
		doc.job_applicant = applicant.name
		doc.interview_type = interview_type
		doc.designation = applicant.designation
		doc.scheduled_on = add_days(getdate(), idx - 2)
		doc.from_time = "11:00:00"
		doc.to_time = "12:00:00"
		doc.status = "Pending"
		for user in users[:2]:
			doc.append("interview_details", {"interviewer": user})
		try:
			doc.insert(ignore_permissions=True)
			count += 1
		except frappe.ValidationError as e:
			print(f"Skipped interview for {applicant.name}: {e}")
	return count


CURRENT_TITLES = [
	"Software Engineer", "Senior Software Engineer", "QA Engineer", "Software Quality Assurance Intern",
	"Backend Developer", "Frontend Web Developer", "Business Analyst", "WordPress Developer",
	"Mobile App Developer", "DevOps Engineer", "Data Analyst", "UI/UX Designer",
]
CURRENT_EMPLOYERS = [
	"Brightway Technologies", "Nexora Systems", "Devlynk", "Cloudnine Labs", "Pixelforge Studio",
	"Datavine Solutions", "Orbit Software House", "Kernel Works", "Bluepeak Digital", "Silverline IT",
]


def fill_candidate_details() -> int:
	"""Give every candidate that has no current job title or employer a made-up one, so the board
	cards have something to show on a development site. Only blanks are filled, the same person always
	gets the same values, and the cards follow (the candidate's save updates the applicants).

	    bench --site <site> execute hrms.ats.demo_data.fill_candidate_details
	"""
	import hashlib

	frappe.set_user("Administrator")
	changed = 0
	for name, title, employer in frappe.get_all(
		"Candidate", fields=["name", "current_title", "current_employer"], as_list=True
	):
		if title and employer:
			continue
		digest = int(hashlib.md5(name.encode()).hexdigest(), 16)
		doc = frappe.get_doc("Candidate", name)
		doc.current_title = title or CURRENT_TITLES[digest % len(CURRENT_TITLES)]
		doc.current_employer = employer or CURRENT_EMPLOYERS[(digest // 7) % len(CURRENT_EMPLOYERS)]
		doc.save(ignore_permissions=True)
		changed += 1
	frappe.db.commit()
	return changed


def delete_demo_data():
	"""Remove everything create_demo_data added."""
	frappe.set_user("Administrator")
	applicants = frappe.get_all("Job Applicant", filters={"email_id": ["like", f"%{DEMO_DOMAIN}"]}, pluck="name")
	for name in frappe.get_all("Interview", filters={"job_applicant": ["in", applicants]}, pluck="name"):
		frappe.delete_doc("Interview", name, force=True, ignore_permissions=True)
	for name in frappe.get_all("Job Offer", filters={"job_applicant": ["in", applicants]}, pluck="name"):
		frappe.delete_doc("Job Offer", name, force=True, ignore_permissions=True)
	for name in applicants:
		frappe.delete_doc("Job Applicant", name, force=True, ignore_permissions=True)
	for name in frappe.get_all("Job Opening", filters={"job_title": ["like", f"{DEMO_TAG}%"]}, pluck="name"):
		frappe.delete_doc("Job Opening", name, force=True, ignore_permissions=True)
	frappe.db.commit()
	print("Demo data removed")
