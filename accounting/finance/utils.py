from .models import Account


def _get_or_create_account(code, name, parent, account_type, category):
    """یک حساب را با کد یکتا ایجاد یا برگردان (برای نمودار حساب‌ها)."""
    acc, _ = Account.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "parent": parent,
            "account_type": account_type,
            "category": category,
        },
    )
    return acc


def setup_chart_of_accounts():
    """
    ایجاد نمودار حساب‌های پایه بر اساس ساختار تعریف شده.
    پشتیبانی از بستانکاری و طلبکاری برای مشتریان، مشاوران، بنگاه و مدیر بنگاه.
    """
    # حساب‌های اصلی (ریشه)
    assets, _ = Account.objects.get_or_create(
        code="1",
        defaults={
            "name": "دارایی‌ها",
            "account_type": Account.AccountType.ASSET,
            "category": Account.AccountCategory.OTHER,
        },
    )
    liabilities, _ = Account.objects.get_or_create(
        code="2",
        defaults={
            "name": "بدهی‌ها",
            "account_type": Account.AccountType.LIABILITY,
            "category": Account.AccountCategory.OTHER,
        },
    )
    income, _ = Account.objects.get_or_create(
        code="4",
        defaults={
            "name": "درآمدها",
            "account_type": Account.AccountType.INCOME,
            "category": Account.AccountCategory.OTHER,
        },
    )
    expenses, _ = Account.objects.get_or_create(
        code="5",
        defaults={
            "name": "هزینه‌ها",
            "account_type": Account.AccountType.EXPENSE,
            "category": Account.AccountCategory.OTHER,
        },
    )

    # حساب‌های تفصیلی: (کد، نام، والد، نوع، دسته)
    sub_accounts = [
        (
            "110101",
            "نقد و بانک",
            assets,
            Account.AccountType.ASSET,
            Account.AccountCategory.CASH_BANK,
        ),
        (
            "110201",
            "بستانکاری کمیسیون از مشتریان",
            assets,
            Account.AccountType.ASSET,
            Account.AccountCategory.RECEIVABLE_CLIENT,
        ),
        (
            "110302",
            "بستانکاری از مشاوران",
            assets,
            Account.AccountType.ASSET,
            Account.AccountCategory.RECEIVABLE_CONSULTANT,
        ),
        (
            "110403",
            "بستانکاری از بنگاه",
            assets,
            Account.AccountType.ASSET,
            Account.AccountCategory.RECEIVABLE_OFFICE,
        ),
        (
            "110504",
            "بستانکاری از مدیر بنگاه",
            assets,
            Account.AccountType.ASSET,
            Account.AccountCategory.RECEIVABLE_MANAGER,
        ),
        (
            "210101",
            "طلبکاری به مشاوران",
            liabilities,
            Account.AccountType.LIABILITY,
            Account.AccountCategory.PAYABLE_CONSULTANT,
        ),
        (
            "210201",
            "حساب‌های جاری/دفتری اشخاص",
            liabilities,
            Account.AccountType.LIABILITY,
            Account.AccountCategory.OTHER,
        ),
        (
            "210301",
            "طلبکاری به مشتریان",
            liabilities,
            Account.AccountType.LIABILITY,
            Account.AccountCategory.PAYABLE_CLIENT,
        ),
        (
            "210401",
            "طلبکاری به بنگاه",
            liabilities,
            Account.AccountType.LIABILITY,
            Account.AccountCategory.PAYABLE_OFFICE,
        ),
        (
            "210501",
            "طلبکاری به مدیر بنگاه",
            liabilities,
            Account.AccountType.LIABILITY,
            Account.AccountCategory.PAYABLE_MANAGER,
        ),
        (
            "410101",
            "درآمد کمیسیون",
            income,
            Account.AccountType.INCOME,
            Account.AccountCategory.REVENUE_COMMISSION,
        ),
        (
            "510101",
            "هزینه سهم مشاور",
            expenses,
            Account.AccountType.EXPENSE,
            Account.AccountCategory.EXPENSE_CONSULTANT_SHARE,
        ),
        (
            "510201",
            "هزینه سهم مدیر",
            expenses,
            Account.AccountType.EXPENSE,
            Account.AccountCategory.EXPENSE_MANAGER_SHARE,
        ),
    ]
    created = {}
    for code, name, parent, acc_type, category in sub_accounts:
        created[code] = _get_or_create_account(code, name, parent, acc_type, category)

    return {
        "cash_bank": created["110101"],
        "receivables_commission": created["110201"],
        "receivables_consultant": created["110302"],
        "receivables_office": created["110403"],
        "receivables_manager": created["110504"],
        "payables_consultant": created["210101"],
        "payables_persons": created["210201"],
        "payables_clients": created["210301"],
        "payables_offices": created["210401"],
        "payables_managers": created["210501"],
        "revenue_commission": created["410101"],
        "expense_consultant_share": created["510101"],
        "expense_manager_share": created["510201"],
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
