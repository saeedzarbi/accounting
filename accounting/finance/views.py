import json
import os
from datetime import date as date_type
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q, Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, ListView, TemplateView
from transactions.models import Deals

from .forms import JournalEntryForm, VoucherDocumentForm
from .models import (
    Account,
    AccountEntry,
    AccountingDocument,
    AccountPayment,
    DealFinance,
    PendingDealPayment,
)
from .services import (
    create_account_payment,
    create_journal_document,
    create_payment_document,
    create_receipt_document,
    get_deal_ledger_summary,
    repair_deal_ledger_revenue,
)
from .utils import (
    ensure_office_accounts,
    ensure_office_manager_accounts,
    setup_chart_of_accounts,
)


class DealAccountsView(LoginRequiredMixin, TemplateView):
    """صفحه نمایش حساب‌های ساخته‌شده برای یک معامله (سند حسابداری کمیسیون)."""

    template_name = "finance/deal_accounts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deal_id = self.kwargs.get("deal_id")
        user = self.request.user
        office = getattr(user, "office", None)

        deal = get_object_or_404(Deals, id=deal_id)
        is_consultant = getattr(user, "is_consultant", False) and getattr(
            user, "consultant_profile", None
        )
        if is_consultant:
            if user.consultant_profile not in deal.consultants.all():
                raise Http404("معامله مربوط به شما نیست.")
        elif office and deal.office_id != office.id:
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

        summary = get_deal_ledger_summary(deal, trx, context["document"])
        context.update(summary)
        # مشاور فقط حساب‌های نوع مشتری را در فرم ثبت تراکنش می‌بیند.
        deal_accounts_list = summary["deal_accounts_list"]
        if is_consultant:
            deal_accounts_list = [
                a
                for a in deal_accounts_list
                if a.get("category") in ("receivable_client", "payable_client")
            ]
        context["deal_accounts_list"] = deal_accounts_list
        context["payments_by_account_json"] = json.dumps(
            summary["payments_by_account"], cls=DjangoJSONEncoder, ensure_ascii=False
        )
        context["deal_accounts_list_json"] = json.dumps(
            deal_accounts_list, cls=DjangoJSONEncoder, ensure_ascii=False
        )
        # تراکنش‌های در انتظار تایید (ثبت‌شده توسط مشاور).
        context["pending_payments"] = list(
            PendingDealPayment.objects.filter(deal=deal)
            .select_related("account", "created_by")
            .order_by("-created_at")
        )
        context["can_approve_pending"] = not is_consultant
        context["is_consultant_deal_accounts"] = is_consultant
        return context


class OfficeFinanceView(LoginRequiredMixin, TemplateView):
    """
    مدیریت مالی بنگاه: حساب‌های بنگاه، معاملات مرتبط، گزارش درآمد و هزینه.
    """

    template_name = "finance/office_finance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        office = getattr(self.request.user, "office", None)
        context["office"] = office

        if not office:
            context["office_receivable"] = None
            context["office_payable"] = None
            context["balance_receivable"] = Decimal("0")
            context["balance_payable"] = Decimal("0")
            context["manager_receivable"] = None
            context["manager_payable"] = None
            context["balance_manager_receivable"] = Decimal("0")
            context["balance_manager_payable"] = Decimal("0")
            context["deals"] = []
            context["deals_with_ledger_count"] = 0
            context["report_total_revenue"] = Decimal("0")
            context["report_total_expense_consultant"] = Decimal("0")
            context["report_total_expense_manager"] = Decimal("0")
            context["recent_payments"] = []
            return context

        acc_rec, acc_pay = ensure_office_accounts(office)
        context["office_receivable"] = acc_rec
        context["office_payable"] = acc_pay
        context["balance_receivable"] = acc_rec.get_balance()
        context["balance_payable"] = acc_pay.get_balance()

        mgr_rec, mgr_pay = ensure_office_manager_accounts(office)
        context["manager_receivable"] = mgr_rec
        context["manager_payable"] = mgr_pay
        context["balance_manager_receivable"] = mgr_rec.get_balance()
        context["balance_manager_payable"] = mgr_pay.get_balance()

        deals_qs = (
            Deals.objects.filter(office=office)
            .select_related("type")
            .order_by("-created_at")[:50]
        )
        deal_ids_with_finance = set(
            DealFinance.objects.filter(deal__office=office).values_list(
                "deal_id", flat=True
            )
        )
        deals = []
        for d in deals_qs:
            deals.append(
                {
                    "deal": d,
                    "has_ledger": d.id in deal_ids_with_finance,
                }
            )
        context["deals"] = deals
        context["deals_total_count"] = Deals.objects.filter(office=office).count()
        context["deals_with_ledger_count"] = len(deal_ids_with_finance)

        trx_ids = list(
            DealFinance.objects.filter(deal__office=office).values_list(
                "income_transaction_id", flat=True
            )
        )
        if trx_ids:
            rev = AccountEntry.objects.filter(
                transaction_id__in=trx_ids,
                account__category=Account.AccountCategory.REVENUE_COMMISSION,
            ).aggregate(s=Sum("credit"))["s"]
            context["report_total_revenue"] = rev or Decimal("0")
            exp_c = AccountEntry.objects.filter(
                transaction_id__in=trx_ids,
                account__category=Account.AccountCategory.EXPENSE_CONSULTANT_SHARE,
            ).aggregate(s=Sum("debit"))["s"]
            context["report_total_expense_consultant"] = exp_c or Decimal("0")
            exp_m = AccountEntry.objects.filter(
                transaction_id__in=trx_ids,
                account__category=Account.AccountCategory.EXPENSE_MANAGER_SHARE,
            ).aggregate(s=Sum("debit"))["s"]
            context["report_total_expense_manager"] = exp_m or Decimal("0")
        else:
            context["report_total_revenue"] = Decimal("0")
            context["report_total_expense_consultant"] = Decimal("0")
            context["report_total_expense_manager"] = Decimal("0")

        context["recent_payments"] = (
            AccountPayment.objects.filter(deal__office=office)
            .select_related("account", "deal")
            .order_by("-date", "-created_at")[:20]
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


class ChartOfAccountsView(LoginRequiredMixin, ListView):
    """نمودار حساب‌ها: لیست حساب‌ها با سلسله‌مراتب، کد، نام، نوع، مانده و لینک به گردش حساب."""

    template_name = "finance/chart_of_accounts.html"
    context_object_name = "accounts"
    paginate_by = 50

    def get_queryset(self):
        setup_chart_of_accounts()
        qs = (
            Account.objects.filter(is_active=True)
            .select_related("parent")
            .order_by("code")
        )
        account_type = self.request.GET.get("account_type")
        if account_type and account_type in dict(Account.AccountType.choices):
            qs = qs.filter(account_type=account_type)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        accounts_with_balance = []
        for acc in context["accounts"]:
            accounts_with_balance.append({"account": acc, "balance": acc.get_balance()})
        context["accounts_with_balance"] = accounts_with_balance
        context["account_type_filter"] = self.request.GET.get("account_type", "")
        context["account_type_choices"] = Account.AccountType.choices
        return context


class AccountLedgerView(LoginRequiredMixin, TemplateView):
    """گردش حساب: برای یک حساب، لیست ثبت‌های دفتری با تاریخ، بدهکار/بستانکار، مانده تجمعی و فیلتر بازه تاریخ."""

    template_name = "finance/account_ledger.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account_id = self.kwargs.get("account_id")
        account = get_object_or_404(Account, id=account_id, is_active=True)
        context["account"] = account
        context["balance"] = account.get_balance()

        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        entries_qs = (
            AccountEntry.objects.filter(account=account)
            .select_related("transaction")
            .order_by("transaction__date", "transaction_id", "id")
        )
        if date_from:
            entries_qs = entries_qs.filter(transaction__date__gte=date_from)
        if date_to:
            entries_qs = entries_qs.filter(transaction__date__lte=date_to)

        rows = []
        running = Decimal("0")
        for e in entries_qs:
            debit = e.debit or Decimal("0")
            credit = e.credit or Decimal("0")
            if account.account_type in (
                Account.AccountType.ASSET,
                Account.AccountType.EXPENSE,
            ):
                running += debit - credit
            else:
                running += credit - debit
            rows.append(
                {
                    "entry": e,
                    "debit": debit,
                    "credit": credit,
                    "running_balance": running,
                }
            )
        context["ledger_rows"] = rows
        context["date_from"] = date_from or ""
        context["date_to"] = date_to or ""
        return context


class JournalEntryCreateView(LoginRequiredMixin, FormView):
    """ثبت سند روزنامه دستی."""

    template_name = "finance/journal_entry_form.html"
    form_class = JournalEntryForm
    success_url = None

    def get_success_url(self):
        return reverse("finance:accounting-documents-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["accounts"] = Account.objects.filter(is_active=True).order_by("code")
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if form and not self.request.POST:
            form.add_row()
        return form

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        form.load_from_post(request.POST)
        if not form.is_valid():
            return self.form_invalid(form)
        try:
            rows = form.clean_rows(request.POST)
        except DjangoValidationError as e:
            form.add_error(None, e.messages[0] if e.messages else str(e))
            return self.form_invalid(form)
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        if not rows:
            form.add_error(None, "حداقل یک ردیف با حساب و مبلغ وارد کنید.")
            return self.form_invalid(form)
        date_val = form.cleaned_data.get("date")
        description = (form.cleaned_data.get("description") or "").strip()
        try:
            trx, doc = create_journal_document(date_val, description, rows)
        except ValueError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        return redirect(self.get_success_url())


class CreateVoucherView(LoginRequiredMixin, FormView):
    """ثبت سند دریافت یا سند پرداخت (نوع از آدرس URL مشخص می‌شود)."""

    template_name = "finance/voucher_form.html"
    form_class = VoucherDocumentForm
    success_url = None

    def get_success_url(self):
        return reverse("finance:accounting-documents-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["voucher_type"] = self.kwargs.get("voucher_type", "receipt")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["voucher_type"] = self.kwargs.get("voucher_type", "receipt")
        return context

    def form_valid(self, form):
        voucher_type = form.cleaned_data["voucher_type"]
        receipt_file = self.request.FILES.get("receipt_file")
        common = {
            "date": form.cleaned_data["date"],
            "account": form.cleaned_data["account"],
            "amount": form.cleaned_data["amount"],
            "method": form.cleaned_data.get("method") or "",
            "description": form.cleaned_data.get("description") or "",
            "user": self.request.user,
            "receipt_file": receipt_file,
        }
        if voucher_type == "receipt":
            create_receipt_document(**common)
        else:
            create_payment_document(**common)
        return redirect(self.get_success_url())


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
    """ثبت پرداخت/دریافت برای یکی از حساب‌های معامله (فقط POST). مشاور فقط حساب مشتری و به‌صورت در انتظار تایید ثبت می‌کند."""

    def post(self, request, deal_id):
        user = request.user
        office = getattr(user, "office", None)
        is_consultant = getattr(user, "is_consultant", False) and getattr(
            user, "consultant_profile", None
        )
        deal = get_object_or_404(Deals, id=deal_id)

        if is_consultant:
            if user.consultant_profile not in deal.consultants.all():
                return JsonResponse(
                    {"success": False, "message": "دسترسی به این معامله مجاز نیست."},
                    status=403,
                )
        elif office is None or deal.office_id != office.id:
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
        # مشاور فقط می‌تواند تراکنش برای حساب‌های نوع مشتری پیشنهاد دهد (در انتظار تایید).
        _client_categories = ("receivable_client", "payable_client")
        _transaction_target_categories = (
            "receivable_client",
            "payable_client",
            "receivable_consultant",
            "payable_consultant",
            "receivable_manager",
            "payable_manager",
        )
        if is_consultant:
            if getattr(account, "category", None) not in _client_categories:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "مشاور فقط می‌تواند تراکنش برای حساب‌های مشتری (پرداخت/دریافت مشتری) ثبت کند.",
                    },
                    status=400,
                )
        elif getattr(account, "category", None) not in _transaction_target_categories:
            return JsonResponse(
                {
                    "success": False,
                    "message": "ثبت تراکنش فقط برای پرداخت/دریافت مشتری، پرداخت به مشاور و پرداخت به مدیر بنگاه امکان‌پذیر است.",
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

        # مشاور: ثبت به‌صورت «در انتظار تایید»؛ پس از تایید اپراتور/مدیر در دفتر اعمال می‌شود.
        if is_consultant:
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
            PendingDealPayment.objects.create(
                deal=deal,
                account=account,
                amount=amt_dec,
                direction=direction,
                date=date_val,
                method=method or "",
                description=description or "",
                receipt_file=receipt_file,
                created_by=user,
                status=PendingDealPayment.Status.PENDING,
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": "تراکنش ثبت شد و پس از تایید اپراتور یا مدیر بنگاه در دفتر اعمال می‌شود.",
                },
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


class ApprovePendingDealPaymentView(LoginRequiredMixin, View):
    """تایید تراکنش پیشنهادی مشاور توسط اپراتور/مدیر و اعمال آن در دفتر."""

    def post(self, request, deal_id, pending_id):
        if getattr(request.user, "is_consultant", False):
            return JsonResponse(
                {
                    "success": False,
                    "message": "فقط اپراتور یا مدیر بنگاه می‌تواند تایید کند.",
                },
                status=403,
            )
        office = getattr(request.user, "office", None)
        if not office:
            return JsonResponse(
                {"success": False, "message": "دسترسی مجاز نیست."},
                status=403,
            )
        deal = get_object_or_404(Deals, id=deal_id, office=office)
        pending = get_object_or_404(
            PendingDealPayment,
            id=pending_id,
            deal=deal,
            status=PendingDealPayment.Status.PENDING,
        )
        document = AccountingDocument.objects.filter(
            deal=deal, doc_type=AccountingDocument.DocType.COMMISSION
        ).first()
        try:
            payment = create_account_payment(
                document=document,
                account=pending.account,
                amount=pending.amount,
                direction=AccountPayment.Direction(pending.direction),
                date=pending.date,
                method=pending.method or "",
                description=pending.description or "",
                user=request.user,
                receipt_file=pending.receipt_file,
            )
            from django.utils import timezone as tz

            pending.status = PendingDealPayment.Status.APPROVED
            pending.reviewed_by = request.user
            pending.reviewed_at = tz.now()
            pending.account_payment = payment
            pending.save(
                update_fields=[
                    "status",
                    "reviewed_by",
                    "reviewed_at",
                    "account_payment",
                ]
            )
        except ValueError as e:
            return JsonResponse(
                {"success": False, "message": str(e)},
                status=400,
            )
        return JsonResponse(
            {"success": True, "message": "تراکنش تایید شد و در دفتر اعمال شد."},
        )


class RejectPendingDealPaymentView(LoginRequiredMixin, View):
    """رد تراکنش پیشنهادی مشاور توسط اپراتور/مدیر."""

    def post(self, request, deal_id, pending_id):
        if getattr(request.user, "is_consultant", False):
            return JsonResponse(
                {
                    "success": False,
                    "message": "فقط اپراتور یا مدیر بنگاه می‌تواند رد کند.",
                },
                status=403,
            )
        office = getattr(request.user, "office", None)
        if not office:
            return JsonResponse(
                {"success": False, "message": "دسترسی مجاز نیست."},
                status=403,
            )
        deal = get_object_or_404(Deals, id=deal_id, office=office)
        pending = get_object_or_404(
            PendingDealPayment,
            id=pending_id,
            deal=deal,
            status=PendingDealPayment.Status.PENDING,
        )
        from django.utils import timezone as tz

        reason = ""
        if request.content_type and "application/json" in (request.content_type or ""):
            try:
                data = json.loads(request.body)
                reason = (data.get("rejection_reason") or "").strip()
            except Exception:
                pass
        else:
            reason = (request.POST.get("rejection_reason") or "").strip()
        pending.status = PendingDealPayment.Status.REJECTED
        pending.reviewed_by = request.user
        pending.reviewed_at = tz.now()
        pending.rejection_reason = reason[:2000] if reason else ""
        pending.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"]
        )
        return JsonResponse(
            {"success": True, "message": "تراکنش رد شد."},
        )
