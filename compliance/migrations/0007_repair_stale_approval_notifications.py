from django.db import migrations
from django.urls import reverse


def repair_stale_approval_notifications(apps, schema_editor):
    Notification = apps.get_model("compliance", "Notification")
    ComplianceRequest = apps.get_model("compliance", "ComplianceRequest")
    pending_url = reverse("approval_queue")

    for item in Notification.objects.filter(kind="REQUEST_PENDING_APPROVAL").iterator():
        url = item.url or ""
        parts = url.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "approvals" and parts[1] == "requests" and parts[2].isdigit():
            req = ComplianceRequest.objects.filter(pk=int(parts[2])).only("status").first()
            if req and req.status != "PENDING_APPROVAL":
                item.url = pending_url
                item.is_read = True
                item.save(update_fields=["url", "is_read"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("compliance", "0006_repair_notification_urls")]
    operations = [migrations.RunPython(repair_stale_approval_notifications, noop_reverse)]
