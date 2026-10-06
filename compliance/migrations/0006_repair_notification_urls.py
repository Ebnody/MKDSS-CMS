from django.db import migrations
from django.urls import reverse


def repair_notification_urls(apps, schema_editor):
    Notification = apps.get_model("compliance", "Notification")
    UserProfile = apps.get_model("compliance", "UserProfile")

    profiles = {
        p.user_id: p.role
        for p in UserProfile.objects.all().only("user_id", "role")
    }

    for item in Notification.objects.all().iterator():
        kind = item.kind or ""
        url = item.url or ""
        role = profiles.get(item.recipient_id)
        new_url = url

        if kind == "REQUEST_PENDING_APPROVAL":
            # Previous implementation used /approvals/<id>/, but the actual
            # route is /approvals/requests/<id>/.
            parts = url.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "approvals" and parts[1].isdigit():
                new_url = reverse("approve_request", args=[int(parts[1])])

        elif kind == "REQUEST_SUBMITTED":
            new_url = reverse("compliance_queue")

        elif kind in {"REQUEST_APPROVED", "REQUEST_REJECTED"}:
            new_url = reverse("requests")

        elif kind in {"DOCUMENT_APPROVED", "DOCUMENT_REJECTED"}:
            if role == "COMPLIANCE":
                new_url = reverse("compliance_documents") if kind == "DOCUMENT_APPROVED" else reverse("review_queue")
            else:
                new_url = reverse("requests")

        if new_url != url:
            item.url = new_url
            item.save(update_fields=["url"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("compliance", "0005_notification")]
    operations = [migrations.RunPython(repair_notification_urls, noop_reverse)]
