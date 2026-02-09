import os
import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


def payment_receipt_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1] or ".bin"
    safe_ext = ext.lower() if ext else ".bin"
    return "finance/payment_receipts/{year}/{month}/{uuid}{ext}".format(
        year=timezone.now().strftime("%Y"),
        month=timezone.now().strftime("%m"),
        uuid=uuid.uuid4().hex,
        ext=safe_ext,
    )


def pending_payment_receipt_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1] or ".bin"
    safe_ext = ext.lower() if ext else ".bin"
    return "finance/pending_receipts/{year}/{month}/{uuid}{ext}".format(
        year=timezone.now().strftime("%Y"),
        month=timezone.now().strftime("%m"),
        uuid=uuid.uuid4().hex,
        ext=safe_ext,
    )


class Account(models.Model):

    class AccountType(models.TextChoices):
        ASSET = "asset", "دارایی"
        LIABILITY = "liability", "بدهی"
        INCOME = "income", "درآمد"
        EXPENSE = "expense", "هزینه"

    class AccountCategory(models.TextChoices):
        RECEIVABLE_CLIENT = "receivable_client", "بستانکاری از مشتری"
        RECEIVABLE_CONSULTANT = "receivable_consultant", "بستانکاری از مشاور"
        RECEIVABLE_OFFICE = "receivable_office", "بستانکاری از بنگاه"
        RECEIVABLE_MANAGER = "receivable_manager", "بستانکاری از مدیر بنگاه"
        PAYABLE_CLIENT = "payable_client", "طلبکاری به مشتری"
        PAYABLE_CONSULTANT = "payable_consultant", "طلبکاری به مشاور"
        PAYABLE_OFFICE = "payable_office", "طلبکاری به بنگاه"
        PAYABLE_MANAGER = "payable_manager", "طلبکاری به مدیر بنگاه"
        REVENUE_COMMISSION = "revenue_commission", "درآمد کمیسیون"
        EXPENSE_CONSULTANT_SHARE = "expense_consultant_share", "هزینه سهم مشاور"
        EXPENSE_MANAGER_SHARE = "expense_manager_share", "هزینه سهم مدیر"
        CASH_BANK = "cash_bank", "نقد و بانک"
        OTHER = "other", "سایر"

    name = models.CharField(max_length=255, verbose_name="نام حساب")
    code = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="کد حساب",
        help_text="کد یکتا برای شناسایی حساب",
    )
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        verbose_name="نوع حساب",
    )
    category = models.CharField(
        max_length=50,
        choices=AccountCategory.choices,
        default=AccountCategory.OTHER,
        verbose_name="دسته حساب",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="حساب والد",
    )
    description = models.TextField(blank=True, default="", verbose_name="توضیحات")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "حساب"
        verbose_name_plural = "حساب‌ها"
        ordering = ("code", "name")

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_balance(self):
        """محاسبه مانده حساب: بدهکار - بستانکار"""
        debit_total = self.entries.aggregate(total=Sum("debit", filter=Q(debit__gt=0)))[
            "total"
        ] or Decimal("0")
        credit_total = self.entries.aggregate(
            total=Sum("credit", filter=Q(credit__gt=0))
        )["total"] or Decimal("0")

        # برای حساب‌های دارایی و هزینه: بدهکار - بستانکار
        # برای حساب‌های بدهی و درآمد: بستانکار - بدهکار
        if self.account_type in (
            Account.AccountType.ASSET,
            Account.AccountType.EXPENSE,
        ):
            return debit_total - credit_total
        else:
            return credit_total - debit_total


class AccountingTransaction(models.Model):
    """
    تراکنش حسابداری: گروهی از ثبت‌های دفتری که باید همیشه متعادل باشند
    """

    description = models.TextField(verbose_name="شرح تراکنش")
    date = models.DateField(verbose_name="تاریخ تراکنش", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تراکنش حسابداری"
        verbose_name_plural = "تراکنش‌های حسابداری"
        ordering = ("-date", "-created_at")

    def __str__(self):
        return f"تراکنش #{self.id} - {self.date}"

    def is_balanced(self):
        """بررسی تعادل تراکنش: مجموع بدهکار = مجموع بستانکار"""
        totals = self.entries.aggregate(
            total_debit=Sum("debit"), total_credit=Sum("credit")
        )
        debit_total = totals["total_debit"] or Decimal("0")
        credit_total = totals["total_credit"] or Decimal("0")
        return debit_total == credit_total

    def get_total_debit(self):
        """مجموع بدهکار"""
        return self.entries.aggregate(total=Sum("debit"))["total"] or Decimal("0")

    def get_total_credit(self):
        """مجموع بستانکار"""
        return self.entries.aggregate(total=Sum("credit"))["total"] or Decimal("0")


class AccountEntry(models.Model):
    """
    ثبت دفتری: یک بدهکار یا بستانکار در یک حساب
    """

    transaction = models.ForeignKey(
        AccountingTransaction,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="تراکنش",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="entries",
        verbose_name="حساب",
    )
    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="بدهکار",
        help_text="مبلغ بدهکار (برای حساب‌های دارایی و هزینه)",
    )
    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="بستانکار",
        help_text="مبلغ بستانکار (برای حساب‌های بدهی و درآمد)",
    )
    description = models.TextField(blank=True, default="", verbose_name="شرح")
    counterpart_entry = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="counterpart_reverses",
        verbose_name="ثبت طرف مقابل",
        help_text="ثبت دفتری طرف مقابل در همان تراکنش (مثلاً طلب مشتری ↔ درآمد کمیسیون)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ثبت دفتری"
        verbose_name_plural = "ثبت‌های دفتری"
        ordering = ("transaction", "id")

    def __str__(self):
        return f"{self.account.name} - بدهکار: {self.debit}, بستانکار: {self.credit}"

    def save(self, *args, **kwargs):
        """ذخیره با اعتبارسنجی"""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """اعتبارسنجی: هر ثبت باید یا بدهکار یا بستانکار داشته باشد، نه هر دو"""
        from django.core.exceptions import ValidationError

        if self.debit > 0 and self.credit > 0:
            raise ValidationError(
                "یک ثبت نمی‌تواند هم بدهکار و هم بستانکار داشته باشد."
            )
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("یک ثبت باید حداقل یک بدهکار یا بستانکار داشته باشد.")


class DealFinance(models.Model):
    """
    پل ارتباطی بین معامله املاک و تراکنش حسابداری.
    """

    deal = models.OneToOneField(
        "transactions.Deals", on_delete=models.CASCADE, related_name="finance_details"
    )

    # تراکنش حسابداری اصلی که درآمد کمیسیون را ثبت می‌کند
    income_transaction = models.OneToOneField(
        AccountingTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deal_finance",
        verbose_name="تراکنش درآمد",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "اطلاعات مالی معامله"
        verbose_name_plural = "اطلاعات مالی معاملات"

    def __str__(self):
        return f"اطلاعات مالی معامله #{self.deal.id}"


class AccountingDocument(models.Model):
    """
    سند حسابداری: برای مدیریت شماره سند، نوع سند و ارتباط با تراکنش و معامله.
    """

    class DocType(models.TextChoices):
        JOURNAL = "journal", "سند روزنامه"
        RECEIPT = "receipt", "سند دریافت"
        PAYMENT = "payment", "سند پرداخت"
        COMMISSION = "commission", "سند کمیسیون معامله"
        TRANSFER = "transfer", "سند انتقال"
        OTHER = "other", "سند متفرقه"

    doc_type = models.CharField(
        max_length=20,
        choices=DocType.choices,
        default=DocType.JOURNAL,
        verbose_name="نوع سند",
    )
    number = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="شماره سند",
        db_index=True,
    )
    date = models.DateField(verbose_name="تاریخ سند")
    description = models.TextField(blank=True, default="", verbose_name="شرح")
    transaction = models.OneToOneField(
        AccountingTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_document",
        verbose_name="تراکنش حسابداری",
    )
    deal = models.ForeignKey(
        "transactions.Deals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_documents",
        verbose_name="معامله",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سند حسابداری"
        verbose_name_plural = "اسناد حسابداری"
        ordering = ("-date", "-created_at")

    def __str__(self):
        num = self.number or f"#{self.id}"
        return f"{self.get_doc_type_display()} {num} ({self.date})"


class AccountPayment(models.Model):
    """
    ثبت واریز/برداشت برای یک حساب خاص در قالب یک تراکنش حسابداری جداگانه.
    هر پرداخت به یک سند (Commission/Receipt/Payment) و یک حساب مرتبط می‌شود.
    """

    class Direction(models.TextChoices):
        RECEIVE = "receive", "دریافت از طرف حساب"
        PAY = "pay", "پرداخت به طرف حساب"

    document = models.ForeignKey(
        AccountingDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="سند مرتبط",
    )
    deal = models.ForeignKey(
        "transactions.Deals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_payments",
        verbose_name="معامله",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="حساب طرف مقابل",
    )
    transaction = models.OneToOneField(
        AccountingTransaction,
        on_delete=models.CASCADE,
        related_name="account_payment",
        verbose_name="تراکنش حسابداری",
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        verbose_name="نوع عملیات",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="مبلغ (ریال)",
    )
    date = models.DateField(verbose_name="تاریخ پرداخت/دریافت")
    method = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="روش پرداخت/دریافت",
        help_text="مثلاً نقد، کارت، حواله بانکی و ...",
    )
    description = models.TextField(blank=True, default="", verbose_name="توضیحات")
    receipt_file = models.FileField(
        upload_to=payment_receipt_upload_to,
        blank=True,
        null=True,
        verbose_name="ضمیمه / تصویر رسید",
        help_text="عکس یا فایل رسید پرداخت/دریافت (اختیاری)",
    )
    created_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_account_payments",
        verbose_name="ثبت‌کننده",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "پرداخت/دریافت حساب"
        verbose_name_plural = "پرداخت‌ها و دریافت‌های حساب‌ها"
        ordering = ("-date", "-created_at")

    def __str__(self):
        return f"{self.get_direction_display()} {self.amount} برای حساب {self.account}"


class PendingDealPayment(models.Model):
    """
    تراکنش پیشنهادی توسط مشاور برای حساب‌های مشتری؛ پس از تایید اپراتور/مدیر به دفتر اعمال می‌شود.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار تایید"
        APPROVED = "approved", "تایید شده"
        REJECTED = "rejected", "رد شده"

    deal = models.ForeignKey(
        "transactions.Deals",
        on_delete=models.CASCADE,
        related_name="pending_payments",
        verbose_name="معامله",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="pending_deal_payments",
        verbose_name="حساب",
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="مبلغ (ریال)",
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    direction = models.CharField(
        max_length=10,
        choices=AccountPayment.Direction.choices,
        verbose_name="نوع",
    )
    date = models.DateField(verbose_name="تاریخ پرداخت/دریافت")
    method = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="روش پرداخت/دریافت",
    )
    description = models.TextField(blank=True, default="", verbose_name="توضیحات")
    receipt_file = models.FileField(
        upload_to=pending_payment_receipt_upload_to,
        blank=True,
        null=True,
        verbose_name="ضمیمه رسید",
    )
    created_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_pending_deal_payments",
        verbose_name="ثبت‌کننده (مشاور)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="وضعیت",
    )
    reviewed_by = models.ForeignKey(
        "users.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_pending_deal_payments",
        verbose_name="تایید/رد توسط",
    )
    reviewed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="تاریخ تایید/رد"
    )
    rejection_reason = models.TextField(blank=True, default="", verbose_name="علت رد")
    # پس از تایید، تراکنش واقعی ساخته می‌شود و این رکورد به آن لینک می‌شود (اختیاری)
    account_payment = models.OneToOneField(
        AccountPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_source",
        verbose_name="تراکنش اعمال‌شده",
    )

    class Meta:
        verbose_name = "تراکنش در انتظار تایید"
        verbose_name_plural = "تراکنش‌های در انتظار تایید"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_direction_display()} {self.amount} — {self.get_status_display()}"
