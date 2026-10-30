from django.db import migrations, models
import django.db.models.deletion


def migrate_manager_audiences(apps, schema_editor):
    Document = apps.get_model("compliance", "Document")
    for doc in Document.objects.filter(audience="SELECTED_MANAGERS").iterator():
        department_ids = list(doc.audience_managers.filter(profile__department__isnull=False).values_list("profile__department_id", flat=True).distinct())
        if department_ids:
            doc.audience_departments.set(department_ids)


class Migration(migrations.Migration):
    dependencies = [("compliance", "0011_document_audience_and_manager_role")]
    operations = [
        migrations.AddField(
            model_name="document", name="audience_departments",
            field=models.ManyToManyField(blank=True, related_name="selected_management_documents", to="compliance.department"),
        ),
        migrations.AlterField(
            model_name="document", name="audience",
            field=models.CharField(choices=[("UNCLASSIFIED", "Not Classified"), ("PUBLIC", "Public"), ("DEPARTMENT", "Specific Department"), ("ALL_MANAGERS", "All Management Staff"), ("SELECTED_MANAGERS", "Selected Departments (Managers)")], db_index=True, default="UNCLASSIFIED", max_length=24),
        ),
        migrations.RunPython(migrate_manager_audiences, migrations.RunPython.noop),
    ]
