from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from users.models import Consultant

from .models import (
    Client,
    CommissionSplit,
    DealClientCommission,
    DealConsultantApproval,
    DealContract,
    DealProperty,
    Deals,
    Office,
    TransactionType,
)


class TransactionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionType
        fields = ["name"]


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "name",
            "father_name",
            "national_id",
            "birth_date",
            "city_of_issuance",
            "phone",
        ]


class OfficeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Office
        fields = ["name"]


class DealPropertySerializer(serializers.ModelSerializer):
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


class DealsListSerializer(serializers.ModelSerializer):
    type = TransactionTypeSerializer()
    latest_contract_id = serializers.SerializerMethodField()
    creator = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    pending_my_approval = serializers.SerializerMethodField()

    def get_creator(self, obj):
        if not obj.created_by:
            return ""
        user = obj.created_by
        name = (user.get_full_name() or "").strip()
        return name or user.username

    def get_pending_my_approval(self, obj):
        """برای مشاور: True اگر معامله در انتظار تایید مشاور و نظر این مشاور هنوز ثبت نشده."""
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_consultant", False):
            return False
        if obj.status != "consultant_pending":
            return False
        consultant = getattr(request.user, "consultant_profile", None)
        if not consultant:
            return False
        approval = DealConsultantApproval.objects.filter(
            deal=obj, consultant=consultant
        ).first()
        return (
            approval is not None
            and approval.status == DealConsultantApproval.ApprovalStatus.PENDING
        )

    class Meta:
        model = Deals
        fields = [
            "id",
            "title",
            "type",
            "status",
            "status_display",
            "agreement_date",
            "office_date",
            "date",
            "created_at",
            "latest_contract_id",
            "creator",
            "pending_my_approval",
        ]

    def get_latest_contract_id(self, obj):
        contract = obj.contracts.order_by("-created_at").first()
        return contract.pk if contract else None


class DealClientCommissionSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = DealClientCommission
        fields = [
            "id",
            "client",
            "client_name",
            "role",
            "role_display",
            "amount",
            "description",
        ]
        read_only_fields = ["id"]


class DealsSerializer(serializers.ModelSerializer):
    property_details = DealPropertySerializer(required=False, allow_null=True)

    class Meta:
        model = Deals
        fields = [
            "id",
            "title",
            "type",
            "amount",
            "agreement_date",
            "office_date",
            "base_price",
            "overpayment",
            "overpayment_received",
            "deposit_amount",
            "rent_amount",
            "buyers",
            "sellers",
            "consultants",
            "date",
            "status",
            "property_details",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "status": {"required": False},
            "agreement_date": {"required": False, "allow_null": True},
            "office_date": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        buyers = attrs.get("buyers")
        sellers = attrs.get("sellers")
        instance = self.instance
        if instance:
            buyer_ids = {
                c.pk for c in (buyers if buyers is not None else instance.buyers.all())
            }
            seller_ids = {
                c.pk
                for c in (sellers if sellers is not None else instance.sellers.all())
            }
        else:
            buyer_ids = {c.pk for c in (buyers or [])}
            seller_ids = {c.pk for c in (sellers or [])}
        if buyer_ids & seller_ids:
            raise serializers.ValidationError(
                "یک مشتری نمی\u200cتواند هم\u200cزمان فروشنده و خریدار باشد."
            )
        return attrs

    def create(self, validated_data):
        buyers = validated_data.pop("buyers", [])
        sellers = validated_data.pop("sellers", [])
        consultants = validated_data.pop("consultants", [])
        property_details = validated_data.pop("property_details", None)

        user = self.context["request"].user
        office = user.office if hasattr(user, "office") else None

        validated_data["created_by"] = user
        validated_data["office"] = office
        if not validated_data.get("date"):
            validated_data["date"] = timezone.localdate().strftime("%Y/%m/%d")

        with transaction.atomic():
            deal = Deals.objects.create(**validated_data)

            if buyers:
                deal.buyers.set(buyers)
            if sellers:
                deal.sellers.set(sellers)
            if consultants:
                deal.consultants.set(consultants)
            if property_details:
                DealProperty.objects.create(deal=deal, **property_details)

        return deal

    def update(self, instance, validated_data):
        buyers = validated_data.pop("buyers", None)
        sellers = validated_data.pop("sellers", None)
        consultants = validated_data.pop("consultants", None)
        property_details = validated_data.pop("property_details", None)
        new_status = validated_data.pop("status", None)

        if new_status is not None:
            if new_status == "pending" and instance.status in (
                "init",
                "consultant_pending",
            ):
                instance.status = new_status
            elif new_status != instance.status and new_status != "pending":
                instance.status = new_status

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        if buyers is not None:
            instance.buyers.set(buyers)
        if sellers is not None:
            instance.sellers.set(sellers)
        if consultants is not None:
            instance.consultants.set(consultants)
        if property_details is not None:
            DealProperty.objects.update_or_create(
                deal=instance, defaults=property_details
            )

        return instance


class CommissionSplitSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionSplit
        fields = ["deal", "role", "percentage", "amount"]
        extra_kwargs = {
            "deal": {"required": False},
            "role": {"required": False},
            "percentage": {"required": False},
            "amount": {"required": False, "read_only": True},
        }

    def create(self, validated_data):
        if "percentage" in validated_data and "deal" in validated_data:
            deal = validated_data["deal"]
            percentage = validated_data["percentage"]

            total_value = (
                deal.overpayment_received
                if hasattr(deal, "overpayment_received")
                else deal.amount
            )

            validated_data["amount"] = (total_value * percentage) / 100

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "percentage" in validated_data:
            percentage = validated_data["percentage"]

            deal = validated_data.get("deal", instance.deal)

            if deal:
                total_value = (
                    deal.overpayment_received
                    if hasattr(deal, "overpayment_received")
                    else deal.amount
                )
                validated_data["amount"] = (total_value * percentage) / 100

        return super().update(instance, validated_data)


class ClientDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "father_name",
            "national_id",
            "birth_date",
            "city_of_issuance",
            "phone",
        ]


class ConsultantMinSerializer(serializers.ModelSerializer):
    """فقط id و name برای نمایش در جزئیات معامله."""

    class Meta:
        model = Consultant
        fields = ["id", "name"]


class TransactionTypeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionType
        fields = ["id", "name"]


class CommissionSplitDetailSerializer(serializers.ModelSerializer):
    consultant_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = CommissionSplit
        fields = [
            "id",
            "consultant_name",
            "role",
            "role_display",
            "percentage",
            "amount",
        ]

    def get_consultant_name(self, obj):
        return obj.consultant.name if obj.consultant else None


class DealConsultantApprovalSerializer(serializers.ModelSerializer):
    consultant_name = serializers.CharField(source="consultant.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DealConsultantApproval
        fields = [
            "id",
            "consultant",
            "consultant_name",
            "status",
            "status_display",
            "suggested_amount",
            "note",
            "responded_at",
        ]


class DealContractSerializer(serializers.ModelSerializer):
    template_title = serializers.CharField(source="template.title", read_only=True)

    class Meta:
        model = DealContract
        fields = ["id", "template_title", "is_finalized", "created_at"]


class ContractListSerializer(serializers.ModelSerializer):
    """برای لیست مبایعه‌نامه‌ها در داشبورد."""

    template_title = serializers.SerializerMethodField()
    deal_id = serializers.IntegerField(source="deal.id", read_only=True)
    deal_title = serializers.SerializerMethodField()
    deal_type = serializers.CharField(source="deal.type.name", read_only=True)

    class Meta:
        model = DealContract
        fields = [
            "id",
            "deal_id",
            "deal_title",
            "deal_type",
            "template_title",
            "is_finalized",
            "created_at",
        ]

    def get_template_title(self, obj):
        return obj.template.title if obj.template else ""

    def get_deal_title(self, obj):
        return (obj.deal.title or "").strip() if obj.deal else ""


class DealDetailSerializer(serializers.ModelSerializer):
    type = TransactionTypeSerializer(read_only=True)
    buyers = ClientDetailSerializer(many=True, read_only=True)
    sellers = ClientDetailSerializer(many=True, read_only=True)
    consultants = ConsultantMinSerializer(many=True, read_only=True)
    property_details = DealPropertySerializer(read_only=True)

    splits = CommissionSplitDetailSerializer(many=True, read_only=True)
    client_commissions = DealClientCommissionSerializer(many=True, read_only=True)
    contracts = DealContractSerializer(many=True, read_only=True)
    consultant_approvals = DealConsultantApprovalSerializer(many=True, read_only=True)
    my_consultant_approval = serializers.SerializerMethodField()

    status = serializers.CharField(source="get_status_display", read_only=True)
    status_code = serializers.CharField(source="status", read_only=True)
    creator = serializers.SerializerMethodField()

    def get_creator(self, obj):
        if not obj.created_by:
            return ""
        user = obj.created_by
        name = (user.get_full_name() or "").strip()
        return name or user.username

    def get_my_consultant_approval(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request.user, "consultant_profile", None):
            return None
        consultant = request.user.consultant_profile
        approval = obj.consultant_approvals.filter(consultant=consultant).first()
        if not approval:
            return None
        return DealConsultantApprovalSerializer(approval).data

    class Meta:
        model = Deals
        fields = [
            "id",
            "title",
            "status",
            "status_code",
            "my_consultant_approval",
            "type",
            "amount",
            "agreement_date",
            "office_date",
            "base_price",
            "overpayment",
            "overpayment_received",
            "deposit_amount",
            "rent_amount",
            "property_details",
            "buyers",
            "sellers",
            "consultants",
            "creator",
            "description",
            "date",
            "created_at",
            "rejection_reason",
            "splits",
            "client_commissions",
            "consultant_approvals",
            "contracts",
        ]
