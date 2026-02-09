from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from finance.models import AccountEntry, AccountPayment
from finance.utils import (
    ensure_client_account,
    ensure_client_payable_account,
    ensure_consultant_accounts,
)
from rest_framework.authentication import SessionAuthentication
from transactions.models import Client, DealClientCommission, Deals

from .forms import (
    ClientForm,
    ConsultantForm,
    ConsultantLoginForm,
    LoginForm,
    ProfilePasswordChangeForm,
    ProfileUpdateForm,
)
from .models import Consultant, Role


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            has_office = getattr(user, "office", None) is not None
            is_consultant = getattr(user, "is_consultant", False)
            if not has_office and not is_consultant:
                logout(request)
                messages.warning(
                    request,
                    "کاربری شما به دفتری متصل نیست. لطفاً با مدیر سامانه تماس بگیرید.",
                )
                return redirect(reverse_lazy("login"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["is_consultant"] = getattr(user, "is_consultant", False)
        context["consultant"] = getattr(user, "consultant_profile", None)
        return context


def _build_consultant_commissions_summary(consultant):
    """ساخت لیست خلاصه معاملات و کمیسیون مشاور برای نمایش در صفحه خلاصه یا داشبورد."""
    from finance.models import DealFinance
    from transactions.models import CommissionSplit

    deals = (
        Deals.objects.filter(consultants=consultant)
        .select_related("type")
        .prefetch_related("buyers", "sellers")
        .order_by("-created_at")
    )
    deal_ids = list(deals.values_list("id", flat=True))
    splits_by_deal = {
        s["deal_id"]: s
        for s in CommissionSplit.objects.filter(
            deal_id__in=deal_ids,
            consultant=consultant,
            role="consultant",
        ).values("deal_id", "amount", "percentage")
    }
    has_ledger = set(
        DealFinance.objects.filter(deal_id__in=deal_ids).values_list(
            "deal_id", flat=True
        )
    )
    summary = []
    for d in deals:
        split = splits_by_deal.get(d.id)
        clients = [c.name for c in d.buyers.all()] + [c.name for c in d.sellers.all()]
        summary.append(
            {
                "deal": d,
                "deal_id": d.id,
                "title": (d.title or "").strip() or f"معامله #{d.id}",
                "type_name": d.type.name if d.type_id else "—",
                "date": d.date or "—",
                "status": d.status,
                "status_display": d.get_status_display(),
                "amount": d.amount,
                "my_commission": split["amount"] if split else None,
                "my_commission_percentage": (
                    split.get("percentage") if split else None
                ),
                "clients": clients,
                "has_ledger": d.id in has_ledger,
            }
        )
    return summary


class ConsultantSummaryView(LoginRequiredMixin, TemplateView):
    """صفحه «خلاصه کمیسیون و معاملات من» فقط برای مشاور."""

    template_name = "consultant_summary.html"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, "is_consultant", False) or not getattr(
            request.user, "consultant_profile", None
        ):
            messages.info(request, "این صفحه فقط برای مشاوران است.")
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultant = self.request.user.consultant_profile
        context["consultant_commissions_summary"] = (
            _build_consultant_commissions_summary(consultant)
        )
        return context


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


class LoginViewUI(DjangoLoginView):
    template_name = "login.html"
    form_class = LoginForm
    redirect_authenticated_user = True
    success_url = reverse_lazy("dashboard")

    def get_success_url(self):
        return self.get_redirect_url() or self.success_url

    def form_valid(self, form):
        user = form.get_user()
        if not user.roles.exists():
            messages.error(
                self.request,
                "ورود امکان‌پذیر نیست. این کاربر نقشی تعریف نشده است.",
            )
            return redirect("login")
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "profile.html"

    def _role_display(self, user):
        try:
            return user.role
        except Exception:
            return "مشخص نشده"

    def _office_display(self, user):
        if getattr(user, "office", None) and user.office:
            return user.office.name
        return "بنگاه مشخص نشده"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["profile_form"] = ProfileUpdateForm(instance=user)
        context["password_form"] = ProfilePasswordChangeForm(user=user)
        context["role_display"] = self._role_display(user)
        context["office_display"] = self._office_display(user)
        context["username"] = user.username
        return context

    def post(self, request, *args, **kwargs):
        user = request.user

        if "update_profile" in request.POST:
            profile_form = ProfileUpdateForm(instance=user, data=request.POST)
            password_form = ProfilePasswordChangeForm(user=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(
                    self.request, "اطلاعات پروفایل با موفقیت به‌روزرسانی شد."
                )
                return redirect("profile")
        elif "change_password" in request.POST:
            profile_form = ProfileUpdateForm(instance=user)
            password_form = ProfilePasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "رمز عبور با موفقیت تغییر کرد.")
                return redirect("profile")
        else:
            profile_form = ProfileUpdateForm(instance=user)
            password_form = ProfilePasswordChangeForm(user=user)

        context = self.get_context_data()
        context["profile_form"] = profile_form
        context["password_form"] = password_form
        return render(request, self.template_name, context)


@login_required
def manage_accounts(request):
    user = request.user
    if getattr(user, "is_consultant", False):
        messages.info(request, "دسترسی به مدیریت حساب‌ها فقط برای پرسنل دفتر است.")
        return redirect("dashboard")
    office = getattr(user, "office", None)

    client_form = ClientForm(prefix="client")
    consultant_form = ConsultantForm(prefix="consultant")

    if request.method == "POST":
        if not office:
            messages.error(
                request, "برای مدیریت حساب‌ها ابتدا باید به یک دفتر متصل شوید."
            )
            return redirect("manage-accounts")

        if "create_client" in request.POST:
            client_form = ClientForm(request.POST, prefix="client")
            if client_form.is_valid():
                client = client_form.save(commit=False)
                client.office = office
                client.save()
                messages.success(request, "مشتری جدید با موفقیت ثبت شد.")
                return redirect(reverse("manage-accounts") + "?tab=clients")
            # form invalid: fall through to render with show_client_modal
        elif "create_consultant" in request.POST:
            consultant_form = ConsultantForm(request.POST, prefix="consultant")
            if consultant_form.is_valid():
                consultant = consultant_form.save(commit=False)
                consultant.office = office
                consultant.save()
                messages.success(request, "مشاور جدید با موفقیت ثبت شد.")
                return redirect(reverse("manage-accounts") + "?tab=consultants")
            # form invalid: fall through to render with show_consultant_modal

    clients_qs = Client.objects.none()
    consultants_qs = Consultant.objects.none()
    if office:
        clients_qs = Client.objects.filter(office=office).order_by(
            "-created_at", "name"
        )
        consultants_qs = Consultant.objects.filter(office=office).order_by(
            "-created_at", "name"
        )

    per_page = 10
    client_page_num = request.GET.get("client_page", 1)
    consultant_page_num = request.GET.get("consultant_page", 1)
    try:
        client_page_num = max(1, int(client_page_num))
    except (TypeError, ValueError):
        client_page_num = 1
    try:
        consultant_page_num = max(1, int(consultant_page_num))
    except (TypeError, ValueError):
        consultant_page_num = 1

    clients_paginator = Paginator(clients_qs, per_page)
    consultants_paginator = Paginator(consultants_qs, per_page)
    clients_page = clients_paginator.get_page(client_page_num)
    consultants_page = consultants_paginator.get_page(consultant_page_num)

    current_tab = request.GET.get("tab", "clients")
    if current_tab not in ("clients", "consultants"):
        current_tab = "clients"

    show_client_modal = (
        request.method == "POST"
        and "create_client" in request.POST
        and not client_form.is_valid()
    )
    show_consultant_modal = (
        request.method == "POST"
        and "create_consultant" in request.POST
        and not consultant_form.is_valid()
    )
    if show_consultant_modal:
        current_tab = "consultants"
    if show_client_modal:
        current_tab = "clients"

    auto_open_modals = " ".join(
        (["modal-client"] if show_client_modal else [])
        + (["modal-consultant"] if show_consultant_modal else [])
    )

    context = {
        "client_form": client_form,
        "consultant_form": consultant_form,
        "clients_page": clients_page,
        "consultants_page": consultants_page,
        "current_tab": current_tab,
        "show_client_modal": show_client_modal,
        "show_consultant_modal": show_consultant_modal,
        "auto_open_modals": auto_open_modals,
    }
    return render(request, "accounts/manage_accounts.html", context)


@login_required
def edit_client(request, client_id):
    office = getattr(request.user, "office", None)
    client = get_object_or_404(Client, id=client_id, office=office)
    form = ClientForm(instance=client, prefix="client")

    if request.method == "POST":
        form = ClientForm(request.POST, instance=client, prefix="client")
        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات مشتری با موفقیت به‌روزرسانی شد.")
            return redirect("manage-accounts")

    return render(
        request,
        "accounts/edit_client.html",
        {"form": form, "client": client},
    )


@login_required
def edit_consultant(request, consultant_id):
    office = getattr(request.user, "office", None)
    consultant = get_object_or_404(Consultant, id=consultant_id, office=office)
    form = ConsultantForm(instance=consultant, prefix="consultant")
    login_form = ConsultantLoginForm(prefix="consultant_login")

    if request.method == "POST":
        if "enable_consultant_login" in request.POST:
            login_form = ConsultantLoginForm(request.POST, prefix="consultant_login")
            if login_form.is_valid():
                User = get_user_model()
                username = login_form.cleaned_data["username"]
                password = login_form.cleaned_data["password"]
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=consultant.name,
                    office=consultant.office,
                )
                role = Role.objects.filter(name="consultant").first()
                if role:
                    user.roles.add(role)
                consultant.user = user
                consultant.save()
                messages.success(
                    request,
                    "ورود برای مشاور فعال شد. نام کاربری: " + username,
                )
                return redirect("edit-consultant", consultant_id=consultant.id)
        else:
            form = ConsultantForm(
                request.POST, instance=consultant, prefix="consultant"
            )
            if form.is_valid():
                form.save()
                messages.success(request, "اطلاعات مشاور با موفقیت به‌روزرسانی شد.")
                return redirect("manage-accounts")

    return render(
        request,
        "accounts/edit_consultant.html",
        {
            "form": form,
            "consultant": consultant,
            "login_form": login_form,
        },
    )


@require_POST
@login_required
def delete_client(request, client_id):
    office = getattr(request.user, "office", None)
    client = get_object_or_404(Client, id=client_id, office=office)
    client.delete()
    messages.success(request, "مشتری با موفقیت حذف شد.")
    return redirect("manage-accounts")


@require_POST
@login_required
def delete_consultant(request, consultant_id):
    office = getattr(request.user, "office", None)
    consultant = get_object_or_404(Consultant, id=consultant_id, office=office)
    consultant.delete()
    messages.success(request, "مشاور با موفقیت حذف شد.")
    return redirect("manage-accounts")


@login_required
def client_account_detail(request, client_id):
    """صفحه جزئیات حساب مشتری: اطلاعات شخص، حساب‌ها، مانده، معاملات و کمیسیون‌ها."""
    office = getattr(request.user, "office", None)
    client = get_object_or_404(Client, id=client_id, office=office)

    acc_receivable = ensure_client_account(client)
    acc_payable = ensure_client_payable_account(client)

    balance_receivable = acc_receivable.get_balance()
    balance_payable = acc_payable.get_balance()

    entries_receivable = (
        AccountEntry.objects.filter(account=acc_receivable)
        .select_related("transaction")
        .order_by("-transaction__date", "-id")[:30]
    )
    entries_payable = (
        AccountEntry.objects.filter(account=acc_payable)
        .select_related("transaction")
        .order_by("-transaction__date", "-id")[:30]
    )

    payments_receivable = AccountPayment.objects.filter(
        account=acc_receivable
    ).order_by("-date", "-created_at")[:20]
    payments_payable = AccountPayment.objects.filter(account=acc_payable).order_by(
        "-date", "-created_at"
    )[:20]

    deals_as_buyer = (
        client.purchased_deals.filter(office=office)
        .select_related("type")
        .order_by("-created_at")[:15]
    )
    deals_as_seller = (
        client.sold_deals.filter(office=office)
        .select_related("type")
        .order_by("-created_at")[:15]
    )
    commissions = (
        DealClientCommission.objects.filter(client=client)
        .select_related("deal")
        .order_by("-deal__created_at")[:20]
    )

    context = {
        "client": client,
        "account_receivable": acc_receivable,
        "account_payable": acc_payable,
        "balance_receivable": balance_receivable,
        "balance_payable": balance_payable,
        "entries_receivable": entries_receivable,
        "entries_payable": entries_payable,
        "payments_receivable": payments_receivable,
        "payments_payable": payments_payable,
        "deals_as_buyer": deals_as_buyer,
        "deals_as_seller": deals_as_seller,
        "commissions": commissions,
        "person_type": "client",
    }
    return render(request, "accounts/account_detail.html", context)


@login_required
def consultant_account_detail(request, consultant_id):
    """صفحه جزئیات حساب مشاور: اطلاعات شخص، حساب‌ها، مانده، معاملات."""
    office = getattr(request.user, "office", None)
    consultant = get_object_or_404(Consultant, id=consultant_id, office=office)

    acc_payable, acc_receivable = ensure_consultant_accounts(consultant)

    balance_payable = acc_payable.get_balance()
    balance_receivable = acc_receivable.get_balance()

    entries_payable = (
        AccountEntry.objects.filter(account=acc_payable)
        .select_related("transaction")
        .order_by("-transaction__date", "-id")[:30]
    )
    entries_receivable = (
        AccountEntry.objects.filter(account=acc_receivable)
        .select_related("transaction")
        .order_by("-transaction__date", "-id")[:30]
    )

    payments_payable = AccountPayment.objects.filter(account=acc_payable).order_by(
        "-date", "-created_at"
    )[:20]
    payments_receivable = AccountPayment.objects.filter(
        account=acc_receivable
    ).order_by("-date", "-created_at")[:20]

    deals = (
        Deals.objects.filter(consultants=consultant, office=office)
        .select_related("type")
        .order_by("-created_at")[:15]
    )

    context = {
        "consultant": consultant,
        "account_receivable": acc_receivable,
        "account_payable": acc_payable,
        "balance_receivable": balance_receivable,
        "balance_payable": balance_payable,
        "entries_receivable": entries_receivable,
        "entries_payable": entries_payable,
        "payments_receivable": payments_receivable,
        "payments_payable": payments_payable,
        "deals": deals,
        "person_type": "consultant",
    }
    return render(request, "accounts/account_detail.html", context)


def pwa_manifest(request):
    """PWA manifest for installability and PWABuilder/Android packaging."""
    base = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse(
        {
            "name": "سامانه حسابداری املاک",
            "short_name": "حسابداری املاک",
            "description": "سامانه حسابداری و معاملات املاک",
            "start_url": base + "/login/",
            "display": "standalone",
            "orientation": "any",
            "lang": "fa",
            "dir": "rtl",
            "theme_color": "#0f172a",
            "background_color": "#0f172a",
            "icons": [
                {
                    "src": base + "/static/images/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": base + "/static/images/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
            ],
        }
    )
