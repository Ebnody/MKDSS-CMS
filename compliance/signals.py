from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserProfile, AuditLog


def ip(request):
    return request.META.get("REMOTE_ADDR") if request else None


@receiver(post_save, sender=User)
def ensure_profile(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def login_audit(sender, request, user, **kwargs):
    AuditLog.objects.create(user=user, action="LOGIN", ip_address=ip(request), details={})


@receiver(user_logged_out)
def logout_audit(sender, request, user, **kwargs):
    AuditLog.objects.create(user=user, action="LOGOUT", ip_address=ip(request), details={})


@receiver(user_login_failed)
def failed_login_audit(sender, credentials, request, **kwargs):
    AuditLog.objects.create(user=None, action="FAILED_LOGIN", ip_address=ip(request), details={"username": credentials.get("username", "")})
