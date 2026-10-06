from pathlib import Path
import shutil
import re

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists() or not (ROOT / "compliance").is_dir():
    raise SystemExit("Run this script from the MKDSS project root containing manage.py and compliance\\")

PATCH = Path(__file__).resolve().parent
# The patch may be extracted either directly beside this script or as a
# top-level folder (the normal ZIP extraction layout). Support both layouts.
if not (PATCH / "notification_model_snippet.txt").exists():
    nested = PATCH / "MKDSS_UI_Notifications_DarkMode_PATCH"
    if (nested / "notification_model_snippet.txt").exists():
        PATCH = nested
BACKUP = ROOT / "_pre_ui_notifications_backup"
BACKUP.mkdir(exist_ok=True)

def backup(rel):
    src = ROOT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)

def write(rel, text):
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")

def copy_file(rel):
    src = PATCH / rel
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    # If the patch files were extracted directly into the project root,
    # source and destination are the same file. Do not copy a file onto itself.
    if src.resolve() == dst.resolve():
        return
    shutil.copy2(src, dst)

# Preserve current files before changing them.
for rel in [
    "compliance/models.py", "compliance/views.py", "compliance/urls.py", "config/settings.py",
    "templates/compliance/base.html", "templates/registration/login.html",
]:
    backup(rel)

# 1. Add Notification model to the existing models.py. The model is deliberately
# inserted before Department so it has no dependency on later compliance models.
models = ROOT / "compliance/models.py"
text = models.read_text(encoding="utf-8")
if "class Notification(models.Model):" not in text:
    marker = "class Department(models.Model):"
    if marker not in text:
        raise SystemExit("Could not find class Department in compliance/models.py")
    model = r'''
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
'''.rstrip() + "\n\n"
    text = text.replace(marker, model + marker, 1)
    models.write_text(text, encoding="utf-8")

# 2. Add context processor for the bell/dropdown.
copy_file("compliance/context_processors.py")

settings = ROOT / "config/settings.py"
st = settings.read_text(encoding="utf-8")
cp = '"compliance.context_processors.notifications"'
if cp not in st:
    needle = '"django.contrib.messages.context_processors.messages"'
    if needle not in st:
        raise SystemExit("Could not find Django messages context processor in config/settings.py")
    st = st.replace(needle, needle + ', ' + cp, 1)
    settings.write_text(st, encoding="utf-8")

# 3. Copy notification service/views/static assets.
for rel in [
    "compliance/notification_service.py", "compliance/notification_views.py",
    "compliance/migrations/0005_notification.py", "templates/compliance/base.html",
    "templates/compliance/notifications.html", "static/css/mkdss_theme.css",
    "static/js/mkdss_ui.js", "static/img/mkdss-logo.png",
]:
    copy_file(rel)

# 4. Wire notification events into the current workflow views. The replacements
# are guarded and idempotent so running this script twice does not duplicate calls.
views = ROOT / "compliance/views.py"
v = views.read_text(encoding="utf-8")
imp = 'from .notification_service import notify_request_submitted, notify_request_decision, notify_document_decision, notify_document_published\n'
if 'from .notification_service import' not in v:
    needle = 'from .reports import reading_csv, reading_pdf\n'
    if needle not in v:
        raise SystemExit("Could not find reports import in compliance/views.py")
    v = v.replace(needle, needle + imp, 1)

repls = [
    (
        'audit(request, "REQUEST_SUBMISSION", req)\n            messages.success(request, "New document request submitted to Approver and Compliance.")',
        'audit(request, "REQUEST_SUBMISSION", req)\n            notify_request_submitted(req, f"/approvals/{req.pk}/")\n            messages.success(request, "New document request submitted to Approver and Compliance.")'
    ),
    (
        'audit(request, "REQUEST_SUBMISSION", req)\n            messages.success(request, "Change request submitted to Approver and Compliance.")',
        'audit(request, "REQUEST_SUBMISSION", req)\n            notify_request_submitted(req, f"/approvals/{req.pk}/")\n            messages.success(request, "Change request submitted to Approver and Compliance.")'
    ),
    (
        'audit(request, "REQUEST_APPROVAL" if decision == "approve" else "REQUEST_REJECTION", req, {"comments": req.approval_comments})\n            messages.success(request, "Request approved." if decision == "approve" else "Request rejected.")',
        'audit(request, "REQUEST_APPROVAL" if decision == "approve" else "REQUEST_REJECTION", req, {"comments": req.approval_comments})\n                notify_request_decision(req, decision == "approve", f"/approvals/{req.pk}/")\n            messages.success(request, "Request approved." if decision == "approve" else "Request rejected.")'
    ),
    (
        'audit(request, "DOCUMENT_APPROVAL" if decision == "approve" else "DOCUMENT_REJECTION", approval, {"version": version.version, "document": version.document_id})\n            messages.success(request, "Document approved and returned to Compliance." if decision == "approve" else "Document rejected and returned for revision.")',
        'audit(request, "DOCUMENT_APPROVAL" if decision == "approve" else "DOCUMENT_REJECTION", approval, {"version": version.version, "document": version.document_id})\n                notify_document_decision(req, version, decision == "approve", "/approvals/")\n            messages.success(request, "Document approved and returned to Compliance." if decision == "approve" else "Document rejected and returned for revision.")'
    ),
    (
        'audit(request, "DOCUMENT_PUBLICATION", v, {"document": doc.pk, "version": v.version, "replaced_version": old.version if old else None})\n    messages.success(request, "Document published. The previous published version has been removed automatically.")',
        'audit(request, "DOCUMENT_PUBLICATION", v, {"document": doc.pk, "version": v.version, "replaced_version": old.version if old else None})\n        notify_document_published(doc, v, f"/documents/{doc.pk}/read/")\n    messages.success(request, "Document published. The previous published version has been removed automatically.")'
    ),
]
for old, new in repls:
    if old in v and new not in v:
        v = v.replace(old, new, 1)

views.write_text(v, encoding="utf-8")

# 5. Add notification routes and ensure final document approval has a URL.
urls = ROOT / "compliance/urls.py"
u = urls.read_text(encoding="utf-8")
if 'from .notification_views import' not in u:
    u = u.replace('from . import views\n', 'from . import views\nfrom .notification_views import notifications_page, mark_notification_read, mark_all_notifications_read\n', 1)
if 'name="approve_document"' not in u:
    needle = 'path("approvals/<int:pk>/", views.approve_request, name="approve_request"),'
    if needle not in u:
        raise SystemExit("Could not find approve_request route in compliance/urls.py")
    u = u.replace(needle, needle + '\n    path("approvals/document/<int:pk>/", views.approve_document, name="approve_document"),', 1)
if 'name="notifications"' not in u:
    needle = 'path("reports/reading.pdf", views.report_pdf, name="report_pdf"),'
    if needle not in u:
        raise SystemExit("Could not find report_pdf route in compliance/urls.py")
    u = u.replace(needle, needle + '\n    path("notifications/", notifications_page, name="notifications"),\n    path("notifications/<int:pk>/read/", mark_notification_read, name="notification_read"),\n    path("notifications/read-all/", mark_all_notifications_read, name="notifications_read_all"),', 1)
urls.write_text(u, encoding="utf-8")

print("MKDSS UI + notifications + dark mode patch applied.")
print(f"Backup of changed files: {BACKUP}")
print("Next: python manage.py migrate && python manage.py check && python manage.py test")
