from django.contrib.auth.models import User
from django.urls import reverse

from .models import Notification, Role


def notify_user(user, kind, title, message, url=""):
    if not user or not getattr(user, "is_active", False):
        return None
    return Notification.objects.create(
        recipient=user,
        kind=kind,
        title=title,
        message=message,
        url=url or "",
    )


def notify_users(users, kind, title, message, url="", exclude_ids=None):
    excluded = {int(x) for x in (exclude_ids or [])}
    seen = set()
    objects = []
    for user in users:
        if not user or not user.is_active or user.pk in excluded or user.pk in seen:
            continue
        seen.add(user.pk)
        objects.append(Notification(
            recipient=user,
            kind=kind,
            title=title,
            message=message,
            url=url or "",
        ))
    if objects:
        Notification.objects.bulk_create(objects)
    return objects


def notify_request_submitted(req, _legacy_url=None):
    """Notify each role with a destination that role is actually allowed to open."""
    approver_url = reverse("approve_request", args=[req.pk])
    compliance_url = reverse("compliance_queue")

    approvers = User.objects.filter(
        is_active=True,
        profile__active=True,
        profile__role=Role.APPROVER,
    )
    notify_users(
        approvers,
        "REQUEST_PENDING_APPROVAL",
        "Request Requires Approval",
        f"Request {req.request_number} from {req.requester.get_username()} is waiting for your approval.",
        approver_url,
    )

    compliance_users = User.objects.filter(
        is_active=True,
        profile__active=True,
        profile__role=Role.COMPLIANCE,
    )
    notify_users(
        compliance_users,
        "REQUEST_SUBMITTED",
        "New Request Submitted",
        f"Request {req.request_number} has been submitted and is awaiting processing.",
        compliance_url,
    )


def retarget_request_approval_notifications(req):
    """Retarget stale initial-approval notifications after a request is decided."""
    old_url = reverse("approve_request", args=[req.pk])
    return Notification.objects.filter(
        kind="REQUEST_PENDING_APPROVAL",
        url=old_url,
    ).update(url=reverse("approval_queue"))


def retarget_document_approval_notifications(version):
    """Retarget stale final-approval notifications after a version is decided."""
    old_url = reverse("approve_document", args=[version.pk])
    return Notification.objects.filter(
        kind="DOCUMENT_PENDING_FINAL_APPROVAL",
        url=old_url,
    ).update(url=reverse("approval_queue"))


def notify_request_decision(req, approved, _legacy_url=None):
    retarget_request_approval_notifications(req)
    title = "Request Approved" if approved else "Request Rejected"
    message = (
        f"Request {req.request_number} has been approved by the Approver."
        if approved
        else f"Request {req.request_number} has been rejected by the Approver."
    )

    # Requester can open their request list; it is available to Users and Compliance.
    notify_user(
        req.requester,
        "REQUEST_APPROVED" if approved else "REQUEST_REJECTED",
        title,
        message,
        reverse("requests"),
    )

    compliance_users = User.objects.filter(
        is_active=True,
        profile__active=True,
        profile__role=Role.COMPLIANCE,
    )
    notify_users(
        compliance_users,
        "REQUEST_APPROVED" if approved else "REQUEST_REJECTED",
        title,
        message,
        reverse("compliance_queue"),
    )


def notify_document_uploaded(req, version, _legacy_url=None):
    """Notify Compliance immediately when an approved request receives its document upload."""
    compliance_users = User.objects.filter(
        is_active=True,
        profile__active=True,
        profile__role=Role.COMPLIANCE,
    )
    notify_users(
        compliance_users,
        "DOCUMENT_UPLOADED_FOR_REVIEW",
        "Document Uploaded for Compliance Review",
        f"{version.document.title} v{version.version} was uploaded for request {req.request_number} and is waiting for Compliance review.",
        reverse("compliance_queue"),
    )
    notify_user(
        req.requester,
        "DOCUMENT_UPLOAD_RECEIVED",
        "Document Upload Received",
        f"Your document for request {req.request_number} was uploaded and sent to Compliance for review.",
        reverse("requests"),
    )


def notify_document_review_result(req, version, accepted, _legacy_url=None):
    """Notify the next responsible party after Compliance reviews a document."""
    if accepted:
        approvers = User.objects.filter(
            is_active=True,
            profile__active=True,
            profile__role=Role.APPROVER,
        )
        notify_users(
            approvers,
            "DOCUMENT_PENDING_FINAL_APPROVAL",
            "Document Requires Final Approval",
            f"{version.document.title} v{version.version} passed Compliance review and is waiting for your final approval.",
            reverse("approve_document", args=[version.pk]),
        )
        notify_user(
            req.requester if req else None,
            "DOCUMENT_COMPLIANCE_ACCEPTED",
            "Document Passed Compliance Review",
            f"{version.document.title} v{version.version} passed Compliance review and is now waiting for final approval.",
            reverse("requests"),
        )
    else:
        notify_user(
            req.requester if req else None,
            "DOCUMENT_REVISION_REQUIRED",
            "Document Revision Required",
            f"{version.document.title} v{version.version} requires revision after Compliance review.",
            reverse("requests"),
        )


def notify_document_decision(req, version, approved, _legacy_url=None):
    retarget_document_approval_notifications(version)
    title = "Document Approved" if approved else "Document Rejected"
    message = (
        f"{version.document.title} v{version.version} was approved by the Approver and returned to Compliance for publication."
        if approved
        else f"{version.document.title} v{version.version} was rejected by the Approver and requires revision."
    )

    notify_user(
        req.requester if req else None,
        "DOCUMENT_APPROVED" if approved else "DOCUMENT_REJECTED",
        title,
        message,
        reverse("requests"),
    )

    compliance_users = User.objects.filter(
        is_active=True,
        profile__active=True,
        profile__role=Role.COMPLIANCE,
    )
    compliance_url = reverse("document_detail", args=[version.document_id]) if approved else reverse("review_queue")
    notify_users(
        compliance_users,
        "DOCUMENT_APPROVED" if approved else "DOCUMENT_REJECTED",
        title,
        message,
        compliance_url,
    )


def notify_document_published(document, version, _legacy_url=None):
    users = User.objects.filter(
        is_active=True,
        profile__active=True,
    ).exclude(profile__role=Role.SYSTEM_ADMIN)
    notify_users(
        users,
        "DOCUMENT_PUBLISHED",
        "Document Published",
        f"{document.title} v{version.version} has been published and is now available for reading.",
        reverse("read_document", args=[document.pk]),
    )
