"""Speed check for a job with thousands of applicants. Run it on a development or staging site:

    bench --site <site> execute hrms.ats.stress_test.run --kwargs "{'count': 3000}"

It creates one job named _PERF ... with that many applicants spread over its stages, times the
screens people actually use against the budgets in the plan, then deletes everything it made.
Budgets: job list under 500 ms, board under 1000 ms, one stage move under 300 ms.
"""

import time

import frappe

from hrms.ats.importer import MAX_ROWS, import_rows

BUDGET_MS = {"job list": 500, "board": 1000, "stage move": 300}


def _median_ms(fn, repeat: int = 5) -> float:
	times = []
	for _ in range(repeat):
		started = time.perf_counter()
		fn()
		times.append((time.perf_counter() - started) * 1000)
	return sorted(times)[len(times) // 2]


def run(count: int = 3000) -> dict:
	from hrms.ats.pipeline import get_job_stages

	title = f"_PERF Job {frappe.generate_hash(length=6)}"
	results: dict = {"applicants": count}
	job = None
	try:
		made = 0
		while made < count:
			size = min(MAX_ROWS, count - made)
			rows = [
				{"job_title": title, "name": f"Perf Person {made + i}", "email": f"perf.{made + i}@example.com", "legacy_id": f"PERF-{made + i}"}
				for i in range(size)
			]
			report = import_rows(rows, dry_run=False)
			frappe.db.commit()
			made += report["created"]
			if report["errors"] or not report["created"]:
				frappe.throw(f"Import for the stress test failed: {report['errors'][:3]}")
		job = frappe.db.get_value("Job Opening", {"job_title": title}, "name")
		stages = [s.stage_name for s in get_job_stages(job)]
		# spread the applicants over the stages so every board column has cards
		for index, stage in enumerate(stages):
			frappe.db.sql(
				"update `tabJob Applicant` set pipeline_stage=%s where job_title=%s and mod(cast(substring_index(legacy_id, '-', -1) as unsigned), %s)=%s",
				(stage, job, len(stages), index),
			)
		frappe.db.commit()

		results["job list"] = _median_ms(
			lambda: frappe.get_list(
				"Job Opening",
				fields=["name", "job_title", "location", "headcount", "hired_count", "in_pipeline_count", "dropped_count"],
				limit_page_length=20,
				order_by="modified desc",
			)
		)

		def board():
			frappe.db.sql("select pipeline_stage, count(*) from `tabJob Applicant` where job_title=%s group by pipeline_stage", job)
			for stage in stages:
				frappe.get_list(
					"Job Applicant",
					filters={"job_title": job, "pipeline_stage": stage},
					fields=["name", "applicant_name", "designation", "applicant_rating", "applied_on", "stage_entered_date"],
					limit_page_length=20,
				)

		results["board"] = _median_ms(board)

		victim = frappe.db.get_value("Job Applicant", {"job_title": job, "pipeline_stage": stages[0]}, "name")
		targets = iter([stages[1], stages[2], stages[1], stages[2]])

		def move():
			doc = frappe.get_doc("Job Applicant", victim)
			doc.pipeline_stage = next(targets)
			doc.save()

		results["stage move"] = _median_ms(move, repeat=3)

		results["within budget"] = all(results[name] <= limit for name, limit in BUDGET_MS.items())
		return {k: (round(v) if isinstance(v, float) else v) for k, v in results.items()}
	finally:
		frappe.db.rollback()
		job = job or frappe.db.get_value("Job Opening", {"job_title": title}, "name")
		if job:
			frappe.db.sql("delete from `tabApplicant Stage Log` where job_opening=%s", job)
			frappe.db.sql("delete from `tabJob Applicant` where job_title=%s", job)
		frappe.db.sql("delete from `tabCandidate` where email like 'perf.%%@example.com'")
		frappe.db.commit()
		if job:
			frappe.delete_doc("Job Opening", job, force=True, ignore_permissions=True)
			frappe.db.commit()
