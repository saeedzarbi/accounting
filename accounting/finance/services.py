from decimal import Decimal

from django.db import transaction as db_transaction
from transactions.models import DealClientCommission

from .models import (
    Account,
    AccountEntry,
    AccountingDocument,
    AccountingTransaction,
    AccountPayment,
    DealFinance,
)

# دسته‌ی حساب برای تشخیص طلب مشتری و درآمد کمیسیون
from .utils import (
    ensure_client_account,
    ensure_consultant_accounts,
    ensure_office_manager_accounts,
    setup_chart_of_accounts,
)


def repair_deal_ledger_revenue(deal, trx):
    """
    اگر در تراکنش سند کمیسیون، طلب از مشتریان (بدهکار) وجود دارد ولی معادل
    درآمد کمیسیون بنگاه (بستانکار) ثبت نشده یا ناقص است، ردیف‌های بستانکار درآمد را اضافه می‌کند.
    """
    base_accounts = setup_chart_of_accounts()
    revenue_account = base_accounts["revenue_commission"]
    receivable_client_category = Account.AccountCategory.RECEIVABLE_CLIENT

    entries = AccountEntry.objects.filter(transaction=trx).select_related("account")
    client_debit_total = Decimal("0")
    revenue_credit_total = Decimal("0")
    for e in entries:
        acc = e.account
        if not acc:
            continue
        if getattr(acc, "category", None) == receivable_client_category:
            client_debit_total += Decimal(str(e.debit or 0))
        if acc.id == revenue_account.id:
            revenue_credit_total += Decimal(str(e.credit or 0))

    missing = client_debit_total - revenue_credit_total
    if missing <= 0:
        return
    with db_transaction.atomic():
        AccountEntry.objects.create(
            transaction=trx,
            account=revenue_account,
            debit=Decimal("0"),
            credit=missing,
            description=f"اصلاح معادل درآمد کمیسیون بنگاه (معامله {deal.id})",
        )


def _parse_deal_date(deal):
    if deal.date:
        try:
            parts = str(deal.date).replace("/", "-").split("-")
            if len(parts) >= 3:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 1500:
                    from jdatetime import date as jdate

                    return jdate(y, m, d).togregorian()
                return __import__("datetime").date(y, m, d)
        except Exception:
            pass
    return (
        deal.created_at.date()
        if deal.created_at
        else __import__("datetime").date.today()
    )


def create_account_payment(
    *,
    document: AccountingDocument | None,
    account: Account,
    amount,
    direction: AccountPayment.Direction,
    date=None,
    method: str = "",
    description: str = "",
    user=None,
    receipt_file=None,
):
    """
    ایجاد یک پرداخت/دریافت برای یک حساب مشخص و ثبت آن در دفتر روزنامه.

    منطق کلی:
    - اگر حساب «دارایی/بستانکاری» باشد (مثلاً بستانکاری از مشتری):
        - دریافت از طرف حساب: بدهکار نقد و بانک، بستانکار حساب طرف.
        - پرداخت به طرف حساب: بدهکار حساب طرف، بستانکار نقد و بانک.
    - اگر حساب «بدهی/پرداختنی» باشد (مثلاً پرداختنی به مشاور):
        - پرداخت به طرف حساب: بدهکار حساب طرف، بستانکار نقد و بانک.
        - دریافت از طرف حساب: بدهکار نقد و بانک، بستانکار حساب طرف.
    """

    base_accounts = setup_chart_of_accounts()
    cash_account = base_accounts["cash_bank"]

    amount = Decimal(str(amount or 0))
    if amount <= 0:
        raise ValueError("مبلغ پرداخت/دریافت باید بزرگ‌تر از صفر باشد.")

    if date is None:
        if document and document.date:
            date = document.date
        else:
            date = __import__("datetime").date.today()

    with db_transaction.atomic():
        trx = AccountingTransaction.objects.create(
            description=description or f"{direction.label} بابت حساب {account.name}",
            date=date,
        )

        is_asset = account.account_type in (
            Account.AccountType.ASSET,
            Account.AccountType.EXPENSE,
        )

        def _link_counterpart(e1, e2):
            e1.counterpart_entry = e2
            e1.save(update_fields=["counterpart_entry"])
            e2.counterpart_entry = e1
            e2.save(update_fields=["counterpart_entry"])

        # جهت ثبت از دید بنگاه
        if direction == AccountPayment.Direction.RECEIVE:
            if is_asset:
                # دریافت از مشتری/سایرین: کاهش بستانکاری، افزایش نقد و بانک
                e_cash = AccountEntry.objects.create(
                    transaction=trx,
                    account=cash_account,
                    debit=amount,
                    credit=Decimal("0"),
                    description=description or "دریافت وجه از طرف حساب",
                )
                e_acc = AccountEntry.objects.create(
                    transaction=trx,
                    account=account,
                    debit=Decimal("0"),
                    credit=amount,
                    description=description or "تسویه/کاهش بستانکاری طرف حساب",
                )
                _link_counterpart(e_cash, e_acc)
            else:
                # دریافت از حساب بدهی (مثلاً وقتی طرف بدهی خود را بازمی‌گرداند)
                e_acc = AccountEntry.objects.create(
                    transaction=trx,
                    account=account,
                    debit=amount,
                    credit=Decimal("0"),
                    description=description or "کاهش بدهی بنگاه به طرف حساب",
                )
                e_cash = AccountEntry.objects.create(
                    transaction=trx,
                    account=cash_account,
                    debit=Decimal("0"),
                    credit=amount,
                    description=description or "دریافت وجه از طرف حساب",
                )
                _link_counterpart(e_acc, e_cash)
        else:  # PAY
            if is_asset:
                # پرداخت به صاحب حساب دارایی: افزایش بستانکاری، کاهش نقد و بانک
                e_acc = AccountEntry.objects.create(
                    transaction=trx,
                    account=account,
                    debit=amount,
                    credit=Decimal("0"),
                    description=description or "افزایش بستانکاری طرف حساب",
                )
                e_cash = AccountEntry.objects.create(
                    transaction=trx,
                    account=cash_account,
                    debit=Decimal("0"),
                    credit=amount,
                    description=description or "پرداخت وجه به طرف حساب",
                )
                _link_counterpart(e_acc, e_cash)
            else:
                # پرداخت به حساب بدهی (پرداختنی به مشاور/مدیر/مشتری)
                e_acc = AccountEntry.objects.create(
                    transaction=trx,
                    account=account,
                    debit=amount,
                    credit=Decimal("0"),
                    description=description or "تسویه بدهی به طرف حساب",
                )
                e_cash = AccountEntry.objects.create(
                    transaction=trx,
                    account=cash_account,
                    debit=Decimal("0"),
                    credit=amount,
                    description=description or "پرداخت وجه به طرف حساب",
                )
                _link_counterpart(e_acc, e_cash)

        payment = AccountPayment.objects.create(
            document=document,
            deal=document.deal if document and document.deal_id else None,
            account=account,
            transaction=trx,
            direction=direction,
            amount=amount,
            date=date,
            method=method,
            description=description or "",
            created_by=user,
        )
        if receipt_file:
            payment.receipt_file = receipt_file
            payment.save(update_fields=["receipt_file"])

        return payment


def create_deal_ledger_entry(deal):
    """
    ثبت سند حسابداری معامله: درآمد کمیسیون از مشتریان، تسهیم به مشاوران و مدیر دفتر.

    فرآیند:
    1. ایجاد تراکنش حسابداری
    2. برای هر ردیف کمیسیون مشتری (`DealClientCommission`): ثبت بدهکار از حساب بستانکاری همان
       مشتری به درآمد کمیسیون.
    3. برای هر مشاور: ثبت هزینه سهم مشاور و پرداختنی به مشاور
    4. برای مدیر دفتر: ثبت هزینه سهم مدیر و پرداختنی به مدیر
    5. ایجاد DealFinance و AccountingDocument
    """
    base_accounts = setup_chart_of_accounts()
    revenue_account = base_accounts["revenue_commission"]
    trx_date = _parse_deal_date(deal)

    with db_transaction.atomic():
        # ایجاد تراکنش حسابداری
        trx = AccountingTransaction.objects.create(
            description=f"ثبت سند درآمد و تسهیم کمیسیون معامله {deal.id}",
            date=trx_date,
        )

        client_commissions = (
            DealClientCommission.objects.filter(deal=deal, amount__gt=0)
            .select_related("client")
            .order_by("id")
        )
        for cc in client_commissions:
            client_acc = ensure_client_account(cc.client)
            amount = Decimal(str(cc.amount))
            role_label = (
                "خریدار"
                if cc.role == DealClientCommission.ClientRole.BUYER
                else "فروشنده"
            )
            # بدهکار: حساب بستانکاری مشتری (طلب بنگاه از مشتری)
            entry_receivable = AccountEntry.objects.create(
                transaction=trx,
                account=client_acc,
                debit=amount,
                credit=Decimal("0"),
                description=f"کمیسیون مشتری {cc.client.name} ({role_label})",
            )
            # بستانکار: درآمد کمیسیون بنگاه (طرف مقابل همان طلب مشتری)
            entry_revenue = AccountEntry.objects.create(
                transaction=trx,
                account=revenue_account,
                debit=Decimal("0"),
                credit=amount,
                description=f"درآمد کمیسیون از مشتری {cc.client.name} ({role_label})",
            )
            entry_receivable.counterpart_entry = entry_revenue
            entry_receivable.save(update_fields=["counterpart_entry"])
            entry_revenue.counterpart_entry = entry_receivable
            entry_revenue.save(update_fields=["counterpart_entry"])

        # ثبت تسهیم مشاوران
        consultant_splits = deal.splits.filter(role="consultant")
        expense_consultant = base_accounts["expense_consultant_share"]
        for split in consultant_splits:
            if split.consultant and split.amount and split.amount > 0:
                payable_acc, receivable_acc = ensure_consultant_accounts(
                    split.consultant
                )
                amount = Decimal(str(split.amount))
                # بدهکار: هزینه سهم مشاور
                entry_expense = AccountEntry.objects.create(
                    transaction=trx,
                    account=expense_consultant,
                    debit=amount,
                    credit=Decimal("0"),
                    description=f"هزینه سهم مشاور {split.consultant.name}",
                )
                # بستانکار: پرداختنی به مشاور (طرف مقابل همان هزینه)
                entry_payable = AccountEntry.objects.create(
                    transaction=trx,
                    account=payable_acc,
                    debit=Decimal("0"),
                    credit=amount,
                    description=f"سهم مشاور {split.consultant.name} (طبق توافق)",
                )
                entry_expense.counterpart_entry = entry_payable
                entry_expense.save(update_fields=["counterpart_entry"])
                entry_payable.counterpart_entry = entry_expense
                entry_payable.save(update_fields=["counterpart_entry"])

        # ثبت تسهیم مدیر دفتر
        manager_splits = deal.splits.filter(role="manager")
        if manager_splits.exists() and deal.office:
            _, manager_payable_acc = ensure_office_manager_accounts(deal.office)
            expense_manager = base_accounts["expense_manager_share"]
            total_manager_amount = sum(
                Decimal(str(s.amount or 0)) for s in manager_splits
            )
            if total_manager_amount > 0:
                # بدهکار: هزینه سهم مدیر
                entry_expense_mgr = AccountEntry.objects.create(
                    transaction=trx,
                    account=expense_manager,
                    debit=total_manager_amount,
                    credit=Decimal("0"),
                    description=f"هزینه سهم مدیر دفتر - معامله {deal.id}",
                )
                # بستانکار: پرداختنی به مدیر (طرف مقابل همان هزینه)
                entry_payable_mgr = AccountEntry.objects.create(
                    transaction=trx,
                    account=manager_payable_acc,
                    debit=Decimal("0"),
                    credit=total_manager_amount,
                    description=f"سهم مدیر دفتر - معامله {deal.id}",
                )
                entry_expense_mgr.counterpart_entry = entry_payable_mgr
                entry_expense_mgr.save(update_fields=["counterpart_entry"])
                entry_payable_mgr.counterpart_entry = entry_expense_mgr
                entry_payable_mgr.save(update_fields=["counterpart_entry"])

        # بررسی تعادل تراکنش
        if not trx.is_balanced():
            raise ValueError(
                f"تراکنش متعادل نیست! بدهکار: {trx.get_total_debit()}, "
                f"بستانکار: {trx.get_total_credit()}"
            )

        # ایجاد DealFinance
        DealFinance.objects.create(deal=deal, income_transaction=trx)

        # ایجاد AccountingDocument
        AccountingDocument.objects.create(
            doc_type=AccountingDocument.DocType.COMMISSION,
            number=f"کم-{deal.id}",
            date=trx_date,
            description=trx.description,
            transaction=trx,
            deal=deal,
        )

    return trx
