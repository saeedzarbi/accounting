import pathlib

import weasyprint
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import Context, Template
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView
from transactions.forms import DealCreateForm, DealPropertyForm
from transactions.models import (
    Client,
    ContractTemplate,
    DealContract,
    DealProperty,
    Deals,
)
from weasyprint.text.fonts import FontConfiguration

_ASCII_TO_PERSIAN = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_persian_nums(value):
    if value is None:
        return ""
    return str(value).translate(_ASCII_TO_PERSIAN)


def text_to_persian_digits(text):
    if not text:
        return text
    return str(text).translate(_ASCII_TO_PERSIAN)


PLACEHOLDER = "......"


def client_to_template_dict(client):

    return {
        "name": client.name or PLACEHOLDER,
        "father_name": client.father_name or PLACEHOLDER,
        "national_id": client.national_id or PLACEHOLDER,
        "city_of_issuance": client.city_of_issuance or PLACEHOLDER,
        "birth_date": client.birth_date or PLACEHOLDER,
        "phone": client.phone or PLACEHOLDER,
        "address": PLACEHOLDER,
    }


def property_to_template_dict(prop):
    if prop is None:
        return {
            "property_dang": PLACEHOLDER,
            "property_title": PLACEHOLDER,
            "registry_sub_number": PLACEHOLDER,
            "registry_main_number": PLACEHOLDER,
            "registry_piece_number": PLACEHOLDER,
            "registry_section": PLACEHOLDER,
            "registry_area": PLACEHOLDER,
            "area_m2": PLACEHOLDER,
            "deed_serial": PLACEHOLDER,
            "deed_page": PLACEHOLDER,
            "deed_book": PLACEHOLDER,
            "parking_dang": PLACEHOLDER,
            "parking_number": PLACEHOLDER,
            "parking_area_m2": PLACEHOLDER,
            "parking_deed_serial": PLACEHOLDER,
            "storage_dang": PLACEHOLDER,
            "storage_number": PLACEHOLDER,
            "storage_area_m2": PLACEHOLDER,
            "storage_deed_serial": PLACEHOLDER,
            "water_share": PLACEHOLDER,
            "electricity_share": PLACEHOLDER,
            "gas_share": PLACEHOLDER,
            "phone_numbers": PLACEHOLDER,
            "property_address": PLACEHOLDER,
            "postal_code": PLACEHOLDER,
        }
    return {
        "property_dang": (
            to_persian_nums(prop.property_dang)
            if prop.property_dang is not None
            else PLACEHOLDER
        ),
        "property_title": prop.property_title or PLACEHOLDER,
        "registry_sub_number": prop.registry_sub_number or PLACEHOLDER,
        "registry_main_number": prop.registry_main_number or PLACEHOLDER,
        "registry_piece_number": prop.registry_piece_number or PLACEHOLDER,
        "registry_section": prop.registry_section or PLACEHOLDER,
        "registry_area": prop.registry_area or PLACEHOLDER,
        "area_m2": (
            to_persian_nums(prop.area_m2) if prop.area_m2 is not None else PLACEHOLDER
        ),
        "deed_serial": prop.deed_serial or PLACEHOLDER,
        "deed_page": prop.deed_page or PLACEHOLDER,
        "deed_book": prop.deed_book or PLACEHOLDER,
        "parking_dang": (
            to_persian_nums(prop.parking_dang)
            if prop.parking_dang is not None
            else PLACEHOLDER
        ),
        "parking_number": prop.parking_number or PLACEHOLDER,
        "parking_area_m2": (
            to_persian_nums(prop.parking_area_m2)
            if prop.parking_area_m2 is not None
            else PLACEHOLDER
        ),
        "parking_deed_serial": prop.parking_deed_serial or PLACEHOLDER,
        "storage_dang": (
            to_persian_nums(prop.storage_dang)
            if prop.storage_dang is not None
            else PLACEHOLDER
        ),
        "storage_number": prop.storage_number or PLACEHOLDER,
        "storage_area_m2": (
            to_persian_nums(prop.storage_area_m2)
            if prop.storage_area_m2 is not None
            else PLACEHOLDER
        ),
        "storage_deed_serial": prop.storage_deed_serial or PLACEHOLDER,
        "water_share": (
            prop.get_water_share_display() if prop.water_share else PLACEHOLDER
        ),
        "electricity_share": (
            prop.get_electricity_share_display()
            if prop.electricity_share
            else PLACEHOLDER
        ),
        "gas_share": prop.get_gas_share_display() if prop.gas_share else PLACEHOLDER,
        "phone_numbers": prop.phone_numbers or PLACEHOLDER,
        "property_address": prop.property_address or PLACEHOLDER,
        "postal_code": prop.postal_code or PLACEHOLDER,
    }


@login_required
def generate_contract_view(request, deal_id):
    deal = get_object_or_404(Deals, id=deal_id)

    user_office = getattr(request.user, "office", None)
    if not user_office:
        return HttpResponseForbidden(
            "شما عضو هیچ دفتر املاکی نیستید و نمی‌توانید قرارداد ایجاد کنید."
        )

    if deal.office != user_office:
        return HttpResponseForbidden(
            "شما اجازه دسترسی به معاملات سایر دفاتر را ندارید."
        )

    sellers_count = deal.sellers.count()
    buyers_count = deal.buyers.count()

    if request.method == "POST":
        template_id = request.POST.get("template_id")
        template = get_object_or_404(ContractTemplate, id=template_id)

        has_header_value = request.POST.get("has_header")
        should_have_header = True if has_header_value == "on" else False

        seller_list = [client_to_template_dict(c) for c in deal.sellers.all()]
        buyer_list = [client_to_template_dict(c) for c in deal.buyers.all()]
        try:
            deal_property = deal.property_details
        except DealProperty.DoesNotExist:
            deal_property = None
        property_data = property_to_template_dict(deal_property)

        deal_type_name = deal.type.name if getattr(deal, "type", None) else "قرارداد"
        context_data = {
            "seller_list": seller_list,
            "buyer_list": buyer_list,
            "sellers_str": "، ".join([s["name"] for s in seller_list]),
            "buyers_str": "، ".join([b["name"] for b in buyer_list]),
            "property": property_data,
            "deal_type_name": deal_type_name,
        }

        django_template = Template(template.body)
        rendered_content = django_template.render(Context(context_data))

        contract = DealContract.objects.create(
            deal=deal,
            template=template,
            content=rendered_content,
            has_header=should_have_header,
        )

        return redirect("contract_edit", pk=contract.id)

    current_mode = ""
    if sellers_count == 1 and buyers_count == 1:
        current_mode = "SS"
    elif sellers_count > 1 and buyers_count == 1:
        current_mode = "MS"
    elif sellers_count == 1 and buyers_count > 1:
        current_mode = "SM"
    else:
        current_mode = "MM"

    templates = ContractTemplate.objects.filter(transaction_type=deal.type).filter(
        Q(participant_mode=current_mode) | Q(participant_mode="ALL")
    )

    context = {"deal": deal, "templates": templates, "suggested_mode": current_mode}
    return render(request, "deals/select_template.html", context)


class DealContractForm(forms.ModelForm):
    class Meta:
        model = DealContract
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 15,
                    "style": "width:100%; padding:10px; font-size:14px;",
                }
            ),
        }


class ContractUpdateView(UpdateView):
    model = DealContract
    form_class = DealContractForm
    template_name = "deals/contract_edit.html"

    def get_success_url(self):
        return reverse("contract_print", kwargs={"pk": self.object.pk})


def contract_print_view(request, pk):
    contract = get_object_or_404(DealContract, pk=pk)
    return render(request, "deals/contract_print.html", {"contract": contract})


@login_required
def contract_pdf_view(request, pk):
    try:
        contract = get_object_or_404(DealContract, pk=pk)

        user_office = getattr(request.user, "office", None)

        if not user_office:
            return redirect(settings.LOGIN_URL)

        if contract.deal.office != user_office:
            return HttpResponseForbidden(
                "شما اجازه دسترسی به قراردادهای سایر دفاتر را ندارید."
            )

        if getattr(settings, "STATIC_ROOT", None):
            static_base = pathlib.Path(settings.STATIC_ROOT)
        else:
            static_base = pathlib.Path(settings.BASE_DIR) / "static"

        font_config = FontConfiguration()

        fonts_dir = static_base / "fonts"
        font_main_name = "BNazanin.ttf"
        if not (fonts_dir / font_main_name).exists():
            alt = "Bnazanin.ttf"
            if (fonts_dir / alt).exists():
                font_main_name = alt
        font_titr_name = "BTitr.ttf"
        if not (fonts_dir / font_titr_name).exists():
            alt = "Btir.ttf"
            if (fonts_dir / alt).exists():
                font_titr_name = alt
        try:
            base_url = static_base.resolve().as_uri() + "/"
        except Exception:
            base_url = static_base.as_uri() + "/"
        font_main_url = f"fonts/{font_main_name}"
        font_titr_url = f"fonts/{font_titr_name}"

        css_path = static_base / "css" / "fonts.css"
        external_css = ""
        if css_path.exists():
            with open(css_path, "r", encoding="utf-8") as f:
                external_css = f.read()

        deal_id_fa = to_persian_nums(contract.deal.id)
        office_name = to_persian_nums(
            contract.deal.office.name if contract.deal.office else "نامشخص"
        )
        content_body = text_to_persian_digits(contract.content)

        header_content = ""
        if contract.has_header:
            header_content = f"""
                <div class="header-table">
                    <div class="header-right">املاک {office_name}</div>
                    <div class="header-center">مبایعه نامه</div>
                    <div class="header-left">شماره: {deal_id_fa}</div>
                </div>
                <div class="header-line"></div>
            """

        watermark_html = ""
        watermark_css = ""

        if not contract.is_finalized:
            watermark_html = '<div class="watermark">پیش‌نویس</div>'
            watermark_css = """
                .watermark {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%) rotate(-45deg);

                    font-size: 80px;
                    font-family: 'BTitr';
                    font-weight: bold;

                    color: rgba(220, 53, 69, 0.1);
                    border: 4px solid rgba(220, 53, 69, 0.1);

                    padding: 10px 30px;
                    border-radius: 15px;

                    z-index: 9999;
                    pointer-events: none;
                    white-space: nowrap;
                }
            """

        html_string = f"""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <style>
                {external_css}

                @font-face {{ font-family: 'PersianFont'; src: url('{font_main_url}') format('truetype'); }}
                @font-face {{ font-family: 'BNazanin'; src: url('{font_main_url}') format('truetype'); }}
                @font-face {{ font-family: 'BTitr'; src: url('{font_titr_url}') format('truetype'); }}

                @page {{
                    size: A4;
                    margin: 1.5cm;
                    border: 2px solid #000;
                    padding: 1cm;

                    @top-center {{ content: element(pageHeader); }}
                    @bottom-center {{ content: element(pageFooter); }}
                }}

                body {{
                    font-family: 'BNazanin', 'PersianFont', Tahoma;
                    font-size: 14px; text-align: justify; margin: 0; line-height: 1.8;
                }}

                .content-body {{
                    font-family: 'BNazanin', 'PersianFont', Tahoma;
                    font-size: 14px; text-align: justify; direction: rtl; line-height: 1.8;
                }}
                .content-body table {{
                    width: 100%;
                    table-layout: fixed;
                    border-collapse: collapse;
                }}
                .content-body table tbody tr {{
                    display: table-row;
                }}
                .content-body table td {{
                    width: 33.33%;
                    text-align: center;
                    vertical-align: top;
                    padding: 8px 4px;
                    box-sizing: border-box;
                }}

                .header-table {{ display: table; width: 100%; margin-bottom: 5px; }}
                .header-right {{ display: table-cell; width: 30%; text-align: right; vertical-align: middle; font-weight: bold; }}
                .header-center {{ display: table-cell; width: 40%; text-align: center; vertical-align: middle; font-family: 'BTitr'; font-size: 20px; }}
                .header-left {{ display: table-cell; width: 30%; text-align: left; vertical-align: middle; font-size: 12px; }}

                header {{ position: running(pageHeader); width: 100%; }}
                footer {{ position: running(pageFooter); width: 100%; text-align: center; border-top: 1px solid #ccc; padding-top: 5px; font-family: 'PersianFont'; }}
                .page-number:after {{ content: "صفحه " counter(page) " از " counter(pages); }}
                .header-line {{ border-bottom: 2px solid #000; margin-top: 5px; }}

                {watermark_css}
            </style>
        </head>
        <body>
            {watermark_html}
            <header>{header_content}</header>
            <footer><span class="page-number"></span></footer>
            <div class="content-body">{content_body}</div>
        </body>
        </html>
        """

        pdf_file = weasyprint.HTML(string=html_string, base_url=base_url).write_pdf(
            font_config=font_config
        )

        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="Contract-{contract.id}.pdf"'
        )
        return response

    except Exception as e:
        import traceback

        return HttpResponse(f"Error: {str(e)} <br> <pre>{traceback.format_exc()}</pre>")


@login_required
def create_deal_view(request):

    if not getattr(request.user, "office", None):
        messages.error(
            request, "شما عضو هیچ دفتر املاکی نیستید. ابتدا دفتر خود را مشخص کنید."
        )
        return redirect(settings.LOGIN_URL)

    office = request.user.office
    client_queryset = Client.objects.filter(office=office)

    if request.method == "POST":
        form = DealCreateForm(request.POST)
        form.fields["sellers"].queryset = client_queryset
        form.fields["buyers"].queryset = client_queryset
        if form.is_valid():
            deal = form.save(commit=False)
            deal.created_by = request.user
            deal.office = office
            deal.status = "init"
            deal.save()
            form.save_m2m()
            return redirect("deal_property", deal_id=deal.id)
    else:
        form = DealCreateForm()
        form.fields["sellers"].queryset = client_queryset
        form.fields["buyers"].queryset = client_queryset

    return render(request, "deals/create_deal.html", {"form": form, "deal": None})


@login_required
def edit_deal_view(request, deal_id):
    user_office = getattr(request.user, "office", None)
    if not user_office:
        messages.error(request, "شما عضو هیچ دفتر املاکی نیستید.")
        return redirect(settings.LOGIN_URL)

    deal = get_object_or_404(Deals, id=deal_id)
    if deal.office != user_office:
        return HttpResponseForbidden("شما اجازه دسترسی به این مبایعه را ندارید.")

    office = request.user.office
    client_queryset = Client.objects.filter(office=office)

    if request.method == "POST":
        form = DealCreateForm(request.POST, instance=deal)
        form.fields["sellers"].queryset = client_queryset
        form.fields["buyers"].queryset = client_queryset
        if form.is_valid():
            form.save()
            form.save_m2m()
            return redirect("deal_property", deal_id=deal.id)
    else:
        form = DealCreateForm(instance=deal)
        form.fields["sellers"].queryset = client_queryset
        form.fields["buyers"].queryset = client_queryset

    initial_sellers = [
        {
            "id": c.id,
            "name": c.name or "",
            "national_id": c.national_id or "",
            "phone": c.phone or "",
        }
        for c in deal.sellers.all()
    ]
    initial_buyers = [
        {
            "id": c.id,
            "name": c.name or "",
            "national_id": c.national_id or "",
            "phone": c.phone or "",
        }
        for c in deal.buyers.all()
    ]

    return render(
        request,
        "deals/create_deal.html",
        {
            "form": form,
            "deal": deal,
            "initial_sellers": initial_sellers,
            "initial_buyers": initial_buyers,
        },
    )


@login_required
def deal_property_view(request, deal_id):
    deal = get_object_or_404(Deals, id=deal_id)

    user_office = getattr(request.user, "office", None)
    if not user_office:
        return HttpResponseForbidden("شما عضو هیچ دفتر املاکی نیستید.")

    if deal.office != user_office:
        return HttpResponseForbidden("شما اجازه دسترسی به این معامله را ندارید.")

    property_details, _ = DealProperty.objects.get_or_create(deal=deal)

    if request.method == "POST":
        form = DealPropertyForm(request.POST, instance=property_details)
        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات ملک ذخیره شد.")
            return redirect("generate_contract", deal_id=deal.id)
    else:
        form = DealPropertyForm(instance=property_details)

    return render(
        request, "deals/deal_property_form.html", {"deal": deal, "form": form}
    )


@login_required
def client_search_api(request):
    office = getattr(request.user, "office", None)
    if not office:
        return JsonResponse({"clients": []})
    qs = Client.objects.filter(office=office).order_by("-created_at")
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(national_id__icontains=q) | Q(phone__icontains=q)
        )
    qs = qs[:50]
    clients = [
        {
            "id": c.id,
            "name": c.name or "",
            "national_id": c.national_id or "",
            "phone": c.phone or "",
        }
        for c in qs
    ]
    return JsonResponse({"clients": clients})


@login_required
@require_POST
def quick_create_client(request):
    name = request.POST.get("name")
    phone = request.POST.get("phone")
    father_name = request.POST.get("father_name") or None
    national_id = request.POST.get("national_id") or None
    birth_date = request.POST.get("birth_date") or None
    city_of_issuance = request.POST.get("city_of_issuance") or None

    if not name:
        return JsonResponse({"error": "نام مشتری الزامی است"}, status=400)

    office = getattr(request.user, "office", None)
    if national_id and national_id.strip():
        national_id = national_id.strip()
        qs = Client.objects.filter(national_id=national_id)
        if office:
            qs = qs.filter(office=office)
        existing = qs.first()
        if existing:
            return JsonResponse(
                {"error": f"مشتری با این کد ملی با نام «{existing.name}» وجود دارد."},
                status=400,
            )

    client = Client.objects.create(
        name=name,
        phone=phone,
        father_name=father_name,
        national_id=national_id,
        birth_date=birth_date,
        city_of_issuance=city_of_issuance,
        office=request.user.office,
    )

    return JsonResponse(
        {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
            "father_name": client.father_name,
            "national_id": client.national_id,
            "birth_date": client.birth_date,
            "city_of_issuance": client.city_of_issuance,
        }
    )


def finalize_contract_view(request, pk):
    contract = get_object_or_404(DealContract, pk=pk)

    if request.method == "POST":
        contract.is_finalized = True
        contract.save()

        return redirect("contract_pdf", pk=contract.id)

    return redirect("contract_edit", pk=contract.id)


def save_contract_as_template_view(request, pk):
    contract = get_object_or_404(DealContract, pk=pk)

    if request.method == "POST":
        new_title = request.POST.get("template_title")

        sellers_count = contract.deal.sellers.count()
        buyers_count = contract.deal.buyers.count()

        mode = "ALL"
        if sellers_count == 1 and buyers_count == 1:
            mode = "SS"
        elif sellers_count > 1 and buyers_count == 1:
            mode = "MS"
        elif sellers_count == 1 and buyers_count > 1:
            mode = "SM"
        elif sellers_count > 1 and buyers_count > 1:
            mode = "MM"

        ContractTemplate.objects.create(
            title=new_title,
            body=contract.content,
            transaction_type=contract.deal.transaction_type,
            participant_mode=mode,
            is_default=False,
        )

        messages.success(request, f"قالب '{new_title}' با موفقیت ذخیره شد.")

    return redirect("contract_print", pk=contract.id)
