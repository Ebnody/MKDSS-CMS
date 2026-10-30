from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0009_document_source"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentAcknowledgment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(db_index=True, max_length=80)),
                ("employee_name", models.CharField(max_length=180)),
                ("document_title", models.CharField(max_length=255)),
                ("document_version_label", models.CharField(max_length=30)),
                ("confirmation_text_version", models.CharField(default="1", max_length=20)),
                ("identity_verified", models.BooleanField(default=False)),
                ("acknowledged_at", models.DateTimeField(auto_now_add=True)),
                ("audit_reference", models.CharField(blank=True, max_length=100)),
                ("department", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="document_acknowledgments", to="compliance.department")),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acknowledgments", to="compliance.document")),
                ("submitted_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submitted_document_acknowledgments", to=settings.AUTH_USER_MODEL)),
                ("version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="acknowledgments", to="compliance.documentversion")),
            ],
            options={"ordering": ["-acknowledged_at"]},
        ),
        migrations.AddConstraint(
            model_name="documentacknowledgment",
            constraint=models.UniqueConstraint(fields=("employee_id", "version"), name="uniq_employee_document_ack_version"),
        ),
        migrations.AddIndex(
            model_name="documentacknowledgment",
            index=models.Index(fields=["department", "acknowledged_at"], name="ack_dept_date_idx"),
        ),
        migrations.AddIndex(
            model_name="documentacknowledgment",
            index=models.Index(fields=["employee_id", "acknowledged_at"], name="ack_employee_date_idx"),
        ),
    ]
