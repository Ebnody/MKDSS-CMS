from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("compliance", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="document",
            name="published_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_for", to="compliance.documentversion"),
        ),
        migrations.AddField(
            model_name="documentversion",
            name="status",
            field=models.CharField(choices=[("DRAFT", "Draft"), ("UNDER_REVIEW", "Under Review"), ("REVISION_REQUIRED", "Revision Required"), ("REVIEW_ACCEPTED", "Review Accepted"), ("PUBLISHED", "Published"), ("ARCHIVED", "Archived")], default="DRAFT", max_length=30),
        ),
        migrations.AddField(
            model_name="compliancerequest",
            name="related_document",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="compliance_requests", to="compliance.document"),
        ),
        migrations.CreateModel(
            name="ComplianceRequestHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, max_length=30)),
                ("to_status", models.CharField(max_length=30)),
                ("comments", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="auth.user")),
                ("request", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="compliance.compliancerequest")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
