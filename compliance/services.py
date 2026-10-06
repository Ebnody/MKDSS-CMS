import hashlib
import mimetypes
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.utils.text import get_valid_filename
from django.utils import timezone

from .models import AuditLog, ComplianceRequest, ComplianceRequestHistory, Document, DocumentVersion

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "png", "jpg", "jpeg"}
DOCUMENT_TRANSITIONS = {
    Document.State.DRAFT: {Document.State.UNDER_REVIEW, Document.State.REVISION_REQUIRED},
    Document.State.UNDER_REVIEW: {Document.State.REVISION_REQUIRED, Document.State.REVIEW_ACCEPTED},
    Document.State.REVISION_REQUIRED: {Document.State.UNDER_REVIEW},
    Document.State.REVIEW_ACCEPTED: {Document.State.PENDING_APPROVAL},
    Document.State.PENDING_APPROVAL: {Document.State.REVISION_REQUIRED, Document.State.PUBLISHED},
    Document.State.PUBLISHED: {Document.State.ARCHIVED},
    Document.State.ARCHIVED: {Document.State.PUBLISHED},
}

REQUEST_TRANSITIONS = {
    ComplianceRequest.Status.PENDING_APPROVAL: {ComplianceRequest.Status.APPROVED, ComplianceRequest.Status.REJECTED, ComplianceRequest.Status.CANCELLED},
    ComplianceRequest.Status.APPROVED: {ComplianceRequest.Status.IN_PROGRESS, ComplianceRequest.Status.CANCELLED},
    ComplianceRequest.Status.IN_PROGRESS: {ComplianceRequest.Status.UNDER_REVIEW, ComplianceRequest.Status.CANCELLED},
    ComplianceRequest.Status.UNDER_REVIEW: {ComplianceRequest.Status.IN_PROGRESS, ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL, ComplianceRequest.Status.CANCELLED},
    ComplianceRequest.Status.DOCUMENT_PENDING_APPROVAL: {ComplianceRequest.Status.IN_PROGRESS, ComplianceRequest.Status.DOCUMENT_APPROVED, ComplianceRequest.Status.CANCELLED},
    ComplianceRequest.Status.DOCUMENT_APPROVED: {ComplianceRequest.Status.COMPLETED},
    ComplianceRequest.Status.REJECTED: set(),
    ComplianceRequest.Status.COMPLETED: set(),
    ComplianceRequest.Status.CANCELLED: set(),
}


def client_ip(request):
    return request.META.get("REMOTE_ADDR")


def audit(request, action, obj=None, details=None):
    AuditLog.objects.create(
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        action=action,
        object_type=obj.__class__.__name__ if obj else "",
        object_id=str(obj.pk) if obj else "",
        ip_address=client_ip(request),
        details=details or {},
    )


def role_required(request, *roles):
    if not request.user.is_authenticated or not request.user.is_active:
        return False
    try:
        return request.user.profile.active and request.user.profile.role in roles
    except Exception:
        return False


def safe_extension(name):
    return Path(name or "").suffix.lower().lstrip(".")


def detect_mime(name):
    return mimetypes.guess_type(name or "")[0] or "application/octet-stream"


def validate_document_file(uploaded):
    name = get_valid_filename(Path(uploaded.name).name)
    ext = safe_extension(name)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported document type.")
    if uploaded.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB upload limit.")
    if ext == "pdf":
        head = uploaded.read(5); uploaded.seek(0)
        if head != b"%PDF-":
            raise ValueError("The uploaded file is not a valid PDF.")
    elif ext in {"png", "jpg", "jpeg"}:
        try:
            from PIL import Image
            with Image.open(uploaded) as image:
                image.verify()
        except Exception as exc:
            uploaded.seek(0)
            raise ValueError("The uploaded image is invalid or corrupted.") from exc
        uploaded.seek(0)
    elif ext in {"docx", "xlsx", "pptx"}:
        try:
            with zipfile.ZipFile(uploaded) as archive:
                if archive.testzip() is not None:
                    raise ValueError("The Office file archive is corrupted.")
        except zipfile.BadZipFile as exc:
            uploaded.seek(0)
            raise ValueError("The Office file is not a valid package.") from exc
        uploaded.seek(0)
    return name, detect_mime(name)


def transition_document(document, new_state):
    if new_state not in DOCUMENT_TRANSITIONS.get(document.state, set()):
        raise ValueError(f"Invalid document transition: {document.state} -> {new_state}")
    document.state = new_state
    if new_state == Document.State.ARCHIVED:
        document.archived_at = timezone.now()
        document.save(update_fields=["state", "archived_at"])
    elif new_state == Document.State.PUBLISHED:
        document.archived_at = None
        document.save(update_fields=["state", "archived_at"])
    else:
        document.save(update_fields=["state"])


def transition_request(request_obj, new_status, actor=None, comments=""):
    if new_status not in REQUEST_TRANSITIONS.get(request_obj.status, set()):
        raise ValueError(f"Invalid request transition: {request_obj.status} -> {new_status}")
    old = request_obj.status
    request_obj.status = new_status
    fields = ["status"]
    if new_status == ComplianceRequest.Status.COMPLETED:
        request_obj.completed_at = timezone.now()
        fields.append("completed_at")
    request_obj.save(update_fields=fields)
    ComplianceRequestHistory.objects.create(request=request_obj, from_status=old, to_status=new_status, actor=actor, comments=comments)


def delete_version_files(version):
    for field in (version.preview_file, version.original_file):
        try:
            if field and field.name:
                field.storage.delete(field.name)
        except Exception:
            pass


def delete_version(version):
    delete_version_files(version)
    version.delete()


def create_version(
    document,
    uploaded_file,
    version,
    user,
    status=DocumentVersion.Status.DRAFT,
):
    """
    Create a new document version.

    Only one unpublished working version is retained. If the document
    already has a working version and that version is not the currently
    published version, remove it before storing the replacement.

    The currently published version is deliberately preserved until the
    replacement version has passed Compliance review, Approver approval,
    and publication.
    """
    name, mime = validate_document_file(uploaded_file)

    if DocumentVersion.objects.filter(
        document=document,
        version=version,
    ).exists():
        raise ValueError(
            "That version number already exists for this document."
        )

    old_current = document.current_version
    published_id = document.published_version_id

    if old_current is not None and old_current.pk != published_id:
        delete_version(old_current)

    new_version = DocumentVersion.objects.create(
        document=document,
        version=version,
        original_name=name,
        original_file=uploaded_file,
        mime_type=mime,
        uploaded_by=user,
        status=status,
    )

    document.current_version = new_version
    document.save(update_fields=["current_version"])

    return new_version


def _find_libreoffice():
    """Resolve LibreOffice on Windows/Linux without requiring a hard-coded deployment path."""
    configured = str(getattr(settings, "LIBREOFFICE_PATH", "") or "").strip()
    candidates = []
    if configured:
        candidates.append(configured)
    candidates.extend([
        "soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ])
    for candidate in candidates:
        if candidate == "soffice":
            path = shutil.which(candidate)
            if path:
                return path
        elif Path(candidate).exists():
            return candidate
    return None


def convert_office_to_pdf(version):
    ext = safe_extension(version.original_name)
    if ext not in {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}: return None
    soffice = _find_libreoffice()
    if not soffice: return None
    source = Path(version.original_file.path)
    outdir = Path(settings.MEDIA_ROOT) / "documents" / "previews" / "office"
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(outdir)) as tmp:
        temp = Path(tmp); safe_name = get_valid_filename(source.name); copied = temp / safe_name
        shutil.copy2(source, copied); (temp / "home").mkdir()
        cmd = [soffice, "--headless", "--norestore", "--nodefault", "--nolockcheck", "--convert-to", "pdf", "--outdir", str(temp), str(copied)]
        env = os.environ.copy(); env["HOME"] = str(temp / "home")
        try: p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90, check=False, env=env, shell=False)
        except (OSError, subprocess.TimeoutExpired): return None
        pdf = temp / (copied.stem + ".pdf")
        if p.returncode != 0 or not pdf.exists(): return None
        with pdf.open("rb") as fh: version.preview_file.save(f"{version.document_id}_{version.pk}.pdf", File(fh), save=True)
        return version.preview_file


def version_preview(version):
    if version.preview_file:
        return version.preview_file
    ext = safe_extension(version.original_name)
    if ext == "pdf":
        return version.original_file
    # Images are already browser-displayable and do not need conversion.
    if ext in {"png", "jpg", "jpeg"}:
        return version.original_file
    return convert_office_to_pdf(version)


def file_sha256(file_field):
    digest = hashlib.sha256()
    with file_field.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def backup_to_zip(base_dir, destination):
    base = Path(base_dir); db = base / "db.sqlite3"; data = base / "data"
    if not db.exists(): raise FileNotFoundError("Database file does not exist.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(db, "db.sqlite3")
        if data.exists():
            for path in data.rglob("*"):
                if path.is_file() and "backups" not in path.relative_to(data).parts:
                    archive.write(path, path.relative_to(base).as_posix())
    return destination


def restore_from_zip(base_dir, uploaded_file):
    base = Path(base_dir)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp); archive_path = tmp_path / "restore.zip"
        with archive_path.open("wb") as fh:
            for chunk in uploaded_file.chunks(): fh.write(chunk)
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            if "db.sqlite3" not in names: raise ValueError("Backup does not contain db.sqlite3.")
            # ZIP members use POSIX separators. Reject absolute paths and any
            # member that escapes the temporary extraction directory.
            for name in names:
                normalized = name.replace("\\", "/")
                parts = [part for part in normalized.split("/") if part not in ("", ".")]
                if normalized.startswith("/") or (parts and ":" in parts[0]) or ".." in parts:
                    raise ValueError("Unsafe backup paths detected.")
            archive.extractall(tmp_path)
        backup_dir = base / "data" / "backups"; backup_dir.mkdir(parents=True, exist_ok=True)
        backup_to_zip(base, backup_dir / f"pre_restore_{timezone.now():%Y%m%d_%H%M%S}.zip")
        from django.db import connections
        connections.close_all()
        shutil.copy2(tmp_path / "db.sqlite3", base / "db.sqlite3")
        extracted_data = tmp_path / "data"
        if extracted_data.exists():
            target = base / "data"
            for child in list(target.iterdir()):
                if child.name != "backups": shutil.rmtree(child) if child.is_dir() else child.unlink()
            for child in extracted_data.iterdir():
                dest = target / child.name
                if child.is_dir(): shutil.copytree(child, dest, dirs_exist_ok=True)
                else: shutil.copy2(child, dest)
