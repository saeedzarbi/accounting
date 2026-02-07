from django.contrib import admin

from .models import Consultant, CustomUser, Office, Role


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_phone")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("name", "office", "phone", "created_at")
    list_filter = ("office", "created_at")
    search_fields = ("name",)
    ordering = ("-created_at",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_editable = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "full_name",
        "phone_number",
        "office",
    )
    list_filter = ("office", "roles", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "phone_number")
    ordering = ("username",)
