from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        # Join the previously separate 0009 migration branches here. The
        # manager/reader role migration was still unapplied in the user's DB,
        # while the document-source branch had continued through 0012.
        ("compliance", "0012_department_based_audience"),
        ("compliance", "0009_manager_reader_only_roles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Restore the role choices used by the current application model after
        # both historical 0009 branches have been joined.
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("SYSTEM_ADMIN", "System Admin"),
                    ("COMPLIANCE", "Compliance"),
                    ("APPROVER", "Approver"),
                    ("USER", "User"),
                    ("MANAGER", "Manager"),
                    ("READER", "Reader"),
                ],
                default="USER",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="employee_id",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="documentacknowledgment",
            name="identity_user",
            field=models.ForeignKey(
                blank=True,
                help_text="Set for individual Manager and Compliance account acknowledgments; null for shared Reader accounts.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="account_document_acknowledgments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="documentacknowledgment",
            constraint=models.UniqueConstraint(
                condition=models.Q(identity_user__isnull=False),
                fields=("identity_user", "version"),
                name="uniq_account_document_ack_version",
            ),
        ),
    ]
