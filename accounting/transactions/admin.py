from django.contrib import admin

from .models import (
    Client,
    CommissionSplit,
    ContractTemplate,
    DealClientCommission,
    DealContract,
    Deals,
    TransactionType,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "father_name",
        "national_id",
        "birth_date",
        "city_of_issuance",
        "phone",
        "created_at",
    )
    search_fields = ("name", "father_name", "national_id", "phone", "city_of_issuance")
    ordering = ("-created_at",)


@admin.register(TransactionType)
class TransactionTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_editable = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Deals)
class DealsAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "type",
        "amount",
        "office",
        "created_by",
        "get_buyer_count",
        "get_seller_count",
    )
    list_filter = ("status", "type", "office", "created_by")
    search_fields = ("title", "type__name")
    ordering = ("date",)

    def get_buyer_count(self, obj):
        return obj.buyers.count()

    get_buyer_count.short_description = "تعداد خریدار"

    def get_seller_count(self, obj):
        return obj.sellers.count()

    get_seller_count.short_description = "تعداد فروشنده"


@admin.register(DealClientCommission)
class DealClientCommissionAdmin(admin.ModelAdmin):
    list_display = ("deal", "client", "role", "amount", "description")
    list_filter = ("role",)
    search_fields = ("deal__title", "client__name", "description")
    ordering = ("-deal__created_at",)
    raw_id_fields = ("deal", "client")


@admin.register(CommissionSplit)
class CommissionSplitAdmin(admin.ModelAdmin):
    list_display = ("deal", "role", "percentage", "amount")
    list_filter = ("role",)
    search_fields = ("deal__title",)
    ordering = ("-deal__date",)


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ["title", "transaction_type", "participant_mode", "is_default"]
    list_filter = ["participant_mode", "transaction_type"]

    search_fields = ("title", "body")


@admin.register(DealContract)
class DealContractAdmin(admin.ModelAdmin):
    list_display = (
        "deal",
        "get_template_title",
        "is_finalized",
        "created_at",
        "has_header",
    )

    list_filter = ("is_finalized", "created_at")

    search_fields = ("deal__id", "deal__title", "content")

    raw_id_fields = ("deal",)

    def get_template_title(self, obj):
        return obj.template.title if obj.template else "بدون الگو"

    get_template_title.short_description = "الگو"
