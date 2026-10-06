from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from compliance import views as compliance_views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password-change/", auth_views.PasswordChangeView.as_view(template_name="registration/password_change.html", success_url="/password-change/done/"), name="password_change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"), name="password_change_done"),
    path("django-admin/", admin.site.urls),
    path("", include("compliance.urls")),
]
