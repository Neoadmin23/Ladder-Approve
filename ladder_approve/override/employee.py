# Copyright (c) 2025, Ahmad Pasha
# License: MIT

import frappe
from frappe.model.document import Document
from frappe.desk.form.assign_to import add as assign_to_add

ROLE_HR_USER = "HR User"
ROLE_HR_MANAGER = "HR Manager"

STATE_DRAFT = "Draft"
STATE_UNDER_REVIEW = "Under Review"
STATE_APPROVED = "Approved by HR MGR"


class Employee(Document):

    # -------------------------
    # LIFECYCLE
    # -------------------------

    def before_insert(self):
        # Maker
        self.custom_created_by = frappe.session.user

    def after_insert(self):
        """Auto assign to another HR User (safe & non-blocking)"""

        hr_users = frappe.get_all(
            "Has Role",
            filters={"role": ROLE_HR_USER},
            pluck="parent"
        )

        reviewers = []

        for user in hr_users:
            if user == self.custom_created_by:
                continue

            if frappe.db.exists("User", user):
                reviewers.append(user)
            else:
                frappe.logger().warning(
                    f"Invalid HR User found in Has Role: {user}"
                )

        if not reviewers:
            frappe.logger().warning(
                f"No valid HR reviewer found for Employee {self.name}"
            )
            return

        assign_to_add({
            "assign_to": [reviewers[0]],
            "doctype": self.doctype,
            "name": self.name,
            "description": "Please review the newly created Employee.",
            "priority": "Medium"
        })

    def validate(self):
        self._handle_workflow_audit_fields()

    # -------------------------
    # WORKFLOW LOGIC
    # -------------------------

    def _handle_workflow_audit_fields(self):
        prev_doc = self.get_doc_before_save()
        prev_state = prev_doc.workflow_state if prev_doc else STATE_DRAFT
        new_state = self.workflow_state or STATE_DRAFT

        if prev_state == new_state:
            return

        current_user = frappe.session.user

        # Draft → Under Review
        if prev_state == STATE_DRAFT and new_state == STATE_UNDER_REVIEW:
            self._validate_hr_user(current_user)

            if current_user == self.custom_created_by:
                frappe.throw("You cannot review an Employee you created.")

            self.custom_reviewed_by = current_user

        # Under Review → Approved
        if prev_state == STATE_UNDER_REVIEW and new_state == STATE_APPROVED:
            self._validate_hr_manager(current_user)

            if not self.custom_reviewed_by:
                frappe.throw(
                    "Employee must be reviewed by HR User before approval."
                )

            self.custom_approved_by = current_user

    # -------------------------
    # ROLE VALIDATION
    # -------------------------

    def _validate_hr_user(self, user):
        if not frappe.db.exists("Has Role", {
            "parent": user,
            "role": ROLE_HR_USER
        }):
            frappe.throw("Only HR Users can submit Employee for review.")

    def _validate_hr_manager(self, user):
        if not frappe.db.exists("Has Role", {
            "parent": user,
            "role": ROLE_HR_MANAGER
        }):
            frappe.throw("Only HR Managers can approve the Employee.")
