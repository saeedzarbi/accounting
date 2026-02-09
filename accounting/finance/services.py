from decimal import Decimal

from django.db import transaction as db_transaction
from django.urls import reverse
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

# برچسب‌ها و ترتیب نمایش برای دفتر معامله
_CATEGORY_LABELS = {
    "receivable_client": "بدهی مشتریان به بنگاه",
    "payable_client": "بدهی بنگاه به مشتریان",
    "payable_consultant": "بدهی بنگاه به مشاوران",
    "payable_manager": "بدهی بنگاه به مدیر دفتر",
    "receivable_office": "بستانکاری از بنگاه",
    "payable_office": "بدهی بنگاه (طلبکاری به بنگاه)",
    "revenue_commission": "درآمد کمیسیون بنگاه",
    "expense_consultant_share": "هزینه سهم مشاوران",
    "expense_manager_share": "هزینه سهم مدیر دفتر",
}
_KIND_LABELS = {
    "receivable_client": "طلب از مشتری (بستانکاری)",
    "payable_client": "بدهی بنگاه به مشتری",
    "receivable_consultant": "طلب از مشاور",
    "payable_consultant": "پرداختنی به مشاور",
    "receivable_manager": "طلب از مدیر دفتر",
    "payable_manager": "پرداختنی به مدیر دفتر",
    "receivable_office": "بستانکاری از بنگاه",
    "payable_office": "طلبکاری به بنگاه",
    "revenue_commission": "درآمد کمیسیون بنگاه",
    "expense_consultant_share": "هزینه سهم مشاور",
    "expense_manager_share": "هزینه سهم مدیر دفتر",
    "cash_bank": "نقد و بانک",
    "other": "سایر",
}
_ORDER_KEYS = {
    "receivable_client": (0, 0),
    "payable_client": (0, 1),
    "revenue_commission": (0, 2),
    "receivable_consultant": (1, 0),
    "payable_consultant": (1, 1),
    "expense_consultant_share": (1, 2),
    "receivable_manager": (2, 0),
    "payable_manager": (2, 1),
    "expense_manager_share": (2, 2),
    "receivable_office": (3, 0),
    "payable_office": (3, 1),
    "cash_bank": (4, 0),
    "other": (5, 0),
}
_TRANSACTION_TARGET_CATEGORIES = (
    "receivable_client",
    "payable_client",
    "receivable_consultant",
    "payable_consultant",
    "receivable_manager",
    "payable_manager",
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


def get_deal_ledger_summary(deal, trx, document):
    """
    خلاصه دفتر معامله برای نمایش در صفحه: ردیف‌های دفتری، مانده‌ها، پرداخت‌ها، لیست حساب‌ها برای ثبت تراکنش.
    برمی‌گرداند یک دیکت مناسب برای context ویو.
    """
    entries_qs = (
        AccountEntry.objects.filter(transaction=trx)
        .select_related("account")
        .order_by("id")
    )
    payments_qs = (
        AccountPayment.objects.filter(deal=deal)
        .select_related("account", "created_by")
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
        created_by_name = ""
        if p.created_by_id:
            created_by_name = (p.created_by.get_full_name() or "").strip() or (
                getattr(p.created_by, "username", "") or ""
            ).strip()
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
                "created_by_name": created_by_name,
            }
        )
    category_totals = {
        k: {"label": v, "debit": 0.0, "credit": 0.0}
        for k, v in _CATEGORY_LABELS.items()
    }
    by_account = {}
    total_debit = 0.0
    total_credit = 0.0
    deal_accounts_list = []
    seen_account_ids = set()
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
        if acc.id not in seen_account_ids:
            seen_account_ids.add(acc.id)
            if category in _TRANSACTION_TARGET_CATEGORIES:
                deal_accounts_list.append(
                    {
                        "id": acc.id,
                        "code": acc.code or "",
                        "name": acc.name or "",
                        "category": category,
                    }
                )
        if acc.id not in by_account:
            kind_label = _KIND_LABELS.get(category, "سایر")
            payments_list = payments_by_account.get(acc.code or "", [])
            by_account[acc.id] = {
                "account_name": acc.name or "—",
                "account_code": acc.code or "—",
                "account_kind": kind_label,
                "counterpart_label": _CATEGORY_LABELS.get(category, ""),
                "debit": 0.0,
                "credit": 0.0,
                "has_payments": bool(payments_list),
                "settled_amount": 0.0,
                "remaining_amount": 0.0,
                "order_key": _ORDER_KEYS.get(category, (4, 0)),
                "_payments_list": payments_list,
                "_category": category,
            }
        by_account[acc.id]["debit"] += debit
        by_account[acc.id]["credit"] += credit
    total_received_from_clients = 0.0
    ledger_rows = []
    for _acc_id, b in by_account.items():
        payments_list = b.pop("_payments_list", [])
        category = b.pop("_category", "other")
        debit, credit = b["debit"], b["credit"]
        settled = (
            sum(
                x["amount"]
                for x in payments_list
                if x.get("direction_value") == "receive"
            )
            if debit > 0
            else sum(
                x["amount"] for x in payments_list if x.get("direction_value") == "pay"
            )
        )
        if category == "receivable_client":
            total_received_from_clients += settled
        balance = debit if debit > 0 else credit
        b["settled_amount"] = settled
        b["remaining_amount"] = max(0, balance - settled)
        ledger_rows.append(b)
    for row in ledger_rows:
        if row.get("account_kind") == "درآمد کمیسیون بنگاه":
            row["settled_amount"] = total_received_from_clients
            row["remaining_amount"] = max(
                0, float(row.get("credit") or 0) - total_received_from_clients
            )
    client_debit = (category_totals.get("receivable_client") or {}).get("debit", 0) or 0
    for row in ledger_rows:
        if (
            row.get("account_kind") == "درآمد کمیسیون بنگاه"
            and (not row.get("credit") or row["credit"] == 0)
            and client_debit > 0
        ):
            row["credit"] = client_debit
            row["remaining_amount"] = max(0, client_debit - row["settled_amount"])
    ledger_rows.sort(key=lambda r: (r["order_key"], r["account_code"]))
    remaining_by_account_id = {
        aid: by_account[aid]["remaining_amount"] for aid in by_account
    }
    for item in deal_accounts_list:
        item["remaining_amount"] = remaining_by_account_id.get(item["id"], 0.0)
    summary_items = []
    client_receivable_balance = 0.0
    for key, data in category_totals.items():
        if data["debit"] == 0 and data["credit"] == 0:
            continue
        balance = data["debit"] - data["credit"]
        summary_items.append(
            {
                "key": key,
                "label": data["label"],
                "debit": data["debit"],
                "credit": data["credit"],
                "balance": balance,
            }
        )
        if key == "receivable_client":
            client_receivable_balance = balance
    return {
        "entries": [],
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": trx.is_balanced(),
        "summary_items": summary_items,
        "client_receivable_balance": client_receivable_balance,
        "ledger_rows": ledger_rows,
        "payments_by_account": payments_by_account,
        "deal_accounts_list": deal_accounts_list,
        "sections": [],
    }


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

    این تابع فقط برای حساب‌های «طرف مستقیم» (طلب از مشتری/مشاور/مدیر/بنگاه یا پرداختنی به آن‌ها)
    فراخوانی می‌شود. به حساب درآمد کمیسیون بنگاه یا هزینه سهم مشاور/مدیر مستقیم تراکنش نمی‌زنیم:
    آن‌ها در سند کمیسیون به‌صورت دوطرفه (counterpart) با همان طلب/پرداختنی ثبت شده‌اند؛
    هنگام دریافت از مشتری فقط طلب کم و نقد زیاد می‌شود و درآمد کمیسیون تغییری نمی‌کند.

    منطق ثبت:
    - اگر حساب دارایی/بستانکاری باشد (مثلاً طلب از مشتری):
        - دریافت: بدهکار نقد و بانک، بستانکار حساب طرف (کاهش طلب).
        - پرداخت: بدهکار حساب طرف، بستانکار نقد و بانک.
    - اگر حساب بدهی/پرداختنی باشد (مثلاً پرداختنی به مشاور):
        - پرداخت: بدهکار حساب طرف، بستانکار نقد و بانک (کاهش بدهی).
        - دریافت: بدهکار نقد و بانک، بستانکار حساب طرف.
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

    منطق دوطرفه (حساب ↔ طرف مقابل):
    - طلب از مشتری (بدهکار) ↔ درآمد کمیسیون بنگاه (بستانکار). به درآمد کمیسیون مستقیم
      تراکنش نمی‌زنیم؛ فقط به طلب از مشتری (ثبت دریافت/پرداخت) تراکنش ثبت می‌شود.
    - هزینه سهم مشاور (بدهکار) ↔ پرداختنی به مشاور (بستانکار).
    - هزینه سهم مدیر (بدهکار) ↔ پرداختنی به مدیر (بستانکار).

    فرآیند:
    1. ایجاد تراکنش حسابداری
    2. برای هر ردیف کمیسیون مشتری: ثبت بدهکار طلب از مشتری و بستانکار درآمد کمیسیون (با counterpart_entry)
    3. برای هر مشاور: ثبت هزینه سهم مشاور و پرداختنی به مشاور (با counterpart_entry)
    4. برای مدیر دفتر: ثبت هزینه سهم مدیر و پرداختنی به مدیر (با counterpart_entry)
    5. ایجاد DealFinance و AccountingDocument
    """
    base_accounts = setup_chart_of_accounts()
    revenue_account = base_accounts["revenue_commission"]
    trx_date = _parse_deal_date(deal)

    with db_transaction.atomic():
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


def get_next_doc_number(doc_type):
    """شماره سند بعدی برای نوع داده‌شده (مثلاً رو-۱، در-۲، پا-۳)."""
    prefix = {
        AccountingDocument.DocType.JOURNAL: "رو",
        AccountingDocument.DocType.RECEIPT: "در",
        AccountingDocument.DocType.PAYMENT: "پا",
        AccountingDocument.DocType.TRANSFER: "ان",
        AccountingDocument.DocType.OTHER: "مت",
    }.get(doc_type, "سند")
    from django.db.models import Max

    last = (
        AccountingDocument.objects.filter(
            doc_type=doc_type, number__startswith=f"{prefix}-"
        )
        .aggregate(max_id=Max("id"))
        .get("max_id")
    )
    seq = (last or 0) + 1
    return f"{prefix}-{seq}"


def create_journal_document(date, description, rows):
    """
    ثبت سند روزنامه دستی.
    rows: لیست دیکت با کلیدهای account, debit, credit, description.
    برمی‌گرداند (transaction, document).
    """
    total_debit = sum(r["debit"] for r in rows)
    total_credit = sum(r["credit"] for r in rows)
    if total_debit != total_credit:
        raise ValueError(
            f"تراکنش متعادل نیست. جمع بدهکار: {total_debit}، جمع بستانکار: {total_credit}"
        )
    with db_transaction.atomic():
        trx = AccountingTransaction.objects.create(
            description=description or "سند روزنامه دستی",
            date=date,
        )
        for r in rows:
            AccountEntry.objects.create(
                transaction=trx,
                account=r["account"],
                debit=r["debit"],
                credit=r["credit"],
                description=r.get("description", ""),
            )
        number = get_next_doc_number(AccountingDocument.DocType.JOURNAL)
        doc = AccountingDocument.objects.create(
            doc_type=AccountingDocument.DocType.JOURNAL,
            number=number,
            date=date,
            description=description or "",
            transaction=trx,
            deal=None,
        )
    return trx, doc


def create_receipt_document(
    date, account, amount, method="", description="", user=None, receipt_file=None
):
    """
    ایجاد سند دریافت (دریافت از طرف حساب به نقد و بانک).
    برمی‌گرداند (payment, document).
    """
    from .utils import setup_chart_of_accounts

    setup_chart_of_accounts()
    number = get_next_doc_number(AccountingDocument.DocType.RECEIPT)
    with db_transaction.atomic():
        doc = AccountingDocument.objects.create(
            doc_type=AccountingDocument.DocType.RECEIPT,
            number=number,
            date=date,
            description=description or f"دریافت از {account.name}",
            transaction=None,
            deal=None,
        )
        payment = create_account_payment(
            document=doc,
            account=account,
            amount=amount,
            direction=AccountPayment.Direction.RECEIVE,
            date=date,
            method=method,
            description=description,
            user=user,
            receipt_file=receipt_file,
        )
        doc.transaction = payment.transaction
        doc.save(update_fields=["transaction"])
    return payment, doc


def create_payment_document(
    date, account, amount, method="", description="", user=None, receipt_file=None
):
    """
    ایجاد سند پرداخت (پرداخت از نقد و بانک به طرف حساب).
    برمی‌گرداند (payment, document).
    """
    from .utils import setup_chart_of_accounts

    setup_chart_of_accounts()
    number = get_next_doc_number(AccountingDocument.DocType.PAYMENT)
    with db_transaction.atomic():
        doc = AccountingDocument.objects.create(
            doc_type=AccountingDocument.DocType.PAYMENT,
            number=number,
            date=date,
            description=description or f"پرداخت به {account.name}",
            transaction=None,
            deal=None,
        )
        payment = create_account_payment(
            document=doc,
            account=account,
            amount=amount,
            direction=AccountPayment.Direction.PAY,
            date=date,
            method=method,
            description=description,
            user=user,
            receipt_file=receipt_file,
        )
        doc.transaction = payment.transaction
        doc.save(update_fields=["transaction"])
    return payment, doc
