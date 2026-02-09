from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from transactions.models import Client

from .models import Consultant

User = get_user_model()


class LoginForm(AuthenticationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "autocapitalize": "none",
                "spellcheck": "false",
                "inputmode": "text",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        )


class ProfilePasswordChangeForm(PasswordChangeForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "رمز عبور فعلی"
        self.fields["new_password1"].label = "رمز عبور جدید"
        self.fields["new_password2"].label = "تکرار رمز عبور جدید"
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "profile-input")
            f.widget.attrs.setdefault("autocomplete", "off")


class ProfileUpdateForm(forms.ModelForm):
    """نام، نام خانوادگی و تلفن قابل ویرایش."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone_number")
        labels = {
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "phone_number": "شماره تلفن",
        }
        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "نام",
                    "autocomplete": "given-name",
                    "class": "profile-input",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "placeholder": "نام خانوادگی",
                    "autocomplete": "family-name",
                    "class": "profile-input",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "placeholder": "۰۹۱۲۳۴۵۶۷۸۹",
                    "autocomplete": "tel",
                    "class": "profile-input",
                }
            ),
        }


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = (
            "name",
            "father_name",
            "national_id",
            "birth_date",
            "city_of_issuance",
            "phone",
        )
        labels = {
            "name": "نام و نام خانوادگی",
            "father_name": "نام پدر",
            "national_id": "کد ملی",
            "birth_date": "تاریخ تولد (شمسی)",
            "city_of_issuance": "محل صدور",
            "phone": "شماره تماس",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "نام"}
            ),
            "father_name": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "نام پدر"}
            ),
            "national_id": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "کد ملی"}
            ),
            "birth_date": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "۱۳۷۵/۰۲/۱۲"}
            ),
            "city_of_issuance": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "تهران"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "۰۹۱۲۳۴۵۶۷۸۹"}
            ),
        }


class ConsultantLoginForm(forms.Form):
    """فعال‌سازی ورود برای مشاور: نام کاربری و رمز عبور."""

    username = forms.CharField(
        max_length=150,
        label="نام کاربری",
        widget=forms.TextInput(
            attrs={"class": "profile-input", "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(
            attrs={"class": "profile-input", "autocomplete": "new-password"}
        ),
        min_length=6,
    )

    def clean_username(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        username = self.cleaned_data.get("username")
        if username and User.objects.filter(username=username).exists():
            raise forms.ValidationError("این نام کاربری قبلاً استفاده شده است.")
        return username


class ConsultantForm(forms.ModelForm):
    """
    فرم مشاور: حساب‌ها به صورت خودکار از طریق finance.utils مدیریت می‌شوند.
    """

    class Meta:
        model = Consultant
        fields = ("name", "phone")
        labels = {
            "name": "نام مشاور",
            "phone": "شماره تماس",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "نام"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "profile-input", "placeholder": "۰۹۱۲۳۴۵۶۷۸۹"}
            ),
        }
