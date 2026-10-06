import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    ComplianceRequest,
    ComplianceRequestHistory,
    Notification,
    Department,
    Document,
    DocumentApproval,
    DocumentVersion,
    ReadingRecord,
    Role,
)
from .services import DOCUMENT_TRANSITIONS, REQUEST_TRANSITIONS, transition_document, transition_request


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"


class BaseTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(
            MEDIA_ROOT=self.media.name,
            MAX_UPLOAD_MB=50,
            DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
        )
        self.override.enable()
        self.dept = Department.objects.create(name="IT")
        self.users = {}
        for role, username in [
            (Role.SYSTEM_ADMIN, "admin"),
            (Role.COMPLIANCE, "compliance"),
            (Role.APPROVER, "approver"),
            (Role.USER, "reader"),
        ]:
            user = User.objects.create_user(username=username, password="StrongPassword!123")
            user.profile.role = role
            user.profile.department = self.dept
            user.profile.save()
            self.users[role] = user

    def tearDown(self):
        self.override.disable()
        self.media.cleanup()

    def login(self, role):
        self.client.force_login(self.users[role])

    def pdf(self, name="policy.pdf"):
        return SimpleUploadedFile(name, PDF, content_type="application/pdf")

    def published_doc(self, version="1.0"):
        doc = Document.objects.create(
            title="Policy",
            document_number="POL-001",
            category="Security",
            created_by=self.users[Role.COMPLIANCE],
            state=Document.State.PUBLISHED,
        )
        current = DocumentVersion.objects.create(
            document=doc,
            version=version,
            original_name=f"policy-{version}.pdf",
            original_file=self.pdf(f"policy-{version}.pdf"),
            mime_type="application/pdf",
            status=DocumentVersion.Status.PUBLISHED,
            uploaded_by=self.users[Role.COMPLIANCE],
            published_by=self.users[Role.COMPLIANCE],
        )
        doc.current_version = current
        doc.published_version = current
        doc.save(update_fields=["current_version", "published_version"])
        return doc, current


class RoleMatrixTests(BaseTests):
    def test_system_admin_cannot_read_published_documents(self):
        doc, _ = self.published_doc()
        self.login(Role.SYSTEM_ADMIN)
        self.assertEqual(self.client.get(reverse("published_documents")).status_code, 403)
        self.assertEqual(self.client.get(reverse("read_document", args=[doc.pk])).status_code, 403)

    def test_all_non_admin_roles_can_read_published_documents(self):
        doc, _ = self.published_doc()
        for role in [Role.USER, Role.COMPLIANCE, Role.APPROVER]:
            self.login(role)
            self.assertEqual(self.client.get(reverse("published_documents")).status_code, 200)
            self.assertEqual(self.client.get(reverse("read_document", args=[doc.pk])).status_code, 200)

    def test_compliance_is_the_only_document_reviewer(self):
        doc = Document.objects.create(title="Review", created_by=self.users[Role.USER], state=Document.State.UNDER_REVIEW)
        version = DocumentVersion.objects.create(
            document=doc, version="1.0", original_name="review.pdf", original_file=self.pdf("review.pdf"),
            mime_type="application/pdf", status=DocumentVersion.Status.UNDER_REVIEW, uploaded_by=self.users[Role.USER]
        )
        doc.current_version = version
        doc.save(update_fields=["current_version"])
        self.login(Role.USER)
        self.assertEqual(self.client.get(reverse("review_queue")).status_code, 403)
        self.login(Role.APPROVER)
        self.assertEqual(self.client.get(reverse("review_queue")).status_code, 403)
        self.login(Role.COMPLIANCE)
        self.assertEqual(self.client.get(reverse("review_queue")).status_code, 200)

    def test_approver_cannot_submit_requests(self):
        self.login(Role.APPROVER)
        self.assertEqual(self.client.get(reverse("new_request")).status_code, 403)
        self.assertEqual(self.client.get(reverse("change_request")).status_code, 403)

    def test_compliance_cannot_approve(self):
        self.login(Role.COMPLIANCE)
        self.assertEqual(self.client.get(reverse("approval_queue")).status_code, 403)

    def test_system_admin_has_no_document_workflow_access(self):
        self.login(Role.SYSTEM_ADMIN)
        for name in ["compliance_documents", "review_queue", "approval_queue", "published_documents"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)


class ComplianceOwnApprovedRequestUploadTests(BaseTests):
    def test_compliance_can_upload_own_approved_request(self):
        self.login(Role.COMPLIANCE)
        response = self.client.post(reverse("new_request"), {
            "requested_title": "Compliance Requested Procedure",
            "department": self.department.pk,
            "reason": "Compliance needs a controlled procedure.",
            "description": "Requested by Compliance.",
            "additional_notes": "",
        })
        self.assertEqual(response.status_code, 302)
        req = ComplianceRequest.objects.latest("id")

        self.login(Role.APPROVER)
        response = self.client.post(reverse("approve_request", args=[req.pk]), {
            "decision": "approve",
            "approval_comments": "Approved.",
        })
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.APPROVED)

        self.login(Role.COMPLIANCE)
        response = self.client.get(reverse("process_request", args=[req.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse("process_request", args=[req.pk]), {
            "title": "Compliance Requested Procedure",
            "document_number": "CMP-001",
            "category": "Compliance",
            "version": "1.0",
            "original_file": self.pdf("compliance-request.pdf"),
        })
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.UNDER_REVIEW)


class ExistingDocumentUploadTests(BaseTests):
    def test_only_compliance_can_upload_existing_documents(self):
        for role in [Role.USER, Role.APPROVER, Role.SYSTEM_ADMIN]:
            self.login(role)
            self.assertEqual(self.client.get(reverse("upload_existing_document")).status_code, 403)

        self.login(Role.COMPLIANCE)
        response = self.client.get(reverse("upload_existing_document"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload Existing Document")

    def test_existing_document_enters_compliance_review_without_request(self):
        self.login(Role.COMPLIANCE)
        response = self.client.post(reverse("upload_existing_document"), {
            "title": "Legacy Access Control Procedure",
            "document_number": "LEG-001",
            "category": "Access Control",
            "version": "1.0",
            "original_file": self.pdf("legacy-procedure.pdf"),
        })
        self.assertEqual(response.status_code, 302)
        doc = Document.objects.get(title="Legacy Access Control Procedure")
        version = doc.current_version
        self.assertEqual(doc.source, Document.Source.EXISTING)
        self.assertEqual(doc.state, Document.State.UNDER_REVIEW)
        self.assertEqual(version.status, DocumentVersion.Status.UNDER_REVIEW)
        self.assertFalse(ComplianceRequest.objects.filter(related_document=doc).exists())

        self.login(Role.COMPLIANCE)
        self.client.post(reverse("review_document", args=[doc.pk]), {
            "decision": "ACCEPTED", "remarks": "Existing document reviewed."
        })
        version.refresh_from_db()
        doc.refresh_from_db()
        self.assertEqual(version.status, DocumentVersion.Status.PENDING_APPROVAL)
        self.assertEqual(doc.state, Document.State.PENDING_APPROVAL)

        self.login(Role.APPROVER)
        self.client.post(reverse("approve_document", args=[version.pk]), {
            "approval_comments": "Final approval of legacy document.", "decision": "approve"
        })
        version.refresh_from_db()
        self.assertEqual(version.status, DocumentVersion.Status.REVIEW_ACCEPTED)

        self.login(Role.COMPLIANCE)
        self.client.post(reverse("publish_document", args=[doc.pk]))
        doc.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(doc.state, Document.State.PUBLISHED)
        self.assertEqual(version.status, DocumentVersion.Status.PUBLISHED)


class AdminAndApprovalPageTests(BaseTests):
    def test_system_admin_can_open_system_health(self):
        self.login(Role.SYSTEM_ADMIN)
        response = self.client.get(reverse("admin_health"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "System Health")
        self.assertContains(response, "Database")
        self.assertContains(response, "Document Storage")
        self.assertContains(response, "LibreOffice")

    def test_approver_can_open_approval_queue_and_pending_request(self):
        req = ComplianceRequest.objects.create(
            request_number="REQ-PAGE-001",
            request_type=ComplianceRequest.RequestType.NEW,
            requester=self.users[Role.USER],
            department=self.dept,
            requested_title="Approval Page Test",
            reason="Page test",
            status=ComplianceRequest.Status.PENDING_APPROVAL,
        )
        self.login(Role.APPROVER)
        queue = self.client.get(reverse("approval_queue"))
        self.assertEqual(queue.status_code, 200)
        self.assertContains(queue, req.request_number)

        detail = self.client.get(reverse("approve_request", args=[req.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, req.request_number)


class RequestWorkflowTests(BaseTests):
    def test_user_request_approval_upload_compliance_review_final_approval_publish(self):
        self.login(Role.USER)
        response = self.client.post(reverse("new_request"), {
            "requested_title": "New Procedure",
            "department": self.dept.pk,
            "reason": "Business need",
            "description": "Detailed requirement",
            "additional_notes": "",
        })
        self.assertEqual(response.status_code, 302)
        req = ComplianceRequest.objects.get(requested_title="New Procedure")
        self.assertEqual(req.status, ComplianceRequest.Status.PENDING_APPROVAL)

        self.login(Role.COMPLIANCE)
        self.assertEqual(self.client.get(reverse("compliance_queue")).status_code, 200)
        self.assertEqual(self.client.get(reverse("process_request", args=[req.pk])).status_code, 403)

        self.login(Role.APPROVER)
        self.client.post(reverse("approve_request", args=[req.pk]), {"approval_comments": "Approved", "decision": "approve"})
        req.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.APPROVED)

        self.login(Role.USER)
        self.client.post(reverse("process_request", args=[req.pk]), {
            "title": "New Procedure",
            "document_number": "PROC-001",
            "category": "Operations",
            "version": "1.0",
            "original_file": self.pdf("procedure.pdf"),
        })
        req.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.UNDER_REVIEW)
        self.assertIsNotNone(req.related_version_id)

        self.login(Role.COMPLIANCE)
        self.client.post(reverse("review_document", args=[req.related_document_id]), {"decision": "ACCEPTED", "remarks": "Accepted."})
        req.refresh_from_db()
        version = req.related_version
        self.assertEqual(req.status, ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL)
        self.assertEqual(version.status, DocumentVersion.Status.PENDING_APPROVAL)

        self.login(Role.APPROVER)
        self.client.post(reverse("approve_document", args=[version.pk]), {"approval_comments": "Final approval", "decision": "approve"})
        req.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.DOCUMENT_APPROVED)
        self.assertEqual(version.status, DocumentVersion.Status.REVIEW_ACCEPTED)
        self.assertTrue(DocumentApproval.objects.filter(version=version, decision="APPROVED").exists())

        self.login(Role.COMPLIANCE)
        self.client.post(reverse("publish_document", args=[req.related_document_id]))
        req.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.COMPLETED)
        self.assertEqual(version.status, DocumentVersion.Status.PUBLISHED)
        self.assertTrue(ComplianceRequestHistory.objects.filter(request=req, to_status=ComplianceRequest.Status.COMPLETED).exists())

    def test_compliance_can_request_and_upload_own_document(self):
        self.login(Role.COMPLIANCE)
        self.client.post(reverse("new_request"), {
            "requested_title": "Compliance Procedure",
            "department": self.dept.pk,
            "reason": "Required control",
            "description": "Compliance-authored document",
            "additional_notes": "",
        })
        req = ComplianceRequest.objects.get(requested_title="Compliance Procedure")
        self.login(Role.APPROVER)
        self.client.post(reverse("approve_request", args=[req.pk]), {"approval_comments": "Approved", "decision": "approve"})
        self.login(Role.COMPLIANCE)
        response = self.client.post(reverse("process_request", args=[req.pk]), {
            "title": "Compliance Procedure",
            "document_number": "CMP-001",
            "category": "Compliance",
            "version": "1.0",
            "original_file": self.pdf("cmp.pdf"),
        })
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, ComplianceRequest.Status.UNDER_REVIEW)
        self.assertEqual(req.requester_id, self.users[Role.COMPLIANCE].id)

    def test_compliance_cannot_upload_for_another_users_request(self):
        self.login(Role.USER)
        self.client.post(reverse("new_request"), {
            "requested_title": "Other Procedure",
            "department": self.dept.pk,
            "reason": "Need",
            "description": "Description",
            "additional_notes": "",
        })
        req = ComplianceRequest.objects.get(requested_title="Other Procedure")
        self.login(Role.APPROVER)
        self.client.post(reverse("approve_request", args=[req.pk]), {"approval_comments": "Approved", "decision": "approve"})
        self.login(Role.COMPLIANCE)
        self.assertEqual(self.client.get(reverse("process_request", args=[req.pk])).status_code, 403)


class DocumentApprovalAndVersionTests(BaseTests):
    def test_change_keeps_old_published_until_new_version_is_published_then_deletes_it(self):
        doc, old = self.published_doc("1.0")
        self.login(Role.USER)
        self.client.post(reverse("change_request"), {
            "existing_document": doc.pk,
            "department": self.dept.pk,
            "requested_change": "Update section 4",
            "reason": "Regulatory update",
            "additional_notes": "",
        })
        req = ComplianceRequest.objects.get(existing_document=doc)
        self.login(Role.APPROVER)
        self.client.post(reverse("approve_request", args=[req.pk]), {"approval_comments": "Approved", "decision": "approve"})
        self.login(Role.USER)
        self.client.post(reverse("process_request", args=[req.pk]), {"version": "1.1", "original_file": self.pdf("policy11.pdf")})
        self.assertTrue(DocumentVersion.objects.filter(pk=old.pk).exists())
        req.refresh_from_db()
        self.login(Role.COMPLIANCE)
        self.client.post(reverse("review_document", args=[doc.pk]), {"decision": "ACCEPTED", "remarks": "Accepted."})
        version = req.related_version
        self.login(Role.APPROVER)
        self.client.post(reverse("approve_document", args=[version.pk]), {"approval_comments": "Approved", "decision": "approve"})
        self.login(Role.COMPLIANCE)
        self.client.post(reverse("publish_document", args=[doc.pk]))
        doc.refresh_from_db()
        self.assertEqual(doc.published_version.version, "1.1")
        self.assertFalse(DocumentVersion.objects.filter(pk=old.pk).exists())

    def test_compliance_review_revision_removes_old_unpublished_working_version(self):
        self.login(Role.USER)
        req = ComplianceRequest.objects.create(
            request_number="REQ-REV-001",
            request_type=ComplianceRequest.RequestType.NEW,
            requester=self.users[Role.USER],
            department=self.dept,
            requested_title="New",
            reason="Need",
            status=ComplianceRequest.Status.APPROVED,
        )
        self.client.post(reverse("process_request", args=[req.pk]), {"title":"New","version":"1.0","original_file":self.pdf("v1.pdf")})
        req.refresh_from_db()
        old_working = req.related_version
        self.login(Role.COMPLIANCE)
        doc = req.related_document
        self.client.post(reverse("review_document", args=[doc.pk]), {"decision":"REVISION_REQUIRED","remarks":"Correct it"})
        self.assertEqual(DocumentVersion.objects.get(pk=old_working.pk).status, DocumentVersion.Status.REVISION_REQUIRED)
        self.login(Role.USER)
        self.client.post(reverse("process_request", args=[req.pk]), {"version":"1.1","original_file":self.pdf("v2.pdf")})
        self.assertFalse(DocumentVersion.objects.filter(pk=old_working.pk).exists())
        self.assertEqual(DocumentVersion.objects.filter(document=doc).count(), 1)


class ComplianceDocumentControlTests(BaseTests):
    def test_compliance_can_edit_block_unblock_and_delete_published_document(self):
        doc, _ = self.published_doc()
        self.login(Role.COMPLIANCE)
        self.client.post(reverse("edit_document", args=[doc.pk]), {"title":"Edited Policy","document_number":"POL-009","category":"Updated"})
        doc.refresh_from_db()
        self.assertEqual(doc.title, "Edited Policy")
        self.client.post(reverse("block_document", args=[doc.pk]))
        doc.refresh_from_db()
        self.assertEqual(doc.state, Document.State.ARCHIVED)
        self.assertEqual(self.client.get(reverse("published_documents")).status_code, 200)
        self.client.post(reverse("unblock_document", args=[doc.pk]))
        doc.refresh_from_db()
        self.assertEqual(doc.state, Document.State.PUBLISHED)
        self.client.post(reverse("delete_document", args=[doc.pk]))
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())
        self.assertFalse(DocumentVersion.objects.filter(document_id=doc.pk).exists())


class ReadingTests(BaseTests):
    def test_finish_reading_is_explicit_for_all_read_roles(self):
        doc, version = self.published_doc()
        for role in [Role.USER, Role.COMPLIANCE, Role.APPROVER]:
            self.login(role)
            self.client.get(reverse("read_document", args=[doc.pk]))
            record = ReadingRecord.objects.get(user=self.users[role], version=version)
            self.assertEqual(record.status, ReadingRecord.Status.IN_PROGRESS)
            self.assertEqual(self.client.get(reverse("finish_reading", args=[version.pk])).status_code, 403)
            self.client.post(reverse("finish_reading", args=[version.pk]))
            record.refresh_from_db()
            self.assertEqual(record.status, ReadingRecord.Status.COMPLETED)


class AdminTests(BaseTests):
    def test_system_admin_can_block_edit_and_delete_unreferenced_user(self):
        user = User.objects.create_user(username="temporary", password="StrongPassword!123")
        user.profile.role = Role.USER
        user.profile.department = self.dept
        user.profile.save()
        self.login(Role.SYSTEM_ADMIN)
        self.client.post(reverse("admin_user_toggle", args=[user.pk]))
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.client.post(reverse("admin_user_toggle", args=[user.pk]))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.client.post(reverse("admin_user_delete", args=[user.pk]))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())


class TransitionTests(TestCase):
    def test_document_requires_final_approval_before_publish(self):
        self.assertIn(Document.State.PENDING_APPROVAL, DOCUMENT_TRANSITIONS[Document.State.REVIEW_ACCEPTED])
        self.assertIn(Document.State.PUBLISHED, DOCUMENT_TRANSITIONS[Document.State.PENDING_APPROVAL])

    def test_request_requires_document_approval_before_completion(self):
        self.assertIn(ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL, REQUEST_TRANSITIONS[ComplianceRequest.Status.UNDER_REVIEW])
        self.assertIn(ComplianceRequest.Status.DOCUMENT_APPROVED, REQUEST_TRANSITIONS[ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL])
        self.assertIn(ComplianceRequest.Status.COMPLETED, REQUEST_TRANSITIONS[ComplianceRequest.Status.DOCUMENT_APPROVED])

    def test_invalid_request_transition_is_rejected(self):
        req = ComplianceRequest(status=ComplianceRequest.Status.REJECTED)
        with self.assertRaises(ValueError):
            transition_request(req, ComplianceRequest.Status.COMPLETED)


class SystemAdminBootstrapTests(TestCase):
    def test_existing_user_can_be_promoted_to_system_admin(self):
        user = User.objects.create_user(username="bootstrap", password="StrongPass123!")
        call_command("create_system_admin", username="bootstrap")
        user.refresh_from_db()
        self.assertEqual(user.profile.role, Role.SYSTEM_ADMIN)
        self.assertTrue(user.profile.active)


class NotificationAndApprovalHistoryTests(BaseTests):
    def make_pending_request(self, number="REQ-NOTIFY-001"):
        return ComplianceRequest.objects.create(
            request_number=number,
            request_type=ComplianceRequest.RequestType.NEW,
            requester=self.users[Role.USER],
            department=self.dept,
            requested_title="Notification Test",
            reason="Testing workflow notifications",
            status=ComplianceRequest.Status.PENDING_APPROVAL,
        )

    def test_approver_sees_initial_approval_history_after_decision(self):
        req = self.make_pending_request("REQ-HISTORY-001")
        self.login(Role.APPROVER)
        response = self.client.post(
            reverse("approve_request", args=[req.pk]),
            {"approval_comments": "Approved for processing", "decision": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        history_page = self.client.get(reverse("approval_queue"))
        self.assertEqual(history_page.status_code, 200)
        self.assertContains(history_page, req.request_number)
        self.assertContains(history_page, "Approved")
        self.assertContains(history_page, "Approved for processing")

    def test_document_upload_notifies_compliance(self):
        req = self.make_pending_request("REQ-UPLOAD-001")
        self.login(Role.APPROVER)
        self.client.post(
            reverse("approve_request", args=[req.pk]),
            {"approval_comments": "Approved", "decision": "approve"},
        )
        self.login(Role.USER)
        self.client.post(reverse("process_request", args=[req.pk]), {
            "title": "Uploaded Procedure",
            "document_number": "DOC-001",
            "category": "Operations",
            "version": "1.0",
            "original_file": self.pdf("uploaded.pdf"),
        })
        notification = Notification.objects.filter(
            recipient=self.users[Role.COMPLIANCE],
            kind="DOCUMENT_UPLOADED_FOR_REVIEW",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn(req.request_number, notification.message)
        self.assertEqual(notification.url, reverse("compliance_queue"))

    def test_compliance_review_acceptance_notifies_approver(self):
        req = self.make_pending_request("REQ-REVIEW-001")
        self.login(Role.APPROVER)
        self.client.post(
            reverse("approve_request", args=[req.pk]),
            {"approval_comments": "Approved", "decision": "approve"},
        )
        self.login(Role.USER)
        self.client.post(reverse("process_request", args=[req.pk]), {
            "title": "Review Procedure",
            "document_number": "DOC-002",
            "category": "Operations",
            "version": "1.0",
            "original_file": self.pdf("review.pdf"),
        })
        req.refresh_from_db()
        self.login(Role.COMPLIANCE)
        self.client.post(
            reverse("review_document", args=[req.related_document_id]),
            {"decision": "ACCEPTED", "remarks": "Compliance accepted."},
        )
        notification = Notification.objects.filter(
            recipient=self.users[Role.APPROVER],
            kind="DOCUMENT_PENDING_FINAL_APPROVAL",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("Review Procedure", notification.message)
        self.assertEqual(notification.url, reverse("approve_document", args=[req.related_version_id]))

    def test_request_rejection_notifies_compliance(self):
        req = self.make_pending_request("REQ-REJECT-001")
        self.login(Role.APPROVER)
        self.client.post(
            reverse("approve_request", args=[req.pk]),
            {"approval_comments": "Not approved", "decision": "reject"},
        )
        notification = Notification.objects.filter(
            recipient=self.users[Role.COMPLIANCE],
            kind="REQUEST_REJECTED",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn(req.request_number, notification.message)

