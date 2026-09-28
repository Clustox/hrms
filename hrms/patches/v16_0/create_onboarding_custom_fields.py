import frappe


def execute():
	from setup.onboarding.apply_onboarding_schema import run
	run()
