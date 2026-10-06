from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("compliance", "0007_repair_stale_approval_notifications")]

    operations = [
        migrations.AlterModelOptions(
            name="compliancerequest",
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("SYSTEM_ADMIN", "System Admin"),
                    ("COMPLIANCE", "Compliance"),
                    ("APPROVER", "Approver"),
                    ("USER", "User"),
                ],
                default="USER",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="documentapproval",
            name="version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="approvals",
                to="compliance.documentversion",
            ),
        ),
    ]
