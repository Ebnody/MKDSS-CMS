from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compliance", "0008_alter_compliancerequest_options_and_more")]

    operations = [
        migrations.AddField(
            model_name="document",
            name="source",
            field=models.CharField(
                choices=[
                    ("SYSTEM", "Created in Compliance Management System"),
                    ("EXISTING", "Existing Document"),
                ],
                default="SYSTEM",
                max_length=20,
            ),
        ),
    ]
