from pathlib import Path
import shutil

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists() or not (ROOT / "compliance").is_dir():
    raise SystemExit("Run this script from the MKDSS project root containing manage.py and compliance\\")

PATCH = Path(__file__).resolve().parent
BACKUP = ROOT / "_pre_notification_fix_backup"
BACKUP.mkdir(exist_ok=True)


def backup(rel):
    src = ROOT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)


def copy_file(rel):
    src = PATCH / rel
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.resolve() == dst.resolve():
            return
    except FileNotFoundError:
        pass
    shutil.copy2(src, dst)

# Backup only the files this fix changes.
for rel in [
    "compliance/notification_service.py",
    "compliance/notification_views.py",
    "compliance/migrations/0006_repair_notification_urls.py",
    "static/js/mkdss_ui.js",
    "static/css/notification_fix.css",
    "templates/compliance/base.html",
]:
    backup(rel)

for rel in [
    "compliance/notification_service.py",
    "compliance/notification_views.py",
    "compliance/migrations/0006_repair_notification_urls.py",
    "static/js/mkdss_ui.js",
    "static/css/notification_fix.css",
]:
    copy_file(rel)

base = ROOT / "templates/compliance/base.html"
text = base.read_text(encoding="utf-8")

meta = '<meta name="csrf-token" content="{{ csrf_token }}">'
if meta not in text:
    text = text.replace('<meta name="viewport" content="width=device-width,initial-scale=1">', '<meta name="viewport" content="width=device-width,initial-scale=1">\n' + meta, 1)

old_button = '<button type="button" id="notification-button" class="notification-button" aria-label="Notifications" aria-expanded="false">🔔{% if notification_unread_count %}<span class="notification-badge">{{ notification_unread_count }}</span>{% endif %}</button>'
new_button = '''<button type="button" id="notification-button" class="notification-button" aria-label="Notifications" aria-expanded="false" title="Notifications">
        <svg class="notification-bell-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path><path d="M10 21h4"></path></svg>
        {% if notification_unread_count %}<span class="notification-badge">{{ notification_unread_count }}</span>{% endif %}
      </button>'''
if old_button in text:
    text = text.replace(old_button, new_button, 1)
else:
    # If a prior UI package formatted the button differently, replace the
    # complete notification button element conservatively.
    start = text.find('<button type="button" id="notification-button"')
    if start != -1:
        end = text.find('</button>', start)
        if end != -1:
            text = text[:start] + new_button + text[end + len('</button>'):]

css_link = '<link rel="stylesheet" href="{% static \'css/notification_fix.css\' %}">'
if css_link not in text:
    anchor = '<link rel="stylesheet" href="{% static \'css/mkdss_theme.css\' %}">'
    if anchor in text:
        text = text.replace(anchor, anchor + '\n' + css_link, 1)

base.write_text(text, encoding="utf-8")

print("MKDSS notification fix v2 applied.")
print(f"Backup: {BACKUP}")
print("Next: python manage.py migrate && python manage.py check && python manage.py test")
