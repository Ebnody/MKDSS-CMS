from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def convert_legacy_users(apps, schema_editor):
    UserProfile = apps.get_model("compliance", "UserProfile")
    UserProfile.objects.filter(role="USER").update(role="MANAGER")


def reverse_convert(apps, schema_editor):
    UserProfile = apps.get_model("compliance", "UserProfile")
    UserProfile.objects.filter(role="MANAGER").update(role="USER")


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0010_documentacknowledgment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="document", name="audience",
            field=models.CharField(choices=[("UNCLASSIFIED", "Not Classified"), ("PUBLIC", "Public"), ("DEPARTMENT", "Specific Department"), ("ALL_MANAGERS", "All Management Staff"), ("SELECTED_MANAGERS", "Selected Management Staff")], db_index=True, default="UNCLASSIFIED", max_length=24),
        ),
        migrations.AddField(
            model_name="document", name="audience_department",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audience_documents", to="compliance.department"),
        ),
        migrations.AddField(
            model_name="document", name="audience_managers",
            field=models.ManyToManyField(blank=True, related_name="management_audience_documents", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="userprofile", name="role",
            field=models.CharField(choices=[("SYSTEM_ADMIN", "System Admin"), ("COMPLIANCE", "Compliance"), ("APPROVER", "Approver"), ("USER", "User"), ("MANAGER", "Manager"), ("READER", "Reader")], default="USER", max_length=30),
        ),
        migrations.RunPython(convert_legacy_users, reverse_convert),
    ]
