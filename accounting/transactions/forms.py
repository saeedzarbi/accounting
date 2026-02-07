from django import forms
from transactions.models import (
    Client,
    DealContract,
    DealProperty,
    Deals,
    TransactionType,
)
from users.models import Consultant


class CreateDealFormStep1(forms.Form):
    name = forms.CharField(required=True)
    type = forms.ChoiceField(required=True, choices=[])
    agreement_date = forms.CharField()
    office_date = forms.CharField()
    amount = forms.DecimalField(required=True, max_digits=15, decimal_places=4)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].choices = [
            (item["id"], item["name"])
            for item in TransactionType.objects.values("id", "name")
        ]


class CreateDealFormStep2(forms.Form):
    buyers = forms.ModelMultipleChoiceField(
        queryset=Client.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "space-y-2"}),
        required=False,
    )

    sellers = forms.ModelMultipleChoiceField(
        queryset=Client.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "space-y-2"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clients = Client.objects.all()
        self.fields["buyers"].queryset = clients
        self.fields["sellers"].queryset = clients

    def clean(self):
        cleaned_data = super().clean()
        sellers = list(cleaned_data.get("sellers") or [])
        buyers = list(cleaned_data.get("buyers") or [])
        seller_ids = {c.pk for c in sellers}
        buyer_ids = {c.pk for c in buyers}
        if seller_ids & buyer_ids:
            raise forms.ValidationError(
                "یک مشتری نمی\u200cتواند هم\u200cزمان فروشنده و خریدار باشد."
            )
        return cleaned_data


class CreateDealFormStep3(forms.Form):
    base_price = forms.DecimalField(
        label="قیمت پایه", required=True, max_digits=15, decimal_places=0
    )

    overpayment = forms.DecimalField(
        label="کارمزد", required=True, max_digits=15, decimal_places=0
    )

    overpayment_received = forms.DecimalField(
        label="خیر دریافتی به دفتر",
        required=True,
        max_digits=15,
        decimal_places=0,
    )

    def clean_base_price(self):
        price = self.cleaned_data.get("base_price")
        if price is not None and price <= 0:
            raise forms.ValidationError("قیمت پایه باید مثبت باشد.")
        return price

    def clean_overpayment(self):
        comm = self.cleaned_data.get("overpayment")
        if comm is not None and comm <= 0:
            raise forms.ValidationError("بالابود باید مثبت باشد.")
        return comm

    def clean_overpayment_received(self):
        comm = self.cleaned_data.get("overpayment_received")
        if comm is not None and comm <= 0:
            raise forms.ValidationError("بالابود باید مثبت باشد.")
        return comm


class CreateDealFormStep4(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        consultants = Consultant.objects.all()

        for consultant in consultants:
            field_name = f"consultant_{consultant.id}"
            self.fields[field_name] = forms.DecimalField(
                label=f"درصد سهم {consultant.name}",
                required=False,
                max_digits=5,
                decimal_places=2,
                min_value=0,
                widget=forms.NumberInput(
                    attrs={
                        "class": "commission-input border p-2 rounded w-full",
                        "data-consultant-id": consultant.id,
                        "placeholder": "0.00",
                    }
                ),
            )


class CreateDealFormStep5(forms.Form):
    pass


class DealCreateForm(forms.ModelForm):
    class Meta:
        model = Deals
        fields = ["title", "type", "sellers", "buyers"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "عنوان معامله را وارد کنید",
                }
            ),
            "type": forms.Select(attrs={"class": "form-control"}),
            "sellers": forms.SelectMultiple(attrs={"class": "form-control"}),
            "buyers": forms.SelectMultiple(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        sellers = list(cleaned_data.get("sellers") or [])
        buyers = list(cleaned_data.get("buyers") or [])
        if not sellers:
            raise forms.ValidationError("انتخاب حداقل یک فروشنده/موجر الزامی است.")
        if not buyers:
            raise forms.ValidationError("انتخاب حداقل یک خریدار/مستأجر الزامی است.")
        seller_ids = {c.pk for c in sellers}
        buyer_ids = {c.pk for c in buyers}
        overlap = seller_ids & buyer_ids
        if overlap:
            raise forms.ValidationError(
                "یک مشتری نمی\u200cتواند هم\u200cزمان فروشنده و خریدار باشد. لطفاً طرفین را اصلاح کنید."
            )
        return cleaned_data


class DealPropertyForm(forms.ModelForm):
    class Meta:
        model = DealProperty
        fields = [
            "property_dang",
            "property_title",
            "registry_sub_number",
            "registry_main_number",
            "registry_piece_number",
            "registry_section",
            "registry_area",
            "area_m2",
            "deed_serial",
            "deed_page",
            "deed_book",
            "parking_dang",
            "parking_number",
            "parking_area_m2",
            "parking_deed_serial",
            "storage_dang",
            "storage_number",
            "storage_area_m2",
            "storage_deed_serial",
            "water_share",
            "electricity_share",
            "gas_share",
            "phone_lines_count",
            "phone_numbers",
            "property_address",
            "postal_code",
        ]
        widgets = {
            "property_dang": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "placeholder": "مثلاً ۶",
                }
            ),
            "property_title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "مثلاً آپارتمان مسکونی"}
            ),
            "registry_sub_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "پلاک فرعی"}
            ),
            "registry_main_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "پلاک اصلی"}
            ),
            "registry_piece_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "قطعه تفکیکی"}
            ),
            "registry_section": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "بخش ثبتی"}
            ),
            "registry_area": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "حوزه ثبتی"}
            ),
            "area_m2": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "step": "0.01",
                    "placeholder": "مثلاً ۱۲۰",
                }
            ),
            "deed_serial": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "سریال سند مالکیت"}
            ),
            "deed_page": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "صفحه"}
            ),
            "deed_book": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "دفتر"}
            ),
            "parking_dang": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "placeholder": "دانگ پارکینگ",
                }
            ),
            "parking_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "شماره پارکینگ"}
            ),
            "parking_area_m2": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "step": "0.01",
                    "placeholder": "متراژ پارکینگ",
                }
            ),
            "parking_deed_serial": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "سریال سند پارکینگ"}
            ),
            "storage_dang": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "placeholder": "دانگ انباری",
                }
            ),
            "storage_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "شماره انباری"}
            ),
            "storage_area_m2": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "step": "0.01",
                    "placeholder": "متراژ انباری",
                }
            ),
            "storage_deed_serial": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "سریال سند انباری"}
            ),
            "water_share": forms.RadioSelect(attrs={"class": "choice-inline"}),
            "electricity_share": forms.RadioSelect(attrs={"class": "choice-inline"}),
            "gas_share": forms.RadioSelect(attrs={"class": "choice-inline"}),
            "phone_lines_count": forms.NumberInput(
                attrs={
                    "class": "form-control numeric-input",
                    "min": 0,
                    "placeholder": "تعداد خطوط",
                }
            ),
            "phone_numbers": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "مثلاً 021-xxxxxxx"}
            ),
            "property_address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "آدرس کامل ملک",
                }
            ),
            "postal_code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": 20,
                    "placeholder": "کدپستی",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("water_share", "electricity_share", "gas_share"):
            self.fields[field_name].required = False


class DealContractForm(forms.ModelForm):
    class Meta:
        model = DealContract
        fields = ["content", "is_finalized", "has_header"]
        labels = {
            "content": "متن قرارداد",
            "is_finalized": "تایید و نهایی‌سازی قرارداد",
        }

        widgets = {
            "is_finalized": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
