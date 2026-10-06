from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from compliance.services import backup_to_zip

class Command(BaseCommand):
    help = "Create a ZIP backup of the database and controlled document storage."
    def handle(self, *args, **options):
        target = Path(settings.MEDIA_ROOT) / "backups" / f"MKDSS_backup_{timezone.now():%Y%m%d_%H%M%S}.zip"
        backup_to_zip(settings.BASE_DIR, target)
        self.stdout.write(self.style.SUCCESS(str(target)))
