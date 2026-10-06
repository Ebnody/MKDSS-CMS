from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0004_remove_reviewer_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=40)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("url", models.CharField(blank=True, max_length=500)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["recipient", "is_read"], name="notif_recipient_read_idx"),
                    models.Index(fields=["recipient", "-created_at"], name="notif_recipient_date_idx"),
                ],
            },
        ),
    ]
