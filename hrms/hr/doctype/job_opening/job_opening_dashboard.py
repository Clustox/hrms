def get_data():
	return {
		"fieldname": "job_title",
		# Interview links to its job through job_opening, not job_title
		"non_standard_fieldnames": {"Interview": "job_opening"},
		"transactions": [{"items": ["Job Applicant", "Interview"]}],
	}
