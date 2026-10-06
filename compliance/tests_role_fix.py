from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Department, Document, DocumentReview, DocumentVersion, Role, UserProfile


class RoleAndApproverFixTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="IT")
        self.admin = self.make_user("admin", Role.SYSTEM_ADMIN)
        self.compliance = self.make_user("compliance", Role.COMPLIANCE)
        self.approver = self.make_user("approver", Role.APPROVER)
        self.user = self.make_user("user", Role.USER)

    def make_user(self, username, role):
        user = User.objects.create_user(username=username, password="StrongPassword!123")
        user.profile.role = role
        user.profile.department = self.department
        user.profile.save()
        return user

    def pdf(self, name="test.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4\n% test", content_type="application/pdf")

    def login(self, user):
        self.client.force_login(user)

    def test_reviewer_role_is_not_available(self):
        self.assertNotIn("REVIEWER", {value for value, label in Role.choices})

    def test_legacy_reviewer_value_is_converted_to_user(self):
        user = User.objects.create_user("oldreviewer", password="StrongPassword!123")
        # The old value can still exist in the database even though it is no longer
        # a valid model choice; this simulates a pre-0004 account.
        UserProfile.objects.filter(user=user).update(role="REVIEWER")
        self.assertEqual(UserProfile.objects.get(user=user).role, "REVIEWER")

        # Execute the same data-migration function used by 0004.
        import importlib
        migration = importlib.import_module("compliance.migrations.0004_remove_reviewer_role")
        migration.convert_reviewer_accounts(
            type("Apps", (), {"get_model": staticmethod(lambda app, model: UserProfile)})(),
            None,
        )
        self.assertEqual(UserProfile.objects.get(user=user).role, Role.USER)

    def test_approver_can_open_published_document(self):
        document = Document.objects.create(title="Policy", created_by=self.compliance, state=Document.State.PUBLISHED)
        version = DocumentVersion.objects.create(
            document=document, version="1.0", original_name="policy.pdf", original_file=self.pdf(),
            uploaded_by=self.compliance, status=DocumentVersion.Status.PUBLISHED,
        )
        document.published_version = version
        document.current_version = version
        document.save(update_fields=["published_version", "current_version"])
        self.login(self.approver)
        response = self.client.get(reverse("read_document", args=[document.pk]))
        self.assertEqual(response.status_code, 200)

    def test_approver_can_view_pending_document_before_final_approval(self):
        document = Document.objects.create(title="Policy", created_by=self.compliance, state=Document.State.PENDING_APPROVAL)
        version = DocumentVersion.objects.create(
            document=document, version="1.1", original_name="policy.pdf", original_file=self.pdf(),
            uploaded_by=self.user, status=DocumentVersion.Status.PENDING_APPROVAL,
        )
        document.current_version = version
        document.save(update_fields=["current_version"])
        DocumentReview.objects.create(version=version, reviewer=self.compliance, decision=DocumentReview.Decision.ACCEPTED, remarks="Accepted")
        self.login(self.approver)
        response = self.client.get(reverse("approve_document", args=[version.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review the Document")
        self.assertContains(response, "Final Document Approval")

    def test_user_cannot_access_final_approval(self):
        document = Document.objects.create(title="Policy", created_by=self.compliance, state=Document.State.PENDING_APPROVAL)
        version = DocumentVersion.objects.create(
            document=document, version="1.1", original_name="policy.pdf", original_file=self.pdf(),
            uploaded_by=self.user, status=DocumentVersion.Status.PENDING_APPROVAL,
        )
        self.login(self.user)
        self.assertEqual(self.client.get(reverse("approve_document", args=[version.pk])).status_code, 403)

    def test_approver_cannot_approve_without_compliance_acceptance(self):
        document = Document.objects.create(title="Policy", created_by=self.compliance, state=Document.State.PENDING_APPROVAL)
        version = DocumentVersion.objects.create(
            document=document, version="1.1", original_name="policy.pdf", original_file=self.pdf(),
            uploaded_by=self.user, status=DocumentVersion.Status.PENDING_APPROVAL,
        )
        document.current_version = version
        document.save(update_fields=["current_version"])
        self.login(self.approver)
        self.assertEqual(self.client.get(reverse("approve_document", args=[version.pk])).status_code, 403)
