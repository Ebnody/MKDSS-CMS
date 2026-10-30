from django.db import migrations, models


def move_legacy_users_to_manager(apps, schema_editor):
    UserProfile = apps.get_model("compliance", "UserProfile")
    UserProfile.objects.filter(role="USER").update(role="MANAGER")


def reverse_manager_role(apps, schema_editor):
    UserProfile = apps.get_model("compliance", "UserProfile")
    UserProfile.objects.filter(role="MANAGER").update(role="USER")


class Migration(migrations.Migration):
    dependencies = [("compliance", "0008_alter_compliancerequest_options_and_more")]
    operations = [
        migrations.RunPython(move_legacy_users_to_manager, reverse_manager_role),
        migrations.AlterField(
            model_name="userprofile", name="role",
            field=models.CharField(choices=[
                ("SYSTEM_ADMIN", "System Admin"),
                ("COMPLIANCE", "Compliance"),
                ("APPROVER", "Approver"),
                ("MANAGER", "Manager"),
                ("READER_ONLY", "Reader Only"),
            ], default="MANAGER", max_length=30),
        ),
    ]
