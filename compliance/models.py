from django.contrib.auth.models import User
from django.db import models


class Role(models.TextChoices):
    SYSTEM_ADMIN = "SYSTEM_ADMIN", "System Admin"
    COMPLIANCE = "COMPLIANCE", "Compliance"
    APPROVER = "APPROVER", "Approver"
    USER = "USER", "User"



class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    message = models.TextField()
    url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="notif_recipient_read_idx"),
            models.Index(fields=["recipient", "-created_at"], name="notif_recipient_date_idx"),
        ]

    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"

class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.USER)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Document(models.Model):
    class State(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Compliance Review"
        REVISION_REQUIRED = "REVISION_REQUIRED", "Revision Required"
        REVIEW_ACCEPTED = "REVIEW_ACCEPTED", "Compliance Review Accepted"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Final Approval"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Blocked / Archived"

    title = models.CharField(max_length=255)
    document_number = models.CharField(max_length=80, blank=True)
    category = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=30, choices=State.choices, default=State.DRAFT)
    current_version = models.ForeignKey("DocumentVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="current_for")
    published_version = models.ForeignKey("DocumentVersion", null=True, blank=True, on_delete=models.SET_NULL, related_name="published_for")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="documents_created")
    created_at = models.DateTimeField(auto_now_add=True)
    class Source(models.TextChoices):
        SYSTEM = "SYSTEM", "Created in Compliance Management System"
        EXISTING = "EXISTING", "Existing Document"

    source = models.CharField(max_length=20, choices=Source.choices, default=Source.SYSTEM)
    archived_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class DocumentVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Compliance Review"
        REVISION_REQUIRED = "REVISION_REQUIRED", "Revision Required"
        REVIEW_ACCEPTED = "REVIEW_ACCEPTED", "Compliance Review Accepted"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Final Approval"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=30)
    original_name = models.CharField(max_length=255)
    original_file = models.FileField(upload_to="documents/originals/%Y/%m/")
    preview_file = models.FileField(upload_to="documents/previews/%Y/%m/", blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="versions_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    publication_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="versions_published")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "version"], name="uniq_document_version")]
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.document.title} v{self.version}"


class DocumentReview(models.Model):
    class Decision(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        REVISION_REQUIRED = "REVISION_REQUIRED", "Revision Required"

    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.PROTECT)
    decision = models.CharField(max_length=30, choices=Decision.choices)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



class DocumentApproval(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    version = models.ForeignKey(DocumentVersion, on_delete=models.PROTECT, related_name="approvals")
    approver = models.ForeignKey(User, on_delete=models.PROTECT, related_name="document_approvals")
    decision = models.CharField(max_length=20, choices=Decision.choices)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReadingRecord(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not Started"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reading_records")
    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE, related_name="reading_records")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "version"], name="uniq_user_version_reading")]
        indexes = [
            models.Index(fields=["status"], name="reading_status_idx"),
            models.Index(fields=["version", "status"], name="reading_version_status_idx"),
        ]


class ComplianceRequest(models.Model):
    class RequestType(models.TextChoices):
        NEW = "NEW_DOCUMENT", "New Document"
        CHANGE = "CHANGE_REQUEST", "Change Request"

    class Status(models.TextChoices):
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Initial Approval"
        APPROVED = "APPROVED", "Request Approved"
        REJECTED = "REJECTED", "Request Rejected"
        IN_PROGRESS = "IN_PROGRESS", "Document Being Prepared"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Compliance Review"
        DOCUMENT_PENDING_APPROVAL = "DOCUMENT_PENDING_APPROVAL", "Document Pending Final Approval"
        DOCUMENT_APPROVED = "DOCUMENT_APPROVED", "Document Approved"
        COMPLETED = "COMPLETED", "Published / Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    request_number = models.CharField(max_length=40, unique=True)
    request_type = models.CharField(max_length=30, choices=RequestType.choices)
    requester = models.ForeignKey(User, on_delete=models.PROTECT, related_name="requests_made")
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    existing_document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.PROTECT, related_name="change_requests")
    requested_title = models.CharField(max_length=255, blank=True)
    requested_change = models.TextField(blank=True)
    reason = models.TextField()
    description = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.PENDING_APPROVAL)
    submitted_at = models.DateTimeField(auto_now_add=True)
    approver = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="requests_approved")
    approval_decision_at = models.DateTimeField(null=True, blank=True)
    approval_comments = models.TextField(blank=True)
    compliance_processor = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="requests_processed")
    processing_at = models.DateTimeField(null=True, blank=True)
    related_document = models.ForeignKey(Document, null=True, blank=True, on_delete=models.SET_NULL, related_name="compliance_requests")
    related_version = models.ForeignKey(DocumentVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="related_requests")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]


class ComplianceRequestHistory(models.Model):
    request = models.ForeignKey(ComplianceRequest, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40)
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]


class SystemSetting(models.Model):
    key = models.CharField(max_length=120, unique=True)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
