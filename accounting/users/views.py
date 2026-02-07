from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from transactions.models import Client

from .forms import (
    ClientForm,
    ConsultantForm,
    LoginForm,
    ProfilePasswordChangeForm,
    ProfileUpdateForm,
)
from .models import Consultant


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"


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

    if request.method == "POST":
        form = ConsultantForm(request.POST, instance=consultant, prefix="consultant")
        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات مشاور با موفقیت به‌روزرسانی شد.")
            return redirect("manage-accounts")

    return render(
        request,
        "accounts/edit_consultant.html",
        {"form": form, "consultant": consultant},
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
