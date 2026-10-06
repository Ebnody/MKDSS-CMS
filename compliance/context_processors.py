def notifications(request):
    if not request.user.is_authenticated:
        return {"notification_items": [], "notification_unread_count": 0}

    qs = request.user.notifications.all()
    return {
        "notification_items": qs[:8],
        "notification_unread_count": qs.filter(is_read=False).count(),
    }
