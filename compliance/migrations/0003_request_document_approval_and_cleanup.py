from django.db import migrations, models
import django.db.models.deletion


def normalize_request_statuses(apps, schema_editor):
    ComplianceRequest = apps.get_model("compliance", "ComplianceRequest")
    ComplianceRequest.objects.filter(status="COMPLIANCE_QUEUE").update(status="APPROVED")


def reverse_normalize_request_statuses(apps, schema_editor):
    # Historical COMPLIANCE_QUEUE rows cannot be reconstructed reliably.
    pass


class Migration(migrations.Migration):
    dependencies = [("compliance", "0002_workflow_hardening")]

    operations = [
        migrations.RunPython(normalize_request_statuses, reverse_normalize_request_statuses),
        migrations.AlterField(
            model_name="document",
            name="state",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("UNDER_REVIEW", "Under Compliance Review"),
                    ("REVISION_REQUIRED", "Revision Required"),
                    ("REVIEW_ACCEPTED", "Compliance Review Accepted"),
                    ("PENDING_APPROVAL", "Pending Final Approval"),
                    ("PUBLISHED", "Published"),
                    ("ARCHIVED", "Blocked / Archived"),
                ],
                default="DRAFT",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="documentversion",
            name="document",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="compliance.document"),
        ),
        migrations.AlterField(
            model_name="documentversion",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("UNDER_REVIEW", "Under Compliance Review"),
                    ("REVISION_REQUIRED", "Revision Required"),
                    ("REVIEW_ACCEPTED", "Compliance Review Accepted"),
                    ("PENDING_APPROVAL", "Pending Final Approval"),
                    ("PUBLISHED", "Published"),
                    ("ARCHIVED", "Archived"),
                ],
                default="DRAFT",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="documentreview",
            name="version",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="compliance.documentversion"),
        ),
        migrations.CreateModel(
            name="DocumentApproval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected")], max_length=20)),
                ("remarks", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approver", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="document_approvals", to="auth.user")),
                ("version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="approvals", to="compliance.documentversion")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterField(
            model_name="readingrecord",
            name="version",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reading_records", to="compliance.documentversion"),
        ),
        migrations.AlterField(
            model_name="compliancerequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING_APPROVAL", "Pending Initial Approval"),
                    ("APPROVED", "Request Approved"),
                    ("REJECTED", "Request Rejected"),
                    ("IN_PROGRESS", "Document Being Prepared"),
                    ("UNDER_REVIEW", "Under Compliance Review"),
                    ("DOCUMENT_PENDING_APPROVAL", "Document Pending Final Approval"),
                    ("DOCUMENT_APPROVED", "Document Approved"),
                    ("COMPLETED", "Published / Completed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="PENDING_APPROVAL",
                max_length=40,
            ),
        ),
        migrations.AlterField(
            model_name="compliancerequesthistory",
            name="from_status",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AlterField(
            model_name="compliancerequesthistory",
            name="to_status",
            field=models.CharField(max_length=40),
        ),
        migrations.AlterField(
            model_name="compliancerequest",
            name="related_document",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="compliance_requests", to="compliance.document"),
        ),
        migrations.AlterField(
            model_name="compliancerequest",
            name="related_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="related_requests", to="compliance.documentversion"),
        ),
    ]
