from django.contrib.auth.models import User
from django.test import TestCase
from datetime import timedelta
from django.urls import reverse

from .models import (
    ComplianceRequest,
    Department,
    Document,
    DocumentApproval,
    DocumentReview,
    DocumentVersion,
    Notification,
    Role,
)
from .notification_service import (
    notify_document_decision,
    notify_request_decision,
    notify_request_submitted,
)


class NotificationWorkflowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="IT")
        self.user = self.make_user("notif_user", Role.MANAGER)
        self.compliance = self.make_user("notif_compliance", Role.COMPLIANCE)
        self.approver = self.make_user("notif_approver", Role.APPROVER)

        self.req = ComplianceRequest.objects.create(
            request_number="REQ-NOTIF-001",
            request_type=ComplianceRequest.RequestType.NEW,
            requester=self.user,
            department=self.department,
            requested_title="Notification Test",
            reason="Testing notifications",
        )

    def make_user(self, username, role):
        user = User.objects.create_user(username=username, password="StrongPassword!123")
        user.profile.role = role
        user.profile.department = self.department
        user.profile.save()
        return user

    def test_request_submitted_uses_role_correct_urls(self):
        notify_request_submitted(self.req)
        approver_note = Notification.objects.get(recipient=self.approver)
        compliance_note = Notification.objects.get(recipient=self.compliance)
        self.assertEqual(approver_note.url, reverse("approve_request", args=[self.req.pk]))
        self.assertEqual(compliance_note.url, reverse("compliance_queue"))

    def test_request_decision_notification_points_to_request_list(self):
        notify_request_decision(self.req, True)
        note = Notification.objects.get(recipient=self.user)
        self.assertEqual(note.url, reverse("requests"))

    def test_mark_notification_read_requires_csrf_safe_post_and_updates_count(self):
        note = Notification.objects.create(
            recipient=self.user,
            kind="REQUEST_APPROVED",
            title="Request Approved",
            message="Test",
            url=reverse("requests"),
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("notification_read", args=[note.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["unread"], 0)
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_user_cannot_mark_another_users_notification_read(self):
        other = User.objects.create_user("other", password="StrongPassword!123")
        other.profile.role = Role.MANAGER
        other.profile.department = self.department
        other.profile.save()
        note = Notification.objects.create(
            recipient=other,
            kind="REQUEST_APPROVED",
            title="Request Approved",
            message="Test",
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("notification_read", args=[note.pk]))
        self.assertEqual(response.status_code, 404)

    def test_request_notification_does_not_use_old_invalid_approval_path(self):
        notify_request_submitted(self.req)
        note = Notification.objects.get(recipient=self.approver)
        self.assertNotEqual(note.url, f"/approvals/{self.req.pk}/")
        self.assertEqual(note.url, f"/approvals/requests/{self.req.pk}/")

    def test_stale_request_approval_notification_is_retargeted_to_live_queue(self):
        notify_request_submitted(self.req)
        stale = Notification.objects.get(
            recipient=self.approver,
            kind="REQUEST_PENDING_APPROVAL",
        )
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("approve_request", args=[self.req.pk]),
            {"approval_comments": "Approved", "decision": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        stale.refresh_from_db()
        self.assertEqual(stale.url, reverse("approval_queue"))
        response = self.client.get(stale.url)
        self.assertEqual(response.status_code, 200)


class NotificationPublicationRegressionTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="IT")
        self.user = self.make_user("reg_user", Role.MANAGER)
        self.compliance = self.make_user("reg_compliance", Role.COMPLIANCE)
        self.approver = self.make_user("reg_approver", Role.APPROVER)

    def make_user(self, username, role):
        user = User.objects.create_user(username=username, password="StrongPassword!123")
        user.profile.role = role
        user.profile.department = self.department
        user.profile.save()
        return user

    def pdf(self, name="test.pdf"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(name, b"%PDF-1.4\n% test", content_type="application/pdf")

    def pending_document(self, title="Approved Document", version_number="1.0"):
        doc = Document.objects.create(title=title, created_by=self.compliance, state=Document.State.PENDING_APPROVAL)
        version = DocumentVersion.objects.create(
            document=doc, version=version_number, original_name=f"{version_number}.pdf",
            original_file=self.pdf(f"{version_number}.pdf"),
            status=DocumentVersion.Status.PENDING_APPROVAL, uploaded_by=self.compliance,
        )
        doc.current_version = version
        doc.save(update_fields=["current_version"])
        DocumentReview.objects.create(version=version, reviewer=self.compliance, decision=DocumentReview.Decision.ACCEPTED)
        return doc, version

    def test_approved_document_notification_opens_exact_document(self):
        doc, version = self.pending_document()
        # This regression test must represent the post-approval state.
        # The Compliance document page only exposes the publish action after
        # final approval has changed the version to REVIEW_ACCEPTED and an
        # APPROVED DocumentApproval record exists.
        version.status = DocumentVersion.Status.REVIEW_ACCEPTED
        version.save(update_fields=["status"])
        DocumentApproval.objects.create(
            version=version,
            approver=self.approver,
            decision=DocumentApproval.Decision.APPROVED,
            remarks="Approved for publication",
        )
        from .notification_service import notify_document_decision
        notify_document_decision(None, version, True)
        note = Notification.objects.get(recipient=self.compliance, kind="DOCUMENT_APPROVED")
        self.assertEqual(note.url, reverse("document_detail", args=[doc.pk]))
        self.client.force_login(self.compliance)
        response = self.client.get(note.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, doc.title)
        self.assertContains(response, "Publish Approved Document")

    def test_opening_stale_document_notification_returns_queue(self):
        doc, version = self.pending_document("Stale Document Open")
        from .notification_service import notify_document_decision
        notify_document_decision(None, version, True)
        note = Notification.objects.get(recipient=self.compliance, kind="DOCUMENT_APPROVED")
        version.status = DocumentVersion.Status.PUBLISHED
        version.save(update_fields=["status"])
        self.client.force_login(self.approver)
        response = self.client.get(reverse("approve_document", args=[version.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("approval_queue"))


    def test_approver_opening_already_processed_document_notification_returns_queue(self):
        doc, version = self.pending_document("Processed Document")
        from .notification_service import notify_document_review_result
        notify_document_review_result(None, version, True)
        note = Notification.objects.get(recipient=self.approver, kind="DOCUMENT_PENDING_FINAL_APPROVAL")
        version.status = DocumentVersion.Status.REVIEW_ACCEPTED
        version.save(update_fields=["status"])
        self.client.force_login(self.approver)
        response = self.client.get(note.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("approval_queue"))

    def test_stale_document_final_approval_notification_is_retargeted_to_live_queue(self):
        doc, version = self.pending_document("Retargeted Document")
        from .notification_service import notify_document_review_result
        notify_document_review_result(None, version, True)
        stale = Notification.objects.get(
            recipient=self.approver,
            kind="DOCUMENT_PENDING_FINAL_APPROVAL",
        )
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("approve_document", args=[version.pk]),
            {"approval_comments": "Approved", "decision": "approve"},
        )
        self.assertEqual(response.status_code, 302)
        stale.refresh_from_db()
        self.assertEqual(stale.url, reverse("approval_queue"))
        response = self.client.get(stale.url)
        self.assertEqual(response.status_code, 200)

    def test_document_approval_notification_targets_exact_document(self):
        doc, version = self.pending_document("Stale Document")
        from .notification_service import notify_document_decision
        notify_document_decision(None, version, True)
        note = Notification.objects.get(recipient=self.compliance, kind="DOCUMENT_APPROVED")
        self.assertEqual(note.url, reverse("document_detail", args=[doc.pk]))

    def test_published_documents_order_by_latest_publication(self):
        from django.utils import timezone
        from datetime import timedelta
        older = Document.objects.create(title="Older", created_by=self.compliance, state=Document.State.PUBLISHED)
        newer = Document.objects.create(title="Newer", created_by=self.compliance, state=Document.State.PUBLISHED)
        oldv = DocumentVersion.objects.create(document=older, version="1.0", original_name="old.pdf", original_file=self.pdf("old.pdf"), status=DocumentVersion.Status.PUBLISHED, uploaded_by=self.compliance, publication_at=timezone.now()-timedelta(days=1), published_by=self.compliance)
        newv = DocumentVersion.objects.create(document=newer, version="1.0", original_name="new.pdf", original_file=self.pdf("new.pdf"), status=DocumentVersion.Status.PUBLISHED, uploaded_by=self.compliance, publication_at=timezone.now(), published_by=self.compliance)
        older.current_version=oldv; older.published_version=oldv; older.save(update_fields=["current_version","published_version"])
        newer.current_version=newv; newer.published_version=newv; newer.save(update_fields=["current_version","published_version"])
        self.client.force_login(self.user)
        response=self.client.get(reverse("published_documents"))
        self.assertEqual(response.status_code,200)
        docs=list(response.context["documents"])
        self.assertEqual(docs[0].pk,newer.pk)
        self.assertContains(response,"Published Date")

    def test_newer_changed_version_moves_document_to_top(self):
        from django.utils import timezone
        older = Document.objects.create(title="Stable", created_by=self.compliance, state=Document.State.PUBLISHED)
        changed = Document.objects.create(title="Changed", created_by=self.compliance, state=Document.State.PUBLISHED)
        t1=timezone.now()
        v1=DocumentVersion.objects.create(document=older, version="1.0", original_name="a.pdf", original_file=self.pdf("a.pdf"), status=DocumentVersion.Status.PUBLISHED, uploaded_by=self.compliance, publication_at=t1, published_by=self.compliance)
        v2=DocumentVersion.objects.create(document=changed, version="1.0", original_name="b.pdf", original_file=self.pdf("b.pdf"), status=DocumentVersion.Status.PUBLISHED, uploaded_by=self.compliance, publication_at=t1+timedelta(minutes=1), published_by=self.compliance)
        older.current_version=older.published_version=v1; older.save(update_fields=["current_version","published_version"])
        changed.current_version=changed.published_version=v2; changed.save(update_fields=["current_version","published_version"])
        self.client.force_login(self.user)
        response=self.client.get(reverse("published_documents"))
        self.assertEqual(list(response.context["documents"])[0].pk,changed.pk)
