from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("login/", views.LoginViewUI.as_view(), name="login"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/manage/", views.manage_accounts, name="manage-accounts"),
    path(
        "accounts/clients/<int:client_id>/edit/",
        views.edit_client,
        name="edit-client",
    ),
    path(
        "accounts/clients/<int:client_id>/delete/",
        views.delete_client,
        name="delete-client",
    ),
    path(
        "accounts/consultants/<int:consultant_id>/edit/",
        views.edit_consultant,
        name="edit-consultant",
    ),
    path(
        "accounts/consultants/<int:consultant_id>/delete/",
        views.delete_consultant,
        name="delete-consultant",
    ),
]
