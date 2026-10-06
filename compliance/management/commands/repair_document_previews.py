from django.core.management.base import BaseCommand

from compliance.models import DocumentVersion
from compliance.services import generate_version_preview


class Command(BaseCommand):
    help = "Generate missing previews for existing document versions."

    def handle(self, *args, **options):
        versions = DocumentVersion.objects.all().order_by("id")

        total = versions.count()
        repaired = 0
        skipped = 0
        failed = 0

        self.stdout.write(
            self.style.NOTICE(
                f"Checking {total} document version(s)..."
            )
        )

        for version in versions:
            try:
                if version.preview_file:
                    try:
                        if version.preview_file.storage.exists(
                            version.preview_file.name
                        ):
                            skipped += 1
                            self.stdout.write(
                                f"SKIP  Version {version.pk}: "
                                f"preview already exists"
                            )
                            continue
                    except Exception:
                        pass

                preview = generate_version_preview(version)

                if preview:
                    repaired += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"OK    Version {version.pk}: "
                            f"{version.original_name}"
                        )
                    )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"FAIL  Version {version.pk}: "
                            f"{version.original_name} "
                            f"(preview could not be generated)"
                        )
                    )

            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"FAIL  Version {version.pk}: "
                        f"{version.original_name} - {exc}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                f"Finished: {total} total | "
                f"{repaired} repaired | "
                f"{skipped} skipped | "
                f"{failed} failed"
            )
        )

        if failed:
            self.stdout.write(
                self.style.WARNING(
                    "Some previews could not be generated."
                )
            )