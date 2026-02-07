import json
import os
from datetime import date as date_type
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView
from transactions.models import Deals

from .models import (
    Account,
    AccountEntry,
    AccountingDocument,
    AccountPayment,
    DealFinance,
)
from .services import create_account_payment, repair_deal_ledger_revenue


class DealAccountsView(LoginRequiredMixin, TemplateView):
    """صفحه نمایش حساب‌های ساخته‌شده برای یک معامله (سند حسابداری کمیسیون)."""

    template_name = "finance/deal_accounts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deal_id = self.kwargs.get("deal_id")
        office = getattr(self.request.user, "office", None)

        deal = get_object_or_404(Deals, id=deal_id)
        if office and deal.office_id != office.id:
            raise Http404("معامله مربوط به این بنگاه نیست.")

        context["deal"] = deal
        context["transaction"] = None
        context["entries"] = []
        context["document"] = None

        try:
            finance = DealFinance.objects.select_related("income_transaction").get(
                deal=deal
            )
        except DealFinance.DoesNotExist:
            return context

        trx = finance.income_transaction
        repair_deal_ledger_revenue(deal, trx)
        context["transaction"] = trx
        context["document"] = AccountingDocument.objects.filter(
            deal=deal, transaction=trx
        ).first()

        entries_qs = (
            AccountEntry.objects.filter(transaction=trx)
            .select_related("account")
            .order_by("id")
        )

        payments_qs = (
            AccountPayment.objects.filter(deal=deal)
            .select_related("account")
            .order_by("-date", "-created_at")
        )

        payments_by_account = {}
        for p in payments_qs:
            code = getattr(p.account, "code", "") or ""
            if not code:
                continue
            receipt_url = ""
            if getattr(p, "receipt_file", None) and p.receipt_file:
                receipt_url = reverse(
                    "finance:serve-payment-receipt", kwargs={"payment_id": p.id}
                )
            payments_by_account.setdefault(code, []).append(
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y/%m/%d"),
                    "direction": p.get_direction_display(),
                    "direction_value": p.direction,
                    "amount": float(p.amount or 0),
                    "method": p.method or "",
                    "description": p.description or "",
                    "receipt_url": receipt_url,
                }
            )

        entries = []
        total_debit = 0
        total_credit = 0

        category_totals = {
            "receivable_client": {
                "label": "بدهی مشتریان به بنگاه",
                "debit": 0.0,
                "credit": 0.0,
            },
            "payable_client": {
                "label": "بدهی بنگاه به مشتریان",
                "debit": 0.0,
                "credit": 0.0,
            },
            "payable_consultant": {
                "label": "بدهی بنگاه به مشاوران",
                "debit": 0.0,
                "credit": 0.0,
            },
            "payable_manager": {
                "label": "بدهی بنگاه به مدیر دفتر",
                "debit": 0.0,
                "credit": 0.0,
            },
            "revenue_commission": {
                "label": "درآمد کمیسیون بنگاه",
                "debit": 0.0,
                "credit": 0.0,
            },
            "expense_consultant_share": {
                "label": "هزینه سهم مشاوران",
                "debit": 0.0,
                "credit": 0.0,
            },
            "expense_manager_share": {
                "label": "هزینه سهم مدیر دفتر",
                "debit": 0.0,
                "credit": 0.0,
            },
        }

        # فقط حساب‌هایی که طرف مستقیم دریافت/پرداخت هستند در لیست «ثبت تراکنش» می‌آیند؛
        # حساب‌های معادل (درآمد کمیسیون، هزینه سهم مشاور/مدیر) با همان تراکنش دوطرفه اعمال می‌شوند
        TRANSACTION_TARGET_CATEGORIES = (
            "receivable_client",
            "payable_client",
            "receivable_consultant",
            "payable_consultant",
            "receivable_manager",
            "payable_manager",
        )
        deal_accounts_list = []

        COUNTERPART_LABELS = {
            "receivable_client": "هم‌ارز با درآمد کمیسیون بنگاه",
            "payable_client": "هم‌ارز با بدهی بنگاه به مشتری",
            "receivable_consultant": "هم‌ارز با حساب بنگاه",
            "payable_consultant": "هم‌ارز با هزینه سهم مشاور",
            "receivable_manager": "هم‌ارز با حساب بنگاه",
            "payable_manager": "هم‌ارز با هزینه سهم مدیر دفتر",
            "revenue_commission": "هم‌ارز با بدهی مشتریان به بنگاه",
            "expense_consultant_share": "هم‌ارز با پرداختنی به مشاور",
            "expense_manager_share": "هم‌ارز با پرداختنی به مدیر دفتر",
            "cash_bank": "",
            "other": "",
        }
        ORDER_KEY = {
            "receivable_client": (0, 0),
            "payable_client": (0, 1),
            "revenue_commission": (0, 2),
            "receivable_consultant": (1, 0),
            "payable_consultant": (1, 1),
            "expense_consultant_share": (1, 2),
            "receivable_manager": (2, 0),
            "payable_manager": (2, 1),
            "expense_manager_share": (2, 2),
            "cash_bank": (3, 0),
            "other": (4, 0),
        }

        by_account = {}
        seen_account_ids_for_list = set()
        for entry in entries_qs:
            debit = float(entry.debit or 0)
            credit = float(entry.credit or 0)
            total_debit += debit
            total_credit += credit
            acc = entry.account
            category = getattr(acc, "category", None) or "other"
            if category in category_totals:
                category_totals[category]["debit"] += debit
                category_totals[category]["credit"] += credit

            if acc.id not in seen_account_ids_for_list:
                seen_account_ids_for_list.add(acc.id)
                if category in TRANSACTION_TARGET_CATEGORIES:
                    deal_accounts_list.append(
                        {"id": acc.id, "code": acc.code or "", "name": acc.name or ""}
                    )

            if acc.id not in by_account:
                kind_label = {
                    "receivable_client": "طلب از مشتری (بستانکاری)",
                    "payable_client": "بدهی بنگاه به مشتری",
                    "receivable_consultant": "طلب از مشاور",
                    "payable_consultant": "پرداختنی به مشاور",
                    "receivable_manager": "طلب از مدیر دفتر",
                    "payable_manager": "پرداختنی به مدیر دفتر",
                    "revenue_commission": "درآمد کمیسیون بنگاه",
                    "expense_consultant_share": "هزینه سهم مشاور",
                    "expense_manager_share": "هزینه سهم مدیر دفتر",
                    "cash_bank": "نقد و بانک",
                    "other": "سایر",
                }.get(category, "سایر")
                payments_list = payments_by_account.get(acc.code or "", [])
                by_account[acc.id] = {
                    "account_name": acc.name or "—",
                    "account_code": acc.code or "—",
                    "account_kind": kind_label,
                    "counterpart_label": COUNTERPART_LABELS.get(category, ""),
                    "debit": 0.0,
                    "credit": 0.0,
                    "has_payments": bool(payments_list),
                    "settled_amount": 0.0,
                    "remaining_amount": 0.0,
                    "order_key": ORDER_KEY.get(category, (4, 0)),
                    "_payments_list": payments_list,
                    "_category": category,
                }
            by_account[acc.id]["debit"] += debit
            by_account[acc.id]["credit"] += credit

        ledger_rows = []
        for _acc_id, b in by_account.items():
            payments_list = b.pop("_payments_list", [])
            category = b.pop("_category", "other")
            debit = b["debit"]
            credit = b["credit"]
            if debit > 0:
                settled = sum(
                    x["amount"]
                    for x in payments_list
                    if x.get("direction_value") == "receive"
                )
            else:
                settled = sum(
                    x["amount"]
                    for x in payments_list
                    if x.get("direction_value") == "pay"
                )
            balance = debit if debit > 0 else credit
            b["settled_amount"] = settled
            b["remaining_amount"] = max(0, balance - settled)
            ledger_rows.append(b)
        # اگر حساب درآمد کمیسیون بنگاه بستانکار نداشته باشد ولی طلب از مشتریان وجود داشته باشد،
        # معادل را از جمع بدهکار مشتریان استنتاج کن تا نمایش درست باشد (دادهٔ قدیمی یا ناهماهنگ)
        client_debit = (category_totals.get("receivable_client") or {}).get(
            "debit", 0
        ) or 0
        for row in ledger_rows:
            if row.get("account_kind") == "درآمد کمیسیون بنگاه" and (
                not row.get("credit") or row["credit"] == 0
            ):
                if client_debit > 0:
                    row["credit"] = client_debit
                    row["remaining_amount"] = max(
                        0, client_debit - row["settled_amount"]
                    )
        ledger_rows.sort(key=lambda r: (r["order_key"], r["account_code"]))

        # محاسبه مانده خالص برای خلاصه
        summary_items = []
        client_receivable_balance = 0.0
        for key, data in category_totals.items():
            if data["debit"] == 0 and data["credit"] == 0:
                continue
            label = data["label"]
            debit = data["debit"]
            credit = data["credit"]
            balance = debit - credit
            summary_items.append(
                {
                    "key": key,
                    "label": label,
                    "debit": debit,
                    "credit": credit,
                    "balance": balance,
                }
            )
            if key == "receivable_client":
                client_receivable_balance = balance

        context["entries"] = (
            entries  # برای سازگاری قدیم خالی می‌ماند یا همان ledger_rows
        )
        context["total_debit"] = total_debit
        context["total_credit"] = total_credit
        context["is_balanced"] = trx.is_balanced() if trx else False
        context["summary_items"] = summary_items
        context["client_receivable_balance"] = client_receivable_balance
        context["ledger_rows"] = ledger_rows
        context["sections"] = []  # دیگر استفاده نمی‌شود؛ یک جدول واحد
        context["payments_by_account_json"] = json.dumps(
            payments_by_account, cls=DjangoJSONEncoder, ensure_ascii=False
        )
        context["deal_accounts_list"] = deal_accounts_list
        context["deal_accounts_list_json"] = json.dumps(
            deal_accounts_list, cls=DjangoJSONEncoder, ensure_ascii=False
        )
        return context


class AccountingDocumentsListView(LoginRequiredMixin, ListView):
    model = AccountingDocument
    template_name = "finance/accounting_documents_list.html"
    context_object_name = "documents"
    paginate_by = 20

    def get_queryset(self):
        qs = AccountingDocument.objects.select_related("deal", "transaction").order_by(
            "-date", "-created_at"
        )
        office = getattr(self.request.user, "office", None)
        if office:
            qs = qs.filter(Q(deal__isnull=True) | Q(deal__office=office))
        return qs


class ServePaymentReceiptView(LoginRequiredMixin, View):
    """سرو فایل رسید پرداخت با بررسی دسترسی؛ در صورت نبود فایل 404 برگردانده می‌شود."""

    def get(self, request, payment_id):
        payment = get_object_or_404(
            AccountPayment.objects.select_related("deal"), id=payment_id
        )
        office = getattr(request.user, "office", None)
        if (
            payment.deal_id
            and office
            and payment.deal
            and payment.deal.office_id != office.id
        ):
            raise Http404("دسترسی به این رسید مجاز نیست.")
        if not payment.receipt_file:
            raise Http404("برای این تراکنش فایل رسید ثبت نشده است.")
        path = payment.receipt_file.path
        if not os.path.isfile(path):
            raise Http404("فایل رسید روی سرور یافت نشد.")
        return FileResponse(
            open(path, "rb"),
            as_attachment=False,
            filename=os.path.basename(path),
        )


class CreateDealAccountPaymentView(LoginRequiredMixin, View):
    """ثبت پرداخت/دریافت برای یکی از حساب‌های معامله (فقط POST)."""

    def post(self, request, deal_id):
        office = getattr(request.user, "office", None)
        deal = get_object_or_404(Deals, id=deal_id)
        if office and deal.office_id != office.id:
            return JsonResponse(
                {"success": False, "message": "دسترسی به این معامله مجاز نیست."},
                status=403,
            )

        try:
            finance = DealFinance.objects.select_related("income_transaction").get(
                deal=deal
            )
        except DealFinance.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "سند حسابداری این معامله یافت نشد."},
                status=404,
            )

        def _normalize_amount(value):
            if value is None:
                return None
            s = str(value).strip().replace(",", "").replace("٬", "").replace("،", "")
            try:
                return float(s) if s else None
            except ValueError:
                return None

        if request.content_type and "multipart/form-data" in (
            request.content_type or ""
        ):
            account_id = request.POST.get("account_id")
            amount = _normalize_amount(request.POST.get("amount"))
            direction = request.POST.get("direction")
            payment_date = request.POST.get("date")
            method = request.POST.get("method", "")
            description = request.POST.get("description", "")
            receipt_file = request.FILES.get("receipt")
        elif request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body)
                account_id = data.get("account_id")
                amount = _normalize_amount(data.get("amount"))
                direction = data.get("direction")
                payment_date = data.get("date")
                method = data.get("method", "")
                description = data.get("description", "")
                receipt_file = None
            except json.JSONDecodeError:
                return JsonResponse(
                    {"success": False, "message": "داده ارسالی نامعتبر است."},
                    status=400,
                )
        else:
            account_id = request.POST.get("account_id")
            amount = _normalize_amount(request.POST.get("amount"))
            direction = request.POST.get("direction")
            payment_date = request.POST.get("date")
            method = request.POST.get("method", "")
            description = request.POST.get("description", "")
            receipt_file = request.FILES.get("receipt") if request.FILES else None

        if not account_id:
            return JsonResponse(
                {"success": False, "message": "حساب را انتخاب کنید."},
                status=400,
            )
        if amount is None or amount <= 0:
            return JsonResponse(
                {"success": False, "message": "مبلغ باید بزرگ‌تر از صفر باشد."},
                status=400,
            )
        if direction not in (
            AccountPayment.Direction.RECEIVE,
            AccountPayment.Direction.PAY,
        ):
            return JsonResponse(
                {
                    "success": False,
                    "message": "نوع تراکنش (دریافت/پرداخت) را مشخص کنید.",
                },
                status=400,
            )

        trx = finance.income_transaction
        allowed_account_ids = set(
            AccountEntry.objects.filter(transaction=trx).values_list(
                "account_id", flat=True
            )
        )
        if int(account_id) not in allowed_account_ids:
            return JsonResponse(
                {"success": False, "message": "این حساب مربوط به این معامله نیست."},
                status=400,
            )

        account = get_object_or_404(Account, id=account_id)
        # ثبت تراکنش فقط برای حساب‌های طرف مستقیم (طلب/پرداختنی)؛ درآمد و هزینه بنگاه معادل آن‌ها هستند و جدا ثبت نمی‌شوند
        _transaction_target_categories = (
            "receivable_client",
            "payable_client",
            "receivable_consultant",
            "payable_consultant",
            "receivable_manager",
            "payable_manager",
        )
        if getattr(account, "category", None) not in _transaction_target_categories:
            return JsonResponse(
                {
                    "success": False,
                    "message": "ثبت تراکنش فقط برای حساب‌های طلب از مشتری/مشاور/مدیر یا پرداختنی به آن‌ها امکان‌پذیر است؛ حساب معادل (درآمد/هزینه بنگاه) به‌صورت خودکار اعمال می‌شود.",
                },
                status=400,
            )

        document = AccountingDocument.objects.filter(
            deal=deal, doc_type=AccountingDocument.DocType.COMMISSION
        ).first()

        # محاسبه مانده اولیه این حساب در سند کمیسیون (بدهکار / بستانکار)
        entries_for_account = AccountEntry.objects.filter(
            transaction=trx, account=account
        )
        entry_totals = entries_for_account.aggregate(
            total_debit=Sum("debit"), total_credit=Sum("credit")
        )
        orig_debit = entry_totals["total_debit"] or Decimal("0")
        orig_credit = entry_totals["total_credit"] or Decimal("0")

        # مبالغی که قبلاً برای این حساب و این معامله تسویه شده‌اند
        payments_for_account = AccountPayment.objects.filter(deal=deal, account=account)
        paid_receive = payments_for_account.filter(
            direction=AccountPayment.Direction.RECEIVE
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        paid_pay = payments_for_account.filter(
            direction=AccountPayment.Direction.PAY
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        # مانده قابل تسویه بر اساس نوع حساب:
        # - برای حساب‌های بدهکار (طلب بنگاه از طرف مقابل): orig_debit - مجموع دریافت‌ها
        # - برای حساب‌های بستانکار (بدهی بنگاه به طرف مقابل): orig_credit - مجموع پرداخت‌ها
        remaining_receivable = orig_debit - paid_receive
        remaining_payable = orig_credit - paid_pay

        amt_dec = Decimal(str(amount))

        # اگر این حساب طلب بنگاه است، اجازه دریافت بیش از مانده را نده
        if (
            direction == AccountPayment.Direction.RECEIVE
            and orig_debit > 0
            and amt_dec > remaining_receivable
        ):
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "مبلغ وارد شده بیشتر از مانده قابل دریافت از این حساب است. "
                        f"مانده فعلی: {remaining_receivable} ریال."
                    ),
                },
                status=400,
            )

        # اگر این حساب بدهی بنگاه است، اجازه پرداخت بیش از مانده را نده
        if (
            direction == AccountPayment.Direction.PAY
            and orig_credit > 0
            and amt_dec > remaining_payable
        ):
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "مبلغ وارد شده بیشتر از مانده قابل پرداخت به این حساب است. "
                        f"مانده فعلی: {remaining_payable} ریال."
                    ),
                },
                status=400,
            )

        date_val = None
        if payment_date:
            try:
                parts = str(payment_date).replace("/", "-").split("-")
                if len(parts) >= 3:
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 1500:
                        from jdatetime import date as jdate

                        date_val = jdate(y, m, d).togregorian()
                    else:
                        date_val = date_type(y, m, d)
            except (ValueError, TypeError):
                pass
        if date_val is None:
            date_val = date_type.today()

        try:
            create_account_payment(
                document=document,
                account=account,
                amount=amount,
                direction=AccountPayment.Direction(direction),
                date=date_val,
                method=method or "",
                description=description or "",
                user=request.user,
                receipt_file=receipt_file,
            )
        except ValueError as e:
            return JsonResponse(
                {"success": False, "message": str(e)},
                status=400,
            )

        return JsonResponse(
            {"success": True, "message": "تراکنش با موفقیت ثبت شد."},
        )
