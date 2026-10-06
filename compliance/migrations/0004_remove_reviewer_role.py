from django.db import migrations


def convert_reviewer_accounts(apps, schema_editor):
    UserProfile = apps.get_model("compliance", "UserProfile")
    UserProfile.objects.filter(role="REVIEWER").update(role="USER")


def reverse_conversion(apps, schema_editor):
    # Do not recreate Reviewer accounts automatically on rollback.
    pass


class Migration(migrations.Migration):
    dependencies = [("compliance", "0003_request_document_approval_and_cleanup")]

    operations = [
        migrations.RunPython(convert_reviewer_accounts, reverse_conversion),
    ]
