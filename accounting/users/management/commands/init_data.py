from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from users.models import Office, Role


class Command(BaseCommand):
    help = "Initialize initial data for the application (offices, roles, users)"

    def handle(self, *args, **options):
        offices_data = [
            {"name": "دفتر عیان", "contact_phone": "021-12345678"},
        ]
        for office_data in offices_data:
            Office.objects.get_or_create(**office_data)
            self.stdout.write(
                self.style.SUCCESS(f'✅ دفتر "{office_data["name"]}" ایجاد شد')
            )

        role_choices = [
            ("office_manager", "مدیر دفتر"),
            ("office_specialist", "کارشناس دفتر"),
        ]
        for role_code, role_name in role_choices:
            Role.objects.get_or_create(name=role_code)
            self.stdout.write(self.style.SUCCESS(f'✅ نقش "{role_name}" ایجاد شد'))

        User = get_user_model()
        users_data = [
            {
                "username": "khabazi",
                "email": "khabazi@ayanfile.com",
                "password": "khabazi123",
                "office": Office.objects.get(name="دفتر عیان"),
                "roles": ["office_manager"],
                "phone_number": "09123456789",
            },
            {
                "username": "op_user",
                "email": "op_user@ayanfile.com",
                "password": "op_user123",
                "office": Office.objects.get(name="دفتر عیان"),
                "roles": ["office_specialist"],
                "phone_number": "09129876543",
            },
        ]

        for user_data in users_data:
            user = User.objects.create_user(
                username=user_data["username"],
                email=user_data["email"],
                password=user_data["password"],
            )
            user.phone_number = user_data["phone_number"]
            user.office = user_data["office"]
            user.save()

            for role_code in user_data["roles"]:
                role = Role.objects.get(name=role_code)
                user.roles.add(role)
            user.save()

            self.stdout.write(
                self.style.SUCCESS(f'✅ کاربر "{user.username}" ایجاد شد')
            )

        self.stdout.write(self.style.SUCCESS("✅ داده‌های اولیه با موفقیت ایجاد شد!"))
