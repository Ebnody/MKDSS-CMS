from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark one notification read and return its destination for client-side navigation."""
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    unread = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse({
        "ok": True,
        "unread": unread,
        "url": notification.url or "",
    })


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)
    return JsonResponse({"ok": True, "unread": 0})


@login_required
def notifications_page(request):
    all_notifications = request.user.notifications.all()[:100]
    return render(
        request,
        "compliance/notifications.html",
        {"all_notifications": all_notifications},
    )
