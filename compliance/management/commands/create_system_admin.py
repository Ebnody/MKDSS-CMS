from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from compliance.models import Role, UserProfile

class Command(BaseCommand):
    help = "Create or promote the initial MKDSS System Admin account."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Existing username to promote, or new username to create.")
        parser.add_argument("--email", default="", help="Email for a newly created account.")
        parser.add_argument("--password", help="Password for a newly created account. If omitted, prompt securely.")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options.get("username") or input("System Admin username: ").strip()
        if not username:
            raise CommandError("Username is required.")
        try:
            user = User.objects.get(username=username)
            created = False
        except User.DoesNotExist:
            password = options.get("password")
            if password is None:
                from getpass import getpass
                password = getpass("System Admin password: ")
            if not password or len(password) < 10:
                raise CommandError("Password must be at least 10 characters.")
            user = User(username=username, email=options.get("email", ""), is_active=True, is_staff=False, is_superuser=False)
            user.set_password(password)
            user.save()
            created = True
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = Role.SYSTEM_ADMIN
        profile.active = True
        profile.save(update_fields=["role", "active"])
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        verb = "created" if created else "promoted"
        self.stdout.write(self.style.SUCCESS(f"System Admin account {verb}: {user.username}"))
        self.stdout.write("Sign in through the MKDSS web login. Do not use /django-admin/ for normal system administration.")
