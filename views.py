from pathlib import Path

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


READ_ROLES = (Role.USER, Role.COMPLIANCE, Role.REVIEWER, Role.APPROVER)


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
    role = request.user.profile.role
    if role == Role.COMPLIANCE:
        versions = list(published_versions().order_by("document__title"))
        users = list(active_users())
        rows = []
        total_expected = len(versions) * len(users)
        completed_total = 0
        in_progress_total = 0
        for version in versions:
            records = {r.user_id: r for r in ReadingRecord.objects.filter(version=version).select_related("user")}
            completed = sum(r.status == ReadingRecord.Status.COMPLETED for r in records.values())
            in_progress = sum(r.status == ReadingRecord.Status.IN_PROGRESS for r in records.values())
            rows.append({
                "version": version,
                "total": len(users),
                "completed": completed,
                "in_progress": in_progress,
                "not_started": len(users) - completed - in_progress,
                "percent": round(completed * 100 / len(users), 1) if users else 0,
            })
            completed_total += completed
            in_progress_total += in_progress
        return render(request, "compliance/dashboard.html", {
            "versions": rows,
            "users": len(users),
            "published_count": len(versions),
            "completed": completed_total,
            "in_progress": in_progress_total,
            "pending": total_expected - completed_total,
            "expected": total_expected,
            "percent": round(completed_total * 100 / total_expected, 1) if total_expected else 0,
        })
    if role == Role.APPROVER:
        return redirect("approval_queue")
    if role == Role.SYSTEM_ADMIN:
        return redirect("admin_users")
    return redirect("published_documents")


@login_required
def published_documents(request):
    require(request, *READ_ROLES)
    q = request.GET.get("q", "").strip()
    qs = Document.objects.filter(
        published_version__isnull=False,
        archived_at__isnull=True,
    ).select_related("published_version")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(document_number__icontains=q) | Q(category__icontains=q))
    return render(request, "compliance/documents.html", {"documents": qs, "q": q})


@login_required
def read_document(request, pk):
    require(request, *READ_ROLES)
    doc = get_object_or_404(
        Document.objects.select_related("published_version"),
        pk=pk,
        published_version__isnull=False,
        archived_at__isnull=True,
    )
    version = doc.published_version
    record, created = ReadingRecord.objects.get_or_create(
        user=request.user,
        version=version,
        defaults={"status": ReadingRecord.Status.IN_PROGRESS, "started_at": timezone.now()},
    )
    if not created and record.status == ReadingRecord.Status.NOT_STARTED:
        record.status = ReadingRecord.Status.IN_PROGRESS
        record.started_at = timezone.now()
        record.save(update_fields=["status", "started_at"])
    audit(request, "DOCUMENT_VIEW", version)
    preview = version_preview(version)
    return render(request, "compliance/read.html", {
        "document": doc,
        "version": version,
        "record": record,
        "preview": bool(preview),
    })


@login_required
def finish_reading(request, pk):
    require(request, *READ_ROLES)
    if request.method != "POST":
        raise PermissionDenied
    version = get_object_or_404(
        DocumentVersion,
        pk=pk,
        status=DocumentVersion.Status.PUBLISHED,
        document__published_version=pk,
    )
    rec = get_object_or_404(ReadingRecord, user=request.user, version=version)
    if rec.status != ReadingRecord.Status.COMPLETED:
        rec.status = ReadingRecord.Status.COMPLETED
        rec.completed_at = timezone.now()
        rec.save(update_fields=["status", "completed_at"])
        audit(request, "FINISHED_READING", version)
    messages.success(request, "Reading completion recorded.")
    return redirect("read_document", version.document_id)


@login_required
def stream_document(request, pk):
    require(request, *READ_ROLES)
    version = get_object_or_404(
        DocumentVersion,
        pk=pk,
        status=DocumentVersion.Status.PUBLISHED,
        document__published_version=pk,
    )
    preview = version_preview(version)
    if not preview:
        raise Http404
    ext = Path(version.original_name).suffix.lower()
    content_type = "application/pdf" if ext not in {".png", ".jpg", ".jpeg"} else {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[ext]
    response = FileResponse(preview.open("rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, noarchive"
    return response


@login_required
def stream_controlled_version(request, pk):
    require(request, Role.COMPLIANCE)
    version = get_object_or_404(DocumentVersion.objects.select_related("document"), pk=pk)
    if version.status not in {
        DocumentVersion.Status.UNDER_REVIEW,
        DocumentVersion.Status.REVIEW_ACCEPTED,
        DocumentVersion.Status.PENDING_APPROVAL,
        DocumentVersion.Status.REVISION_REQUIRED,
        DocumentVersion.Status.PUBLISHED,
        DocumentVersion.Status.ARCHIVED,
    }:
        raise PermissionDenied
    preview = version_preview(version)
    if not preview:
        raise Http404
    ext = Path(version.original_name).suffix.lower()
    content_type = "application/pdf" if ext not in {".png", ".jpg", ".jpeg"} else {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[ext]
    response = FileResponse(preview.open("rb"), content_type=content_type)
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, noarchive"
    audit(request, "CONTROLLED_VERSION_VIEW", version)
    return response


@login_required
def compliance_documents(request):
    require(request, Role.COMPLIANCE)
    qs = Document.objects.all().select_related("current_version", "published_version")
    return render(request, "compliance/compliance_documents.html", {"documents": qs})


@login_required
def document_create(request):
    # Direct document creation is intentionally disabled. Compliance must use the same request workflow as every other requester.
    require(request, Role.COMPLIANCE)
    return redirect("new_request")


@login_required
def upload_existing_document(request):
    """Register a document that existed before this system, without a request stage."""
    require(request, Role.COMPLIANCE)

    if request.method == "POST":
        form = ExistingDocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    doc = Document.objects.create(
                        title=form.cleaned_data["title"].strip(),
                        document_number=form.cleaned_data["document_number"].strip(),
                        category=form.cleaned_data["category"].strip(),
                        source=Document.Source.EXISTING,
                        state=Document.State.DRAFT,
                        created_by=request.user,
                    )
                    version = create_version(
                        doc,
                        form.cleaned_data["original_file"],
                        form.cleaned_data["version"].strip(),
                        request.user,
                        DocumentVersion.Status.UNDER_REVIEW,
                    )
                    doc.state = Document.State.UNDER_REVIEW
                    doc.save(update_fields=["state"])
                    audit(
                        request,
                        "EXISTING_DOCUMENT_UPLOAD",
                        version,
                        {"document": doc.pk, "version": version.version, "source": Document.Source.EXISTING},
                    )
                messages.success(request, "Existing document uploaded and sent to Compliance review.")
                return redirect("review_queue")
            except ValueError as exc:
                form.add_error("original_file", str(exc))
    else:
        form = ExistingDocumentUploadForm()

    return render(request, "compliance/existing_document_form.html", {"form": form})


@login_required
def document_detail(request, pk):
    require(request, Role.COMPLIANCE)
    doc = get_object_or_404(Document.objects.select_related("current_version", "published_version"), pk=pk)
    versions = doc.versions.select_related("uploaded_by", "published_by").prefetch_related("reviews__reviewer", "approvals__approver")
    return render(request, "compliance/document_detail.html", {"document": doc, "versions": versions})


@login_required
def review_queue(request):
    require(request, Role.COMPLIANCE)
    docs = Document.objects.filter(state=Document.State.UNDER_REVIEW).select_related("current_version", "created_by")
    return render(request, "compliance/review_queue.html", {"documents": docs})


@login_required
def review_document(request, pk):
    require(request, Role.COMPLIANCE)
    doc = get_object_or_404(Document.objects.select_related("current_version"), pk=pk, state=Document.State.UNDER_REVIEW)
    version = doc.current_version
    if not version:
        raise Http404
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                review = form.save(commit=False)
                review.version = version
                review.reviewer = request.user
                review.save()
                if review.decision == DocumentReview.Decision.ACCEPTED:
                    version.status = DocumentVersion.Status.PENDING_APPROVAL
                    version.save(update_fields=["status"])
                    transition_document(doc, Document.State.REVIEW_ACCEPTED)
                    transition_document(doc, Document.State.PENDING_APPROVAL)
                    req = ComplianceRequest.objects.filter(related_version=version).first()
                    if req and req.status == ComplianceRequest.Status.UNDER_REVIEW:
                        transition_request(req, ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL, request.user, "Compliance review accepted; sent to Approver.")
                else:
                    version.status = DocumentVersion.Status.REVISION_REQUIRED
                    version.save(update_fields=["status"])
                    transition_document(doc, Document.State.REVISION_REQUIRED)
                    req = ComplianceRequest.objects.filter(related_version=version).first()
                    if req and req.status == ComplianceRequest.Status.UNDER_REVIEW:
                        transition_request(req, ComplianceRequest.Status.IN_PROGRESS, request.user, "Compliance requested document revision.")
                audit(request, "DOCUMENT_REVIEW", review, {"decision": review.decision, "version": version.version})
            messages.success(request, "Compliance review decision recorded.")
            return redirect("review_queue")
    else:
        form = ReviewForm()
    preview = version_preview(version)
    return render(request, "compliance/review_form.html", {"document": doc, "version": version, "form": form, "preview": bool(preview)})


@login_required
def approval_queue(request):
    require(request, Role.APPROVER)
    requests = ComplianceRequest.objects.filter(status=ComplianceRequest.Status.PENDING_APPROVAL).select_related("requester", "department", "existing_document")
    versions = DocumentVersion.objects.filter(status=DocumentVersion.Status.PENDING_APPROVAL).select_related("document", "uploaded_by")
    return render(request, "compliance/approval_queue.html", {"requests": requests, "versions": versions})


@login_required
def approve_request(request, pk):
    require(request, Role.APPROVER)
    req = get_object_or_404(ComplianceRequest.objects.select_related("requester", "department", "existing_document", "existing_document__published_version"), pk=pk)
    if req.status != ComplianceRequest.Status.PENDING_APPROVAL:
        raise PermissionDenied
    if request.method == "POST":
        form = ApprovalForm(request.POST)
        decision = request.POST.get("decision")
        if form.is_valid() and decision in {"approve", "reject"}:
            with transaction.atomic():
                req.approver = request.user
                req.approval_decision_at = timezone.now()
                req.approval_comments = form.cleaned_data["approval_comments"]
                req.save(update_fields=["approver", "approval_decision_at", "approval_comments"])
                target = ComplianceRequest.Status.APPROVED if decision == "approve" else ComplianceRequest.Status.REJECTED
                transition_request(req, target, request.user, req.approval_comments)
                audit(request, "REQUEST_APPROVAL" if decision == "approve" else "REQUEST_REJECTION", req, {"comments": req.approval_comments})
            messages.success(request, "Request approved." if decision == "approve" else "Request rejected.")
            return redirect("approval_queue")
    else:
        form = ApprovalForm()
    return render(request, "compliance/approval_form.html", {"request_obj": req, "form": form, "document_approval": False})


@login_required
def approve_document(request, pk):
    require(request, Role.APPROVER)
    version = get_object_or_404(
        DocumentVersion.objects.select_related("document", "document__published_version", "uploaded_by"),
        pk=pk,
        status=DocumentVersion.Status.PENDING_APPROVAL,
    )
    if request.method == "POST":
        form = ApprovalForm(request.POST)
        decision = request.POST.get("decision")
        if form.is_valid() and decision in {"approve", "reject"}:
            with transaction.atomic():
                approval = DocumentApproval.objects.create(
                    version=version,
                    approver=request.user,
                    decision=DocumentApproval.Decision.APPROVED if decision == "approve" else DocumentApproval.Decision.REJECTED,
                    remarks=form.cleaned_data["approval_comments"],
                )
                req = ComplianceRequest.objects.filter(related_version=version).first()
                if decision == "approve":
                    version.status = DocumentVersion.Status.REVIEW_ACCEPTED
                    version.save(update_fields=["status"])
                    if req and req.status == ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL:
                        transition_request(req, ComplianceRequest.Status.DOCUMENT_APPROVED, request.user, "Approver approved the controlled document.")
                else:
                    version.status = DocumentVersion.Status.REVISION_REQUIRED
                    version.save(update_fields=["status"])
                    version.document.state = Document.State.REVISION_REQUIRED
                    version.document.save(update_fields=["state"])
                    if req and req.status == ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL:
                        transition_request(req, ComplianceRequest.Status.IN_PROGRESS, request.user, "Approver rejected the controlled document; revision required.")
                audit(request, "DOCUMENT_APPROVAL" if decision == "approve" else "DOCUMENT_REJECTION", approval, {"version": version.version, "document": version.document_id})
            messages.success(request, "Document approved and returned to Compliance." if decision == "approve" else "Document rejected and returned for revision.")
            return redirect("approval_queue")
    else:
        form = ApprovalForm()
    return render(request, "compliance/approval_form.html", {"request_obj": None, "version": version, "form": form, "document_approval": True})


@login_required
def requests_list(request):
    role = request.user.profile.role
    if role == Role.USER:
        qs = ComplianceRequest.objects.filter(requester=request.user)
    elif role in {Role.APPROVER, Role.COMPLIANCE}:
        qs = ComplianceRequest.objects.all()
    else:
        raise PermissionDenied
    qs = qs.select_related("requester", "department", "related_document", "related_version")
    return render(request, "compliance/requests.html", {"requests": qs, "role": role})


def next_request_number():
    return f"REQ-{timezone.now():%Y%m%d%H%M%S%f}"


@login_required
def new_request(request):
    require(request, Role.USER, Role.COMPLIANCE)
    if request.method == "POST":
        form = NewDocumentRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.request_type = ComplianceRequest.RequestType.NEW
            req.requester = request.user
            req.request_number = next_request_number()
            req.save()
            ComplianceRequestHistory.objects.create(request=req, to_status=req.status, actor=request.user, comments="Submitted by requester.")
            audit(request, "REQUEST_SUBMISSION", req)
            messages.success(request, "New document request submitted to Approver and Compliance.")
            return redirect("requests")
    else:
        form = NewDocumentRequestForm(initial={"department": request.user.profile.department})
    return render(request, "compliance/request_form.html", {"form": form, "title": "New Document Request"})


@login_required
def change_request(request):
    require(request, Role.USER, Role.COMPLIANCE)
    if request.method == "POST":
        form = ChangeRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.request_type = ComplianceRequest.RequestType.CHANGE
            req.requester = request.user
            req.request_number = next_request_number()
            req.save()
            ComplianceRequestHistory.objects.create(request=req, to_status=req.status, actor=request.user, comments="Submitted by requester.")
            audit(request, "REQUEST_SUBMISSION", req)
            messages.success(request, "Change request submitted to Approver and Compliance.")
            return redirect("requests")
    else:
        form = ChangeRequestForm(initial={"department": request.user.profile.department})
    return render(request, "compliance/request_form.html", {"form": form, "title": "Document Change Request"})


@login_required
def compliance_queue(request):
    require(request, Role.COMPLIANCE)
    qs = ComplianceRequest.objects.all().select_related("requester", "department", "related_document", "related_version")
    return render(request, "compliance/compliance_queue.html", {"requests": qs})


@login_required
def process_request(request, pk):
    req = get_object_or_404(
        ComplianceRequest.objects.select_related(
            "requester",
            "existing_document",
            "existing_document__published_version",
            "related_document",
            "related_version",
        ),
        pk=pk,
    )

    role = request.user.profile.role
    if role not in {Role.USER, Role.COMPLIANCE}:
        raise PermissionDenied

    # Only the requester uploads the controlled file. Compliance observes
    # other users' requests; if Compliance created the request, Compliance
    # is the requester and may upload.
    if req.requester_id != request.user.id:
        raise PermissionDenied

    if req.status not in {
        ComplianceRequest.Status.APPROVED,
        ComplianceRequest.Status.IN_PROGRESS,
    }:
        return render(
            request,
            "compliance/process_request.html",
            {
                "request_obj": req,
                "can_upload": False,
                "is_change": req.request_type == ComplianceRequest.RequestType.CHANGE,
            },
        )

    # For a NEW request, document metadata is needed only for the first
    # upload. If Compliance requested a revision, the existing related
    # document is reused and the requester only needs to upload the new
    # version/file.
    needs_metadata = (
        req.request_type == ComplianceRequest.RequestType.NEW
        and not req.related_document_id
    )

    if request.method == "POST":
        upload = VersionUploadForm(request.POST, request.FILES)
        meta = DocumentMetaForm(request.POST) if needs_metadata else None

        if upload.is_valid() and (meta is None or meta.is_valid()):
            try:
                with transaction.atomic():
                    if req.request_type == ComplianceRequest.RequestType.NEW:
                        if req.related_document_id:
                            doc = req.related_document
                        else:
                            if meta is None:
                                raise ValueError(
                                    "Document information is required for the first upload."
                                )
                            doc = meta.save(commit=False)
                            doc.created_by = req.requester
                            doc.state = Document.State.DRAFT
                            doc.save()
                    else:
                        doc = req.existing_document
                        if not doc or doc.archived_at:
                            raise ValueError(
                                "The requested document is no longer eligible for change."
                            )

                    version = create_version(
                        doc,
                        upload.cleaned_data["original_file"],
                        upload.cleaned_data["version"],
                        request.user,
                        DocumentVersion.Status.UNDER_REVIEW,
                    )

                    doc.state = Document.State.UNDER_REVIEW
                    doc.archived_at = None
                    doc.save(update_fields=["state", "archived_at"])

                    req.related_document = doc
                    req.related_version = version
                    if role == Role.COMPLIANCE:
                        req.compliance_processor = request.user
                    req.processing_at = timezone.now()
                    req.save(
                        update_fields=[
                            "related_document",
                            "related_version",
                            "compliance_processor",
                            "processing_at",
                        ]
                    )

                    if req.status == ComplianceRequest.Status.APPROVED:
                        transition_request(
                            req,
                            ComplianceRequest.Status.IN_PROGRESS,
                            request.user,
                            "Document preparation started.",
                        )

                    transition_request(
                        req,
                        ComplianceRequest.Status.UNDER_REVIEW,
                        request.user,
                        "Document uploaded and sent to Compliance for review.",
                    )

                    audit(
                        request,
                        "DOCUMENT_UPLOAD_FOR_REQUEST",
                        req,
                        {
                            "document": doc.pk,
                            "version": version.version,
                        },
                    )

                messages.success(
                    request,
                    "Document uploaded and sent to Compliance for review.",
                )
                return redirect(
                    "requests" if role == Role.USER else "compliance_queue"
                )

            except ValueError as exc:
                upload.add_error("original_file", str(exc))

    else:
        upload = VersionUploadForm(initial={"version": "1.0"})
        meta = (
            DocumentMetaForm(initial={"title": req.requested_title})
            if needs_metadata
            else None
        )

    return render(
        request,
        "compliance/process_request.html",
        {
            "request_obj": req,
            "upload": upload,
            "meta": meta,
            "is_change": req.request_type == ComplianceRequest.RequestType.CHANGE,
            "can_upload": True,
        },
    )


@login_required
def publish_document(request, pk):
    require(request, Role.COMPLIANCE)
    if request.method != "POST":
        raise PermissionDenied
    with transaction.atomic():
        doc = get_object_or_404(Document.objects.select_for_update(), pk=pk)
        v = doc.current_version
        if doc.state != Document.State.PENDING_APPROVAL or not v or v.status != DocumentVersion.Status.REVIEW_ACCEPTED:
            raise PermissionDenied
        approval = v.approvals.filter(decision=DocumentApproval.Decision.APPROVED).first()
        if not approval:
            raise PermissionDenied

        old = doc.published_version
        v.status = DocumentVersion.Status.PUBLISHED
        v.publication_at = timezone.now()
        v.published_by = request.user
        v.save(update_fields=["status", "publication_at", "published_by"])
        doc.published_version = v
        doc.state = Document.State.PUBLISHED
        doc.archived_at = None
        doc.save(update_fields=["published_version", "state", "archived_at"])

        if old and old.pk != v.pk:
            delete_version(old)

        req = ComplianceRequest.objects.filter(related_version=v).first()
        if req and req.status == ComplianceRequest.Status.DOCUMENT_APPROVED:
            transition_request(req, ComplianceRequest.Status.COMPLETED, request.user, "Document published by Compliance.")
        audit(request, "DOCUMENT_PUBLICATION", v, {"document": doc.pk, "version": v.version, "replaced_version": old.version if old else None})
    messages.success(request, "Document published. The previous published version has been removed automatically.")
    return redirect("document_detail", pk)


@login_required
def edit_document(request, pk):
    require(request, Role.COMPLIANCE)
    doc = get_object_or_404(Document, pk=pk)
    if request.method == "POST":
        form = DocumentMetaForm(request.POST, instance=doc)
        if form.is_valid():
            saved = form.save()
            audit(request, "PUBLISHED_DOCUMENT_EDIT", saved)
            messages.success(request, "Document information updated.")
            return redirect("document_detail", pk)
    else:
        form = DocumentMetaForm(instance=doc)
    return render(request, "compliance/document_edit.html", {"document": doc, "form": form})


@login_required
def block_document(request, pk):
    require(request, Role.COMPLIANCE)
    if request.method != "POST":
        raise PermissionDenied
    with transaction.atomic():
        doc = get_object_or_404(Document.objects.select_for_update(), pk=pk, state=Document.State.PUBLISHED)
        if doc.published_version:
            doc.published_version.status = DocumentVersion.Status.ARCHIVED
            doc.published_version.save(update_fields=["status"])
        transition_document(doc, Document.State.ARCHIVED)
        audit(request, "DOCUMENT_BLOCK", doc)
    messages.success(request, "Published document blocked from user access.")
    return redirect("compliance_documents")


@login_required
def unblock_document(request, pk):
    require(request, Role.COMPLIANCE)
    if request.method != "POST":
        raise PermissionDenied
    with transaction.atomic():
        doc = get_object_or_404(Document.objects.select_for_update(), pk=pk, state=Document.State.ARCHIVED)
        if not doc.published_version:
            raise PermissionDenied
        doc.published_version.status = DocumentVersion.Status.PUBLISHED
        doc.published_version.save(update_fields=["status"])
        transition_document(doc, Document.State.PUBLISHED)
        audit(request, "DOCUMENT_UNBLOCK", doc)
    messages.success(request, "Document is published again.")
    return redirect("compliance_documents")


@login_required
def delete_document(request, pk):
    require(request, Role.COMPLIANCE)
    if request.method != "POST":
        raise PermissionDenied
    with transaction.atomic():
        doc = get_object_or_404(Document.objects.select_for_update(), pk=pk)
        # Preserve request/audit history while removing the controlled document and all file versions.
        ComplianceRequest.objects.filter(existing_document=doc).update(existing_document=None)
        ComplianceRequest.objects.filter(related_document=doc).update(related_document=None, related_version=None)
        versions = list(doc.versions.all())
        title = doc.title
        for version in versions:
            delete_version(version)
        audit(request, "DOCUMENT_DELETE", details={"document": doc.pk, "title": title})
        doc.delete()
    messages.success(request, "Document and all of its stored versions have been deleted.")
    return redirect("compliance_documents")


@login_required
def admin_users(request):
    require(request, Role.SYSTEM_ADMIN)
    return render(request, "compliance/admin_users.html", {"users": User.objects.select_related("profile", "profile__department").order_by("username")})


@login_required
def admin_user_edit(request, pk=None):
    require(request, Role.SYSTEM_ADMIN)
    user = get_object_or_404(User, pk=pk) if pk else None
    if request.method == "POST":
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            saved = form.save()
            audit(request, "USER_MODIFICATION" if user else "USER_CREATION", saved)
            messages.success(request, "User saved.")
            return redirect("admin_users")
    else:
        form = UserForm(instance=user)
    return render(request, "compliance/admin_user_form.html", {"form": form, "editing": bool(user)})


@login_required
def admin_user_delete(request, pk):
    require(request, Role.SYSTEM_ADMIN)
    if request.method != "POST":
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "The current System Admin account cannot be deleted from its own session.")
        return redirect("admin_users")
    username = user.username
    try:
        with transaction.atomic():
            user.delete()
            audit(request, "USER_DELETION", details={"username": username})
    except Exception:
        messages.error(request, "This account has protected historical records. Use Block/Deactivate instead of deleting it.")
        return redirect("admin_users")
    messages.success(request, f"User account '{username}' was deleted.")
    return redirect("admin_users")


@login_required
def admin_user_toggle(request, pk):
    require(request, Role.SYSTEM_ADMIN)
    if request.method != "POST":
        raise PermissionDenied
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk and user.is_active:
        messages.error(request, "The current System Admin account cannot be blocked from its own session.")
        return redirect("admin_users")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    user.profile.active = user.is_active
    user.profile.save(update_fields=["active"])
    audit(request, "USER_BLOCK" if not user.is_active else "USER_UNBLOCK", user)
    messages.success(request, f"User '{user.username}' is {'active' if user.is_active else 'blocked'}.")
    return redirect("admin_users")


@login_required
def admin_departments(request):
    require(request, Role.SYSTEM_ADMIN)
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            d = form.save(); audit(request, "DEPARTMENT_MODIFICATION", d); return redirect("admin_departments")
    else:
        form = DepartmentForm()
    return render(request, "compliance/admin_departments.html", {"departments": Department.objects.all(), "form": form})


@login_required
def audit_logs(request):
    require(request, Role.SYSTEM_ADMIN, Role.COMPLIANCE)
    logs = AuditLog.objects.select_related("user")[:1000]
    return render(request, "compliance/audit_logs.html", {"logs": logs})


@login_required
def reports(request):
    require(request, Role.COMPLIANCE)
    form = ReportFilterForm(request.GET or None)
    return render(request, "compliance/reports.html", {"form": form})


def filtered_readings(form):
    if not form.is_valid():
        return []
    data = form.cleaned_data
    versions = list(published_versions().order_by("document__title", "version"))
    users = list(active_users())
    if data.get("document"):
        versions = [v for v in versions if v.document_id == data["document"].pk]
    if data.get("version"):
        versions = [v for v in versions if v.pk == data["version"].pk]
    if data.get("user"):
        users = [u for u in users if u.pk == data["user"].pk]
    if data.get("department"):
        users = [u for u in users if u.profile.department_id == data["department"].pk]
    record_map = {(r.user_id, r.version_id): r for r in ReadingRecord.objects.filter(version__in=versions, user__in=users).select_related("user", "user__profile__department", "version", "version__document")}
    rows = []
    for version in versions:
        for user in users:
            record = record_map.get((user.pk, version.pk))
            if data.get("start_date") or data.get("end_date"):
                if not record or not record.started_at:
                    continue
                if data.get("start_date") and record.started_at.date() < data["start_date"]:
                    continue
                if data.get("end_date") and record.started_at.date() > data["end_date"]:
                    continue
            rows.append({"user": user, "version": version, "record": record})
    return rows


@login_required
def report_csv(request):
    require(request, Role.COMPLIANCE)
    form = ReportFilterForm(request.GET or None)
    qs = filtered_readings(form)
    audit(request, "REPORT_GENERATION", details={"format": "CSV"})
    return reading_csv(qs)


@login_required
def report_pdf(request):
    require(request, Role.COMPLIANCE)
    form = ReportFilterForm(request.GET or None)
    qs = filtered_readings(form)
    data = form.cleaned_data if form.is_valid() else {}
    start, end = data.get("start_date"), data.get("end_date")
    label = f"{start or 'All'} to {end or 'All'}"
    audit(request, "REPORT_GENERATION", details={"format": "PDF"})
    return reading_pdf(qs, request.user, date_range=label)


@login_required
def reading_drilldown(request, pk):
    require(request, Role.COMPLIANCE)
    version = get_object_or_404(DocumentVersion.objects.select_related("document"), pk=pk, status=DocumentVersion.Status.PUBLISHED)
    users = list(active_users())
    records = {r.user_id: r for r in ReadingRecord.objects.filter(version=version)}
    rows = [{"user": u, "record": records.get(u.pk)} for u in users]
    return render(request, "compliance/reading_drilldown.html", {"version": version, "rows": rows})


@login_required
def admin_health(request):
    require(request, Role.SYSTEM_ADMIN)
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False
    lo_ok = False
    try:
        lo_ok = _find_libreoffice() is not None
    except Exception:
        pass
    return render(request, "compliance/health.html", {"db_ok": db_ok, "storage_ok": Path(settings.MEDIA_ROOT).exists(), "libreoffice_ok": lo_ok})


@login_required
def admin_settings(request):
    require(request, Role.SYSTEM_ADMIN)
    if request.method == "POST":
        form = SystemSettingForm(request.POST)
        if form.is_valid():
            s = form.save(); audit(request, "SYSTEM_SETTING_CHANGE", s); return redirect("admin_settings")
    else:
        form = SystemSettingForm()
    return render(request, "compliance/settings.html", {"settings": SystemSetting.objects.all().order_by("key"), "form": form})


@login_required
def admin_backup(request):
    require(request, Role.SYSTEM_ADMIN)
    if request.method != "POST":
        return render(request, "compliance/backup.html")
    target = Path(settings.MEDIA_ROOT) / "backups" / f"MKDSS_backup_{timezone.now():%Y%m%d_%H%M%S}.zip"
    backup_to_zip(settings.BASE_DIR, target)
    audit(request, "BACKUP", details={"file": target.name})
    messages.success(request, f"Backup created: {target.name}")
    return render(request, "compliance/backup.html", {"backup_name": target.name})


@login_required
def admin_restore(request):
    require(request, Role.SYSTEM_ADMIN)
    if request.method == "POST":
        form = RestoreForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                restore_from_zip(settings.BASE_DIR, form.cleaned_data["backup"])
                messages.success(request, "Restore completed. Restart the application service before normal use.")
                audit(request, "RESTORE", details={"filename": form.cleaned_data["backup"].name})
                return redirect("login")
            except (ValueError, OSError) as exc:
                form.add_error("backup", str(exc))
    else:
        form = RestoreForm()
    return render(request, "compliance/restore.html", {"form": form})
