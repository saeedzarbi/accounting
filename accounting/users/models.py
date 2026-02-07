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
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Role(models.Model):
    ROLE_CHOICES = (
        ("office_manager", "مدیر دفتر"),
        ("office_specialist", "کارشناس دفتر"),
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

        return "مشخص نشده"

    @property
    def is_office_manager(self):
        return self.roles.filter(name="office_manager").exists()
