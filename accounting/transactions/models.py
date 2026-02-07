from ckeditor.fields import RichTextField
from django.db import models
from django.utils import timezone
from users.models import Consultant, CustomUser, Office


class Client(models.Model):
    name = models.CharField(max_length=255)
    father_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name="نام پدر"
    )
    national_id = models.CharField(
        max_length=10, blank=True, default="", verbose_name="کد ملی"
    )
    birth_date = models.CharField(
        max_length=12, blank=True, default="", verbose_name="تاریخ تولد (شمسی)"
    )
    city_of_issuance = models.CharField(
        max_length=100, blank=True, default="", verbose_name="صادره از شهر"
    )
    phone = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    office = models.ForeignKey(Office, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class TransactionType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Deals(models.Model):
    STATUS_CHOICES = (
        ("init", "تعریف اولیه"),
        ("pending", "در انتظار تایید مدیر بنگاه"),
        ("approved", "تایید شده"),
        ("rejected", "رد شده"),
    )
    title = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, verbose_name="status", default="init"
    )
    type = models.ForeignKey(TransactionType, on_delete=models.PROTECT)
    amount = models.DecimalField(blank=True, null=True, max_digits=15, decimal_places=2)
    agreement_date = models.CharField(max_length=20, blank=True, default="")
    office_date = models.CharField(max_length=20, blank=True, default="")
    base_price = models.DecimalField(
        blank=True, null=True, max_digits=15, decimal_places=2
    )
    overpayment = models.DecimalField(
        blank=True, null=True, max_digits=15, decimal_places=2
    )
    overpayment_received = models.DecimalField(
        blank=True, null=True, max_digits=15, decimal_places=2
    )
    deposit_amount = models.DecimalField(
        blank=True,
        null=True,
        max_digits=15,
        decimal_places=2,
        verbose_name="رهن / ودیعه (ریال)",
    )
    rent_amount = models.DecimalField(
        blank=True,
        null=True,
        max_digits=15,
        decimal_places=2,
        verbose_name="اجاره (ریال)",
    )
    buyers = models.ManyToManyField(Client, related_name="purchased_deals", blank=True)
    sellers = models.ManyToManyField(Client, related_name="sold_deals", blank=True)
    office = models.ForeignKey(Office, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    description = models.TextField(blank=True, default="")
    date = models.CharField(max_length=20, blank=True, default="")
    consultants = models.ManyToManyField(
        Consultant, related_name="consultants_deals", null=True, blank=True
    )
    created_at = models.DateTimeField(default=timezone.now)
    rejection_reason = models.TextField(blank=True, default="", verbose_name="علت رد")

    def __str__(self):
        return f"{self.type.name} - {self.amount} ریال"


class DealClientCommission(models.Model):

    class ClientRole(models.TextChoices):
        BUYER = "buyer", "خریدار"
        SELLER = "seller", "فروشنده"

    deal = models.ForeignKey(
        Deals,
        on_delete=models.CASCADE,
        related_name="client_commissions",
        verbose_name="معامله",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="deal_commissions_to_pay",
        verbose_name="مشتری",
    )
    role = models.CharField(
        max_length=10,
        choices=ClientRole.choices,
        verbose_name="نقش",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="مبلغ کمیسیون قابل پرداخت (ریال)",
        null=True,
        blank=True,
        default=0,
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name="توضیحات",
    )

    class Meta:
        verbose_name = "کمیسیون قابل پرداخت مشتری"
        verbose_name_plural = "کمیسیون‌های قابل پرداخت مشتریان"
        unique_together = [["deal", "client", "role"]]

    def __str__(self):
        amt = f"{self.amount:,.0f}" if self.amount else "0"
        return f"{self.deal} - {self.client} ({self.get_role_display()}): {amt} ریال"


class DealProperty(models.Model):
    class UtilityShare(models.TextChoices):
        EXCLUSIVE = "exclusive", "اختصاصی"
        SHARED = "shared", "اشتراکی"

    deal = models.OneToOneField(
        Deals,
        on_delete=models.CASCADE,
        related_name="property_details",
        verbose_name="معامله مربوطه",
    )
    property_dang = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name="دانگ مورد معامله"
    )
    property_title = models.CharField(
        max_length=255, blank=True, default="", verbose_name="نوع/عنوان ملک"
    )
    registry_sub_number = models.CharField(
        max_length=50, blank=True, default="", verbose_name="پلاک ثبتی فرعی"
    )
    registry_main_number = models.CharField(
        max_length=50, blank=True, default="", verbose_name="پلاک ثبتی اصلی"
    )
    registry_piece_number = models.CharField(
        max_length=50, blank=True, default="", verbose_name="قطعه تفکیکی"
    )
    registry_section = models.CharField(
        max_length=100, blank=True, default="", verbose_name="بخش ثبتی"
    )
    registry_area = models.CharField(
        max_length=100, blank=True, default="", verbose_name="حوزه ثبتی"
    )
    area_m2 = models.DecimalField(
        blank=True,
        null=True,
        max_digits=10,
        decimal_places=2,
        verbose_name="مساحت (متر مربع)",
    )
    deed_serial = models.CharField(
        max_length=100, blank=True, default="", verbose_name="سریال سند مالکیت"
    )
    deed_page = models.CharField(
        max_length=50, blank=True, default="", verbose_name="صفحه سند مالکیت"
    )
    deed_book = models.CharField(
        max_length=50, blank=True, default="", verbose_name="دفتر سند مالکیت"
    )
    parking_dang = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name="دانگ پارکینگ"
    )
    parking_number = models.CharField(
        max_length=50, blank=True, default="", verbose_name="شماره پارکینگ"
    )
    parking_area_m2 = models.DecimalField(
        blank=True,
        null=True,
        max_digits=10,
        decimal_places=2,
        verbose_name="متراژ پارکینگ",
    )
    parking_deed_serial = models.CharField(
        max_length=100, blank=True, default="", verbose_name="سریال سند پارکینگ"
    )
    storage_dang = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name="دانگ انباری"
    )
    storage_number = models.CharField(
        max_length=50, blank=True, default="", verbose_name="شماره انباری"
    )
    storage_area_m2 = models.DecimalField(
        blank=True,
        null=True,
        max_digits=10,
        decimal_places=2,
        verbose_name="متراژ انباری",
    )
    storage_deed_serial = models.CharField(
        max_length=100, blank=True, default="", verbose_name="سریال سند انباری"
    )
    water_share = models.CharField(
        max_length=10,
        blank=True,
        default="",
        choices=UtilityShare.choices,
        verbose_name="حق اشتراک آب",
    )
    electricity_share = models.CharField(
        max_length=10,
        blank=True,
        default="",
        choices=UtilityShare.choices,
        verbose_name="حق اشتراک برق",
    )
    gas_share = models.CharField(
        max_length=10,
        blank=True,
        default="",
        choices=UtilityShare.choices,
        verbose_name="حق اشتراک گاز",
    )
    phone_lines_count = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name="تعداد خطوط تلفن"
    )
    phone_numbers = models.CharField(
        max_length=255, blank=True, default="", verbose_name="شماره تلفن‌ها"
    )
    property_address = models.TextField(blank=True, default="", verbose_name="آدرس ملک")
    postal_code = models.CharField(
        max_length=20, blank=True, default="", verbose_name="کد پستی"
    )

    def __str__(self):
        return f"اطلاعات ملک معامله {self.deal_id}"


class CommissionSplit(models.Model):
    TRANSACTION_ROLES = (
        ("office", "دفتر"),
        ("manager", "مدیر دفتر"),
        ("consultant", "مشاور"),
    )

    deal = models.ForeignKey(Deals, on_delete=models.CASCADE, related_name="splits")

    consultant = models.ForeignKey(
        Consultant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commissions",
        verbose_name="مشاور ذینفع",
    )

    role = models.CharField(max_length=20, choices=TRANSACTION_ROLES)

    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="درصد سهم", null=True, blank=True
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="مبلغ سهم (ریال)",
        null=True,
        blank=True,
    )

    def __str__(self):
        name = self.consultant.name if self.consultant else self.get_role_display()
        amt = f"{self.amount:,.0f}" if self.amount else "0"
        perc = f"{self.percentage}%" if self.percentage else "دستی"
        return f"{self.deal} - {name}: {amt} ریال ({perc})"

    def save(self, *args, **kwargs):
        base_income = self.deal.overpayment_received or 0

        if self.amount is not None and self.amount > 0:
            if base_income > 0 and not self.percentage:
                self.percentage = (self.amount / base_income) * 100

        elif self.percentage is not None:
            self.amount = (base_income * self.percentage) / 100

        else:
            self.amount = 0

        super().save(*args, **kwargs)


class ContractTemplate(models.Model):
    class ParticipantMode(models.TextChoices):
        SINGLE_SELLER_SINGLE_BUYER = "SS", "تک فروشنده - تک خریدار"
        MULTI_SELLER_SINGLE_BUYER = "MS", "چند فروشنده - تک خریدار"
        SINGLE_SELLER_MULTI_BUYER = "SM", "تک فروشنده - چند خریدار"
        MULTI_SELLER_MULTI_BUYER = "MM", "چند فروشنده - چند خریدار"
        UNIVERSAL = "ALL", "عمومی (مناسب همه حالات)"

    title = models.CharField(max_length=200, verbose_name="عنوان الگو")
    body = RichTextField(verbose_name="متن الگو")
    is_default = models.BooleanField(default=False, verbose_name="پیش فرض")
    transaction_type = models.ForeignKey("TransactionType", on_delete=models.CASCADE)

    participant_mode = models.CharField(
        max_length=3,
        choices=ParticipantMode.choices,
        default=ParticipantMode.UNIVERSAL,
        verbose_name="نوع طرفین قرارداد",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.get_participant_mode_display()})"


class DealContract(models.Model):

    deal = models.ForeignKey(
        Deals,
        on_delete=models.CASCADE,
        related_name="contracts",
        verbose_name="معامله مربوطه",
    )
    template = models.ForeignKey(
        ContractTemplate,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="الگوی استفاده شده",
    )
    has_header = models.BooleanField(
        default=False, verbose_name="چاپ سربرگ (نام بنگاه و تاریخ)"
    )
    content = RichTextField(verbose_name="متن قرارداد")

    is_finalized = models.BooleanField(default=False, verbose_name="نهایی شده؟")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"قرارداد معامله {self.deal.id} - {self.template.title if self.template else 'بدون الگو'}"
