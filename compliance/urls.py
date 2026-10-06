from django.urls import path
from . import views
from .notification_views import notifications_page, mark_notification_read, mark_all_notifications_read

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Published document access: every application role except System Admin.
    path("documents/", views.published_documents, name="published_documents"),
    path("documents/<int:pk>/read/", views.read_document, name="read_document"),
    path("versions/<int:pk>/stream/", views.stream_document, name="stream_document"),
    path("versions/<int:pk>/finish/", views.finish_reading, name="finish_reading"),

    # Compliance document control.
    path("documents/control/", views.compliance_documents, name="compliance_documents"),
    path("documents/new/", views.document_create, name="document_create"),
    path("documents/existing/upload/", views.upload_existing_document, name="upload_existing_document"),
    path("documents/<int:pk>/", views.document_detail, name="document_detail"),
    path("documents/<int:pk>/edit/", views.edit_document, name="edit_document"),
    path("documents/<int:pk>/publish/", views.publish_document, name="publish_document"),
    path("documents/<int:pk>/block/", views.block_document, name="block_document"),
    path("documents/<int:pk>/unblock/", views.unblock_document, name="unblock_document"),
    path("documents/<int:pk>/delete/", views.delete_document, name="delete_document"),

    # Compliance review.
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:pk>/", views.review_document, name="review_document"),
    path("versions/<int:pk>/controlled-stream/", views.stream_controlled_version, name="controlled_stream_version"),

    # Requests.
    path("requests/", views.requests_list, name="requests"),
    path("requests/new/", views.new_request, name="new_request"),
    path("requests/change/", views.change_request, name="change_request"),
    path("requests/<int:pk>/process/", views.process_request, name="process_request"),
    path("compliance/queue/", views.compliance_queue, name="compliance_queue"),

    # Approvals: initial request approval and final document approval.
    path("approvals/", views.approval_queue, name="approval_queue"),
    path("approvals/requests/<int:pk>/", views.approve_request, name="approve_request"),
    path("approvals/documents/<int:pk>/", views.approve_document, name="approve_document"),

    # Reading/reporting.
    path("dashboard/readings/<int:pk>/", views.reading_drilldown, name="reading_drilldown"),
    path("reports/", views.reports, name="reports"),
    path("reports/reading.csv", views.report_csv, name="report_csv"),
    path("reports/reading.pdf", views.report_pdf, name="report_pdf"),
    path("notifications/", notifications_page, name="notifications"),
    path("notifications/<int:pk>/read/", mark_notification_read, name="notification_read"),
    path("notifications/read-all/", mark_all_notifications_read, name="notifications_read_all"),

    # System Admin.
    path("admin-panel/users/", views.admin_users, name="admin_users"),
    path("admin-panel/users/new/", views.admin_user_edit, name="admin_user_new"),
    path("admin-panel/users/<int:pk>/edit/", views.admin_user_edit, name="admin_user_edit"),
    path("admin-panel/users/<int:pk>/delete/", views.admin_user_delete, name="admin_user_delete"),
    path("admin-panel/users/<int:pk>/toggle/", views.admin_user_toggle, name="admin_user_toggle"),
    path("admin-panel/departments/", views.admin_departments, name="admin_departments"),
    path("admin-panel/audit/", views.audit_logs, name="audit_logs"),
    path("admin-panel/health/", views.admin_health, name="admin_health"),
    path("admin-panel/settings/", views.admin_settings, name="admin_settings"),
    path("admin-panel/backup/", views.admin_backup, name="admin_backup"),
    path("admin-panel/restore/", views.admin_restore, name="admin_restore"),
]
