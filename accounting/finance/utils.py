from .models import Account


def setup_chart_of_accounts():
    """
    ایجاد نمودار حساب‌های پایه بر اساس ساختار تعریف شده.
    پشتیبانی از بستانکاری و طلبکاری برای مشتریان، مشاوران، بنگاه و مدیر بنگاه.
    """
    # 1. حساب‌های اصلی (Root Accounts)
    assets, _ = Account.objects.get_or_create(
        name="دارایی‌ها",
        code="1",
        defaults={
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.OTHER,
        },
    )
    liabilities, _ = Account.objects.get_or_create(
        name="بدهی‌ها",
        code="2",
        defaults={
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.OTHER,
        },
    )
    income, _ = Account.objects.get_or_create(
        name="درآمدها",
        code="4",
        defaults={
            "account_type": Account.AccountType.INCOME,
            "category": Account.AccountCategory.OTHER,
        },
    )
    expenses, _ = Account.objects.get_or_create(
        name="هزینه‌ها",
        code="5",
        defaults={
            "account_type": Account.AccountType.EXPENSE,
            "category": Account.AccountCategory.OTHER,
        },
    )

    # 2. حساب‌های تفصیلی (Sub Accounts)

    # 1/1/01/001 -> نقد و بانک
    cash_parent, _ = Account.objects.get_or_create(
        code="110101",
        name="نقد و بانک",
        defaults={
            "parent": assets,
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.CASH_BANK,
        },
    )

    # 1/1/02/001 -> بستانکاری از مشتریان (کمیسیون دریافتنی)
    receivables_commission, _ = Account.objects.get_or_create(
        code="110201",
        name="بستانکاری کمیسیون از مشتریان",
        defaults={
            "parent": assets,
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_CLIENT,
        },
    )

    # 1/1/02/002 -> بستانکاری از مشاوران
    receivables_consultant, _ = Account.objects.get_or_create(
        code="110302",
        name="بستانکاری از مشاوران",
        defaults={
            "parent": assets,
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_CONSULTANT,
        },
    )

    # 1/1/02/003 -> بستانکاری از بنگاه
    receivables_office, _ = Account.objects.get_or_create(
        code="110403",
        name="بستانکاری از بنگاه",
        defaults={
            "parent": assets,
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_OFFICE,
        },
    )

    # 1/1/02/004 -> بستانکاری از مدیر بنگاه
    receivables_manager, _ = Account.objects.get_or_create(
        code="110504",
        name="بستانکاری از مدیر بنگاه",
        defaults={
            "parent": assets,
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_MANAGER,
        },
    )

    # 2/1/01/001 -> طلبکاری به مشاوران
    payables_consultant, _ = Account.objects.get_or_create(
        code="210101",
        name="طلبکاری به مشاوران",
        defaults={
            "parent": liabilities,
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_CONSULTANT,
        },
    )

    # 2/1/01/002 -> حساب‌های جاری/دفتری اشخاص
    payables_persons, _ = Account.objects.get_or_create(
        code="210201",
        name="حساب‌های جاری/دفتری اشخاص",
        defaults={
            "parent": liabilities,
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.OTHER,
        },
    )

    # 2/1/01/003 -> طلبکاری به مشتریان
    payables_clients, _ = Account.objects.get_or_create(
        code="210301",
        name="طلبکاری به مشتریان",
        defaults={
            "parent": liabilities,
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_CLIENT,
        },
    )

    # 2/1/01/004 -> طلبکاری به بنگاه
    payables_offices, _ = Account.objects.get_or_create(
        code="210401",
        name="طلبکاری به بنگاه",
        defaults={
            "parent": liabilities,
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_OFFICE,
        },
    )

    # 2/1/01/005 -> طلبکاری به مدیر بنگاه
    payables_managers, _ = Account.objects.get_or_create(
        code="210501",
        name="طلبکاری به مدیر بنگاه",
        defaults={
            "parent": liabilities,
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_MANAGER,
        },
    )

    # 4/1/01/001 -> درآمد کمیسیون
    revenue_commission, _ = Account.objects.get_or_create(
        code="410101",
        name="درآمد کمیسیون",
        defaults={
            "parent": income,
            "account_type": Account.AccountType.INCOME,
            "category": Account.AccountCategory.REVENUE_COMMISSION,
        },
    )

    # 5/1/01/001 -> هزینه سهم مشاور
    expense_consultant_share, _ = Account.objects.get_or_create(
        code="510101",
        name="هزینه سهم مشاور",
        defaults={
            "parent": expenses,
            "account_type": Account.AccountType.EXPENSE,
            "category": Account.AccountCategory.EXPENSE_CONSULTANT_SHARE,
        },
    )

    # 5/1/01/002 -> هزینه سهم مدیر
    expense_manager_share, _ = Account.objects.get_or_create(
        code="510201",
        name="هزینه سهم مدیر",
        defaults={
            "parent": expenses,
            "account_type": Account.AccountType.EXPENSE,
            "category": Account.AccountCategory.EXPENSE_MANAGER_SHARE,
        },
    )

    return {
        "cash_bank": cash_parent,
        "receivables_commission": receivables_commission,
        "receivables_consultant": receivables_consultant,
        "receivables_office": receivables_office,
        "receivables_manager": receivables_manager,
        "payables_consultant": payables_consultant,
        "payables_persons": payables_persons,
        "payables_clients": payables_clients,
        "payables_offices": payables_offices,
        "payables_managers": payables_managers,
        "revenue_commission": revenue_commission,
        "expense_consultant_share": expense_consultant_share,
        "expense_manager_share": expense_manager_share,
    }


def ensure_client_account(client):
    """ایجاد/دریافت حساب بستانکاری از مشتری (کمیسیون دریافتنی)."""
    base_accounts = setup_chart_of_accounts()
    # کد ۶ کاراکتر: 12 + id چهاررقمی
    code = f"12{client.id:04d}"[:6]
    account, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            "name": f"{client.name} (مشتری)",
            "parent": base_accounts["receivables_commission"],
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_CLIENT,
        },
    )
    return account


def ensure_client_payable_account(client):
    """ایجاد/دریافت حساب طلبکاری به مشتری (پرداختنی به مشتری)."""
    base_accounts = setup_chart_of_accounts()
    # کد ۶ کاراکتر: 23 + id چهاررقمی
    code = f"23{client.id:04d}"[:6]
    account, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            "name": f"{client.name} - پرداختنی",
            "parent": base_accounts["payables_clients"],
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_CLIENT,
        },
    )
    return account


def ensure_consultant_accounts(consultant):
    """
    ایجاد/دریافت دو حساب برای مشاور:
    1. حساب طلبکاری (بدهی) - برای ردیابی بدهی ما به مشاور
    2. حساب بستانکاری (دارایی) - برای ردیابی طلب از مشاور
    """
    base_accounts = setup_chart_of_accounts()

    # 1. حساب طلبکاری - کد ۶ کاراکتر: 22 + id چهاررقمی
    payable_code = f"22{consultant.id:04d}"[:6]
    payable_acc, _ = Account.objects.get_or_create(
        code=payable_code,
        defaults={
            "name": f"{consultant.name} - پرداختنی",
            "parent": base_accounts["payables_consultant"],
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_CONSULTANT,
        },
    )

    # 2. حساب بستانکاری - کد ۶ کاراکتر: 32 + id چهاررقمی
    receivable_code = f"32{consultant.id:04d}"[:6]
    receivable_acc, _ = Account.objects.get_or_create(
        code=receivable_code,
        defaults={
            "name": f"{consultant.name} - بستانکاری",
            "parent": base_accounts["receivables_consultant"],
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_CONSULTANT,
        },
    )

    return payable_acc, receivable_acc


def ensure_consultant_receivable_account(consultant):
    """ایجاد/دریافت حساب بستانکاری از مشاور (طلب از مشاور)."""
    base_accounts = setup_chart_of_accounts()
    # کد ۶ کاراکتر: 32 + id چهاررقمی
    code = f"32{consultant.id:04d}"[:6]
    account, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            "name": f"{consultant.name} - بستانکاری",
            "parent": base_accounts["receivables_consultant"],
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_CONSULTANT,
        },
    )
    return account


def ensure_office_accounts(office):
    """
    ایجاد/دریافت حساب‌های بنگاه: بستانکاری از بنگاه و طلبکاری به بنگاه.
    Returns (receivable_account, payable_account).
    """
    base_accounts = setup_chart_of_accounts()
    # کد ۶ کاراکتر: 14/24 + id چهاررقمی
    rec_code = f"14{office.id:04d}"[:6]
    pay_code = f"24{office.id:04d}"[:6]

    rec, _ = Account.objects.get_or_create(
        code=rec_code,
        defaults={
            "name": f"{office.name} - بستانکاری",
            "parent": base_accounts["receivables_office"],
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_OFFICE,
        },
    )
    pay, _ = Account.objects.get_or_create(
        code=pay_code,
        defaults={
            "name": f"{office.name} - پرداختنی",
            "parent": base_accounts["payables_offices"],
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_OFFICE,
        },
    )
    return rec, pay


def ensure_office_manager_accounts(office):
    """
    ایجاد/دریافت حساب‌های مدیر بنگاه برای یک دفتر: بستانکاری و طلبکاری به مدیر.
    سهم مدیر از کمیسیون در پرداختنی ثبت می‌شود.
    Returns (receivable_account, payable_account).
    """
    base_accounts = setup_chart_of_accounts()
    name = f"مدیر - {office.name}"
    # کد ۶ کاراکتر: 15/25 + id چهاررقمی دفتر
    rec_code = f"15{office.id:04d}"[:6]
    pay_code = f"25{office.id:04d}"[:6]

    rec, _ = Account.objects.get_or_create(
        code=rec_code,
        defaults={
            "name": f"{name} - بستانکاری",
            "parent": base_accounts["receivables_manager"],
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.RECEIVABLE_MANAGER,
        },
    )
    pay, _ = Account.objects.get_or_create(
        code=pay_code,
        defaults={
            "name": f"{name} - پرداختنی",
            "parent": base_accounts["payables_managers"],
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.PAYABLE_MANAGER,
        },
    )
    return rec, pay


def ensure_personal_bookkeeping_account(user_or_name, identifier):
    """
    ایجاد/دریافت حساب 'دفتری' یا 'جاری' برای یک شخص.
    مطابق با کد 2/1/01/003 در نمودار حساب.
    """
    base_accounts = setup_chart_of_accounts()
    parent = base_accounts["payables_persons"]

    name = (
        user_or_name.full_name
        if hasattr(user_or_name, "full_name")
        else str(user_or_name)
    )

    # کد ۶ کاراکتر: 29 + چهار رقم از identifier
    code_suffix = str(identifier).replace("-", "")[:4].zfill(4)
    code = f"29{code_suffix}"[:6]
    account, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            "name": f"{name} - حساب دفتری",
            "parent": parent,
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.OTHER,
        },
    )
    return account
