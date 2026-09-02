# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import os
import shutil
from unittest.mock import MagicMock, patch

import frappe

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.controllers.slack_notifications import (
	post_birthday_card_to_slack,
	render_birthday_card,
	send_birthday_slack_notifications,
)
from hrms.tests.utils import HRMSTestSuite

TEST_WEBHOOK_URL = "https://hooks.slack.com/services/TEST/TEST/TEST"


class TestSlackBirthdayNotifications(HRMSTestSuite):
	def setUp(self):
		employee_name = make_employee("test_slack_birthday@example.com", company="_Test Company")
		employee = frappe.get_doc("Employee", employee_name)
		employee.date_of_birth = "1992" + frappe.utils.nowdate()[4:]
		employee.company_email = "test_slack_birthday@example.com"
		employee.company = "_Test Company"
		employee.save()
		self.test_employee = employee

		hr_settings = frappe.get_doc("HR Settings", "HR Settings")
		hr_settings.send_birthday_slack_notification = 0
		hr_settings.save()

	def tearDown(self):
		hr_settings = frappe.get_doc("HR Settings", "HR Settings")
		hr_settings.send_birthday_slack_notification = 0
		hr_settings.save()

	def test_noop_when_toggle_disabled(self):
		with patch.object(frappe, "enqueue") as mock_enqueue:
			send_birthday_slack_notifications()
			mock_enqueue.assert_not_called()

	def test_noop_when_webhook_not_configured(self):
		hr_settings = frappe.get_doc("HR Settings", "HR Settings")
		hr_settings.send_birthday_slack_notification = 1
		hr_settings.save()

		with (
			patch.object(frappe.conf, "get", return_value=None),
			patch.object(frappe, "enqueue") as mock_enqueue,
		):
			send_birthday_slack_notifications()
			mock_enqueue.assert_not_called()

	def test_enqueues_one_job_per_birthday_employee(self):
		hr_settings = frappe.get_doc("HR Settings", "HR Settings")
		hr_settings.send_birthday_slack_notification = 1
		hr_settings.save()

		with (
			patch.object(frappe.conf, "get", return_value=TEST_WEBHOOK_URL),
			patch.object(frappe, "enqueue") as mock_enqueue,
		):
			send_birthday_slack_notifications()

			enqueued_names = [call.kwargs.get("employee_name") for call in mock_enqueue.call_args_list]
			self.assertIn(self.test_employee.employee_name, enqueued_names)

			for call in mock_enqueue.call_args_list:
				self.assertEqual(call.kwargs.get("webhook_url"), TEST_WEBHOOK_URL)

	def test_post_birthday_card_to_slack_payload(self):
		mock_response = MagicMock()
		mock_response.raise_for_status = MagicMock()

		with patch("requests.post", return_value=mock_response) as mock_post:
			post_birthday_card_to_slack(
				TEST_WEBHOOK_URL,
				"Faraz Sohail",
				"https://frappe.theclustox.com/files/birthday_card_faraz_sohail.png",
			)

			mock_post.assert_called_once()
			args, kwargs = mock_post.call_args
			self.assertEqual(args[0], TEST_WEBHOOK_URL)

			payload = kwargs["json"]
			self.assertIn("Faraz Sohail", payload["text"])

			image_blocks = [b for b in payload["blocks"] if b["type"] == "image"]
			self.assertEqual(len(image_blocks), 1)
			self.assertEqual(
				image_blocks[0]["image_url"],
				"https://frappe.theclustox.com/files/birthday_card_faraz_sohail.png",
			)

	def test_render_birthday_card_produces_a_png(self):
		if not shutil.which("wkhtmltoimage"):
			self.skipTest("wkhtmltoimage not available in this environment")

		png_path = render_birthday_card("Faraz Sohail", None)
		try:
			self.assertTrue(os.path.exists(png_path))
			self.assertGreater(os.path.getsize(png_path), 0)
			with open(png_path, "rb") as f:
				# PNG magic bytes
				self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
		finally:
			os.remove(png_path)
