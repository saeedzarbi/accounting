from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import Http404
from django.views.generic import TemplateView
from drf_yasg.utils import swagger_auto_schema
from finance.models import DealFinance
from finance.services import create_deal_ledger_entry
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from transactions.models import CommissionSplit
from users.models import Consultant

from .models import (
    Client,
    DealClientCommission,
    DealContract,
    Deals,
    TransactionType,
)
from .pagination import CustomPagination
from .serializers import (
    CommissionSplitSerializer,
    ContractListSerializer,
    DealDetailSerializer,
    DealsListSerializer,
    DealsSerializer,
)


class DealsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        office = getattr(user, "office", None)

        if office:
            deals = (
                Deals.objects.filter(office=office)
                .select_related("created_by")
                .prefetch_related("contracts")
                .order_by("-created_at")
            )
        else:
            deals = Deals.objects.none()

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(deals, request)

        serializer = DealsListSerializer(result_page, many=True)

        return paginator.get_paginated_response(serializer.data)


class ContractListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        office = getattr(user, "office", None)
        if not office:
            qs = DealContract.objects.none()
        else:
            qs = (
                DealContract.objects.filter(deal__office=office)
                .select_related("deal", "deal__type", "template")
                .order_by("-created_at")
            )
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(qs, request)
        serializer = ContractListSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)


# class DealsListPageView(LoginRequiredMixin, TemplateView):
#     template_name = "transactions/deals_list.html"


class DealCreatePageView(LoginRequiredMixin, TemplateView):
    template_name = "transactions/deal_create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["transaction_types"] = TransactionType.objects.all()
        return context


class DealDetailView(RetrieveAPIView):
    serializer_class = DealDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):

        user = self.request.user
        if user.office:
            return Deals.objects.filter(office=user.office).prefetch_related(
                "buyers",
                "sellers",
                "splits",
                "splits__consultant",
                "client_commissions",
                "client_commissions__client",
                "contracts",
                "consultants",
            )
        return Deals.objects.none()

    def get_object(self):

        try:
            return super().get_object()
        except Http404 as err:
            raise Http404(
                "معامله مورد نظر یافت نشد یا شما دسترسی به آن ندارید."
            ) from err


class ConsultantListByOfficeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        office = user.office

        if office:
            consultants = Consultant.objects.filter(office=office)
        else:
            consultants = Consultant.objects.none()

        consultant_data = consultants.values("id", "name")

        return Response(consultant_data)


class ClientListByOfficeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        office = user.office

        if office:
            clients = Client.objects.filter(office=office)
        else:
            clients = Client.objects.none()

        client_list = list(clients.values("id", "name", "national_id"))
        return Response(client_list)

    def post(self, request, *args, **kwargs):
        user = request.user
        office = user.office

        if not office:
            return Response(
                {"error": "کاربر جاری به هیچ دفتری (Office) متصل نیست."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = request.data.get("name")
        phone = request.data.get("phone_number")
        father_name = request.data.get("father_name") or None
        national_id = request.data.get("national_id") or None
        birth_date = request.data.get("birth_date") or None
        city_of_issuance = request.data.get("city_of_issuance") or None

        if not name:
            return Response(
                {"error": "وارد کردن نام (name) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if national_id and str(national_id).strip():
            national_id = str(national_id).strip()
            qs = Client.objects.filter(national_id=national_id)
            if office:
                qs = qs.filter(office=office)
            existing = qs.first()
            if existing:
                return Response(
                    {
                        "error": f"مشتری با این کد ملی با نام «{existing.name}» وجود دارد."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif national_id is not None:
            national_id = str(national_id).strip() or None

        try:
            new_client = Client.objects.create(
                name=name,
                phone=phone,
                father_name=father_name,
                national_id=national_id,
                birth_date=birth_date,
                city_of_issuance=city_of_issuance,
                office=office,
            )

            return Response(
                {
                    "id": new_client.id,
                    "name": new_client.name,
                    "phone": new_client.phone,
                    "father_name": new_client.father_name,
                    "national_id": new_client.national_id,
                    "birth_date": new_client.birth_date,
                    "city_of_issuance": new_client.city_of_issuance,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CreateDealView(APIView):
    @swagger_auto_schema(request_body=DealsSerializer, responses={201: DealsSerializer})
    def post(self, request, *args, **kwargs):
        serializer = DealsSerializer(data=request.data, context={"request": request})

        if serializer.is_valid():
            deal = serializer.save()

            return Response(DealsSerializer(deal).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateDealView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        deal_id = kwargs.get("deal_id")
        user = request.user
        office = user.office

        try:
            deal = Deals.objects.get(id=deal_id, office=office)
        except Deals.DoesNotExist:
            return Response(
                {"detail": "Deal not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if deal.status == "approved":
            return Response(
                {"detail": 'Only deals in "init" and "pending" status can be updated.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if deal.office != request.user.office:
            return Response(
                {"detail": "You cannot update deals from other offices."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = DealsSerializer(
            deal, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            updated_deal = serializer.save()
            return Response(DealsSerializer(updated_deal).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteDealView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        deal_id = kwargs.get("deal_id")
        user = request.user
        office = user.office

        try:
            deal = Deals.objects.get(id=deal_id, office=office)
        except Deals.DoesNotExist:
            return Response(
                {"detail": "Deal not found"}, status=status.HTTP_404_NOT_FOUND
            )

        if deal.status != "init":
            return Response(
                {"detail": 'Only deals in "init" status can be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deal.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DealClientCommissionBulkView(APIView):

    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        deal_id = kwargs.get("deal_id")
        user = request.user
        office = getattr(user, "office", None)
        try:
            deal = Deals.objects.get(id=deal_id, office=office)
        except Deals.DoesNotExist:
            return Response(
                {"detail": "معامله یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        items = request.data.get("client_commissions") or []
        if not isinstance(items, list):
            return Response(
                {"client_commissions": "باید آرایه باشد."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            DealClientCommission.objects.filter(deal=deal).delete()
            for item in items:
                client_id = item.get("client_id")
                role = item.get("role")
                amount = item.get("amount")
                description = (item.get("description") or "").strip()
                if not client_id or not role:
                    continue
                if role not in ("buyer", "seller"):
                    continue
                try:
                    DealClientCommission.objects.create(
                        deal=deal,
                        client_id=client_id,
                        role=role,
                        amount=amount or 0,
                        description=description,
                    )
                except Exception:
                    pass

        commissions = list(
            deal.client_commissions.values(
                "id", "client_id", "role", "amount", "description"
            )
        )
        return Response({"client_commissions": commissions})


class CommissionSplitBulkView(APIView):
    """جایگزینی کل سهم‌های کمیسیون (دفتر، مدیر، مشاوران) برای یک معامله."""

    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        deal_id = kwargs.get("deal_id")
        user = request.user
        office = getattr(user, "office", None)
        try:
            deal = Deals.objects.get(id=deal_id, office=office)
        except Deals.DoesNotExist:
            return Response(
                {"detail": "معامله یافت نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        items = request.data.get("splits") or []
        if not isinstance(items, list):
            return Response(
                {"splits": "باید آرایه باشد."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            CommissionSplit.objects.filter(deal=deal).delete()
            for item in items:
                role = item.get("role")
                percentage = item.get("percentage")
                amount = item.get("amount")
                consultant_id = item.get("consultant_id")
                if role not in ("office", "manager", "consultant"):
                    continue
                if role == "consultant" and not consultant_id:
                    continue
                try:
                    percentage_value = (
                        float(percentage) if percentage is not None else None
                    )
                except (TypeError, ValueError):
                    percentage_value = None
                try:
                    amount_value = float(amount) if amount is not None else None
                except (TypeError, ValueError):
                    amount_value = None
                use_amount = amount_value is not None and amount_value > 0
                use_percentage = percentage_value is not None and percentage_value > 0
                if not (use_amount or use_percentage):
                    continue
                try:
                    CommissionSplit.objects.create(
                        deal=deal,
                        role=role,
                        percentage=None if use_amount else percentage_value,
                        amount=amount_value if use_amount else None,
                        consultant_id=consultant_id if role == "consultant" else None,
                    )
                except Exception:
                    pass

        from .serializers import CommissionSplitSerializer

        splits = CommissionSplit.objects.filter(deal=deal)
        return Response({"splits": CommissionSplitSerializer(splits, many=True).data})


class CreateCommissionSplitView(APIView):
    @swagger_auto_schema(
        request_body=CommissionSplitSerializer,
        responses={201: CommissionSplitSerializer},
        operation_description="ایجاد کمیسیون. تمام فیلدها اختیاری هستند. "
        "اگر درصد (percentage) و معامله (deal) وارد شوند، مبلغ (amount) خودکار محاسبه می‌شود.",
    )
    def post(self, request, *args, **kwargs):
        serializer = CommissionSplitSerializer(data=request.data)
        if serializer.is_valid():
            commission_split = serializer.save()
            return Response(
                CommissionSplitSerializer(commission_split).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateCommissionSplitView(APIView):
    @swagger_auto_schema(
        request_body=CommissionSplitSerializer,
        responses={200: CommissionSplitSerializer},
        operation_description="آپدیت درصد کمیسیون برای یک معامله خاص. "
        "شما باید درصد کمیسیون (percentage) را ارسال کنید. "
        "مقدار کمیسیون (amount) به صورت خودکار بر اساس درصد جدید محاسبه خواهد شد.",
    )
    def put(self, request, *args, **kwargs):
        commission_split_id = kwargs.get("commission_split_id")

        try:
            commission_split = CommissionSplit.objects.get(id=commission_split_id)
        except CommissionSplit.DoesNotExist:
            return Response(
                {"detail": "Commission Split not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CommissionSplitSerializer(
            commission_split, data=request.data, partial=True
        )
        if serializer.is_valid():
            commission_split = serializer.save()
            return Response(CommissionSplitSerializer(commission_split).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def _user_can_approve_reject(user):
    return getattr(user, "is_office_manager", False)


class ApproveDealView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        user = request.user
        if not _user_can_approve_reject(user):
            return Response(
                {"message": "فقط مدیر بنگاه می‌تواند معامله را تایید کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        deal_id = kwargs.get("deal_id")
        office = user.office
        try:
            deal = Deals.objects.get(id=deal_id, status="pending", office=office)
        except Deals.DoesNotExist:
            return Response(
                {"message": "معامله یافت نشد یا در وضعیت در انتظار تایید نیست."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with transaction.atomic():
                deal.status = "approved"
                deal.rejection_reason = ""
                deal.save()

                if not DealFinance.objects.filter(deal=deal).exists():
                    create_deal_ledger_entry(deal)
        except Exception as exc:
            return Response(
                {
                    "message": "خطا در ثبت سند حسابداری برای این معامله.",
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "وضعیت معامله به «تایید شده» به‌روزرسانی شد و سند حسابداری کمیسیون ثبت شد."
            },
            status=status.HTTP_200_OK,
        )


class RejectDealView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if not _user_can_approve_reject(user):
            return Response(
                {"message": "فقط مدیر بنگاه می‌تواند معامله را رد کند."},
                status=status.HTTP_403_FORBIDDEN,
            )
        deal_id = kwargs.get("deal_id")
        office = user.office
        try:
            deal = Deals.objects.get(id=deal_id, status="pending", office=office)
        except Deals.DoesNotExist:
            return Response(
                {"message": "معامله یافت نشد یا در وضعیت در انتظار تایید نیست."},
                status=status.HTTP_404_NOT_FOUND,
            )
        reason = (request.data.get("rejection_reason") or "").strip()
        deal.status = "rejected"
        deal.rejection_reason = reason
        deal.save()
        return Response(
            {"message": "معامله رد شد.", "rejection_reason": deal.rejection_reason},
            status=status.HTTP_200_OK,
        )
