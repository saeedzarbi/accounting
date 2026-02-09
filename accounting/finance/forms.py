# Forms for finance app - Phase 1: Journal, Receipt, Payment

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Account


def _parse_amount(value):
    if value is None or value == "":
        return None
    s = str(value).strip().replace(",", "").replace("٬", "").replace("،", "")
    try:
        return Decimal(s) if s else None
    except Exception:
        return None


class JournalEntryForm(forms.Form):
    """فرم سند روزنامه دستی: چند ردیف حساب، بدهکار، بستانکار، شرح."""

    date = forms.DateField(
        label="تاریخ سند",
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    description = forms.CharField(
        label="شرح سند",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2, "class": "form-control", "placeholder": "شرح کلی سند"}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rows = []

    def add_row(self, account_id=None, debit=None, credit=None, row_description=""):
        self._rows.append(
            {
                "account_id": account_id,
                "debit": debit or "",
                "credit": credit or "",
                "description": row_description or "",
            }
            if account_id is not None
            else {"account_id": "", "debit": "", "credit": "", "description": ""}
        )

    def load_from_post(self, data):
        """از POST دیتا ردیف‌ها را بخوان (account_id_0, debit_0, ...)."""
        self._rows = []
        i = 0
        while True:
            acc = data.get(f"account_id_{i}")
            if acc is None:
                break
            self._rows.append(
                {
                    "account_id": acc,
                    "debit": data.get(f"debit_{i}", ""),
                    "credit": data.get(f"credit_{i}", ""),
                    "description": data.get(f"row_description_{i}", ""),
                }
            )
            i += 1
        if not self._rows:
            self._rows = [
                {"account_id": "", "debit": "", "credit": "", "description": ""}
            ]

    def get_rows(self):
        if not self._rows:
            return [{"account_id": "", "debit": "", "credit": "", "description": ""}]
        return self._rows

    def clean_rows(self, data):
        # جمع‌آوری اندیس‌ها از کلیدهای account_id_0, account_id_1, ...
        indices = set()
        for key in data:
            if key.startswith("account_id_"):
                suffix = key.replace("account_id_", "", 1)
                if suffix.isdigit():
                    indices.add(int(suffix))
        rows = []
        for i in sorted(indices):
            acc = data.get(f"account_id_{i}", "").strip()
            debit = _parse_amount(data.get(f"debit_{i}"))
            credit = _parse_amount(data.get(f"credit_{i}"))
            if acc and (debit or credit):
                try:
                    account = Account.objects.get(pk=int(acc), is_active=True)
                except (ValueError, Account.DoesNotExist) as err:
                    raise ValidationError(
                        f"ردیف {i + 1}: حساب معتبر انتخاب کنید."
                    ) from err
                if debit and credit:
                    raise ValidationError(
                        f"ردیف {i + 1}: فقط بدهکار یا بستانکار پر شود."
                    )
                if (debit or 0) < 0 or (credit or 0) < 0:
                    raise ValidationError(f"ردیف {i + 1}: مبلغ نمی‌تواند منفی باشد.")
                rows.append(
                    {
                        "account": account,
                        "debit": debit or Decimal("0"),
                        "credit": credit or Decimal("0"),
                        "description": (data.get(f"row_description_{i}") or "").strip(),
                    }
                )
        return rows


class VoucherDocumentForm(forms.Form):
    """
    فرم واحد برای سند دریافت یا سند پرداخت.
    با فیلد پنهان voucher_type مشخص می‌شود نوع سند (receipt / payment).
    """

    voucher_type = forms.ChoiceField(
        choices=[("receipt", "سند دریافت"), ("payment", "سند پرداخت")],
        widget=forms.HiddenInput(),
        required=True,
    )
    date = forms.DateField(
        label="تاریخ",
        required=True,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    account = forms.ModelChoiceField(
        label="حساب طرف مقابل",
        queryset=Account.objects.filter(is_active=True).order_by("code"),
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    amount = forms.DecimalField(
        label="مبلغ (ریال)",
        min_value=Decimal("1"),
        required=True,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "0"}),
    )
    method = forms.CharField(
        label="روش پرداخت/دریافت",
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "نقد، کارت، حواله و ..."}
        ),
    )
    description = forms.CharField(
        label="توضیحات",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
    )
    receipt_file = forms.FileField(
        label="ضمیمه رسید",
        required=False,
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": "image/*,.pdf"}
        ),
    )

    def __init__(self, *args, voucher_type="receipt", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["voucher_type"].initial = voucher_type
        if voucher_type == "receipt":
            self.fields["date"].label = "تاریخ دریافت"
            self.fields["account"].label = "حساب طرف مقابل (واریزکننده)"
        else:
            self.fields["date"].label = "تاریخ پرداخت"
            self.fields["account"].label = "حساب طرف مقابل (دریافت‌کننده)"
