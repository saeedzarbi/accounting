from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Office(models.Model):
    name = models.CharField(max_length=255, verbose_name="office_name")
    contact_phone = models.CharField(max_length=20, verbose_name="contact_phone")

    def __str__(self):
        return self.name


class Consultant(models.Model):
    office = models.ForeignKey(
        Office, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="office"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="consultant_profile",
        verbose_name="کاربر ورود",
    )
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Role(models.Model):
    ROLE_CHOICES = (
        ("office_manager", "مدیر دفتر"),
        ("office_specialist", "کارشناس دفتر"),
        ("consultant", "مشاور"),
    )
    name = models.CharField(
        max_length=50, choices=ROLE_CHOICES, unique=True, verbose_name="role"
    )

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    office = models.ForeignKey(
        Office, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="office"
    )
    roles = models.ManyToManyField(Role, blank=True, verbose_name="roles")

    phone_number = models.CharField(max_length=20, blank=True, verbose_name="phone")

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def role(self):
        role = self.roles.all().first()

        if role.name == "office_specialist":
            return "کارشناس دفتر"

        if role.name == "office_manager":
            return "مدیر دفتر"

        if role.name == "consultant":
            return "مشاور"

        return "مشخص نشده"

    @property
    def is_office_manager(self):
        return self.roles.filter(name="office_manager").exists()

    @property
    def is_consultant(self):
        """کاربری که به عنوان مشاور لاگین کرده (لینک به رکورد Consultant)."""
        return (
            hasattr(self, "consultant_profile") and self.consultant_profile is not None
        )
