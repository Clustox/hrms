from frappe.model.document import Document


class DesignationRate(Document):
    def validate(self):
        self.currency = "USD"
