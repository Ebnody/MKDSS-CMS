from django.contrib import admin
from .models import (
    AuditLog,
    ComplianceRequest,
    ComplianceRequestHistory,
    Department,
    Document,
    DocumentApproval,
    DocumentReview,
    DocumentVersion,
    ReadingRecord,
    SystemSetting,
    UserProfile,
)

admin.site.register([
    Department,
    UserProfile,
    Document,
    DocumentVersion,
    DocumentReview,
    DocumentApproval,
    ReadingRecord,
    ComplianceRequest,
    ComplianceRequestHistory,
    AuditLog,
    SystemSetting,
])
