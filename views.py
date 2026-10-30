from pathlib import Path
import os
import tempfile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import *
from .models import *
from .services import (
    _find_libreoffice,
    audit,
    backup_to_zip,
    create_version,
    delete_version,
    restore_from_zip,
    role_required,
    transition_document,
    transition_request,
    version_preview,
)
from .reports import reading_csv, reading_pdf
from .notification_service import (
    notify_request_submitted,
    notify_request_decision,
    notify_document_uploaded,
    notify_document_review_result,
    notify_document_decision,
    notify_document_published,
)


READ_ROLES = (Role.USER, Role.COMPLIANCE, Role.APPROVER)


def require(request, *roles):
    if not role_required(request, *roles):
        raise PermissionDenied


def active_users():
    return User.objects.filter(is_active=True, profile__active=True, profile__role=Role.USER).select_related("profile__department")


def published_versions():
    return DocumentVersion.objects.filter(
        status=DocumentVersion.Status.PUBLISHED,
        document__published_version__isnull=False,
        document__archived_at__isnull=True,
    ).select_related("document")



@login_required
def dashboard(request):
    """Render role-specific dashboard metrics and safe, read-only summaries."""
    from django.contrib.sessions.models import Session

    role = request.user.profile.role
    context = {
        "notification_unread_count": request.user.notifications.filter(is_read=False).count(),
    }

    def chart_item(label, count, total, tone="blue"):
        count = int(count or 0)
        return {"label": label, "count": count, "percent": round(count * 100 / total) if total else 0, "tone": tone}

    def request_status_chart(queryset):
        total = queryset.count()
        groups = [
            ("Awaiting approval", queryset.filter(status=ComplianceRequest.Status.PENDING_APPROVAL).count(), "amber"),
            ("Approved", queryset.filter(status=ComplianceRequest.Status.APPROVED).count(), "blue"),
            ("In progress", queryset.filter(status=ComplianceRequest.Status.IN_PROGRESS).count(), "blue"),
            ("Compliance review", queryset.filter(status=ComplianceRequest.Status.UNDER_REVIEW).count(), "cyan"),
            ("Final approval / document approved", queryset.filter(status__in=[ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL, ComplianceRequest.Status.DOCUMENT_APPROVED]).count(), "violet"),
            ("Published / completed", queryset.filter(status=ComplianceRequest.Status.COMPLETED).count(), "green"),
            ("Rejected", queryset.filter(status=ComplianceRequest.Status.REJECTED).count(), "red"),
            ("Cancelled", queryset.filter(status=ComplianceRequest.Status.CANCELLED).count(), "gray"),
        ]
        return [chart_item(label, count, total, tone) for label, count, tone in groups]

    if role == Role.COMPLIANCE:
        versions = list(published_versions().order_by("document__title"))
        users = list(active_users())
        rows = []
        total_expected = len(versions) * len(users)
        completed_total = 0
        in_progress_total = 0