from django.contrib import admin

from .models import (
    Account,
    AccountEntry,
    AccountingDocument,
    AccountingTransaction,
    AccountPayment,
    DealFinance,
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "category", "is_active", "parent")
    list_filter = ("account_type", "category", "is_active")
    search_fields = ("code", "name", "description")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("parent",)
    ordering = ("code",)


@admin.register(AccountingTransaction)
class AccountingTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "description", "created_at")
    list_filter = ("date", "created_at")
    search_fields = ("description",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")


@admin.register(AccountEntry)
class AccountEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "transaction",
        "account",
        "debit",
        "credit",
        "counterpart_entry",
        "description",
        "created_at",
    )
    list_filter = ("created_at", "account__account_type")
    search_fields = ("account__name", "account__code", "description")
    readonly_fields = ("created_at",)
    raw_id_fields = ("transaction", "account", "counterpart_entry")
    ordering = ("-created_at",)


@admin.register(AccountingDocument)
class AccountingDocumentAdmin(admin.ModelAdmin):
    list_display = ("number", "doc_type", "date", "deal", "transaction", "created_at")
    list_filter = ("doc_type", "date", "created_at")
    search_fields = ("number", "description")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("transaction", "deal")
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")


@admin.register(DealFinance)
class DealFinanceAdmin(admin.ModelAdmin):
    list_display = ("deal", "income_transaction", "created_at", "updated_at")
    list_filter = ("created_at",)
    search_fields = ("deal__id",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("deal", "income_transaction")
    ordering = ("-created_at",)


@admin.register(AccountPayment)
class AccountPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "date",
        "direction",
        "amount",
        "account",
        "document",
        "deal",
        "receipt_file",
    )
    list_filter = ("direction", "date", "created_at")
    search_fields = ("account__name", "account__code", "document__number", "deal__id")
    readonly_fields = ("created_at",)
    raw_id_fields = ("account", "document", "deal", "transaction", "created_by")
    date_hierarchy = "date"
    ordering = ("-date", "-created_at")
