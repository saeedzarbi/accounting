from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path(
        "office/",
        views.OfficeFinanceView.as_view(),
        name="office-finance",
    ),
    path(
        "documents/",
        views.AccountingDocumentsListView.as_view(),
        name="accounting-documents-list",
    ),
    path(
        "chart-of-accounts/",
        views.ChartOfAccountsView.as_view(),
        name="chart-of-accounts",
    ),
    path(
        "account/<int:account_id>/ledger/",
        views.AccountLedgerView.as_view(),
        name="account-ledger",
    ),
    path(
        "journal/create/",
        views.JournalEntryCreateView.as_view(),
        name="journal-create",
    ),
    path(
        "receipt/create/",
        views.CreateVoucherView.as_view(),
        {"voucher_type": "receipt"},
        name="receipt-create",
    ),
    path(
        "payment/create/",
        views.CreateVoucherView.as_view(),
        {"voucher_type": "payment"},
        name="payment-create",
    ),
    path(
        "deal/<int:deal_id>/accounts/",
        views.DealAccountsView.as_view(),
        name="deal-accounts",
    ),
    path(
        "deal/<int:deal_id>/payment/",
        views.CreateDealAccountPaymentView.as_view(),
        name="deal-account-payment",
    ),
    path(
        "deal/<int:deal_id>/pending/<int:pending_id>/approve/",
        views.ApprovePendingDealPaymentView.as_view(),
        name="pending-deal-payment-approve",
    ),
    path(
        "deal/<int:deal_id>/pending/<int:pending_id>/reject/",
        views.RejectPendingDealPaymentView.as_view(),
        name="pending-deal-payment-reject",
    ),
    path(
        "receipt/<int:payment_id>/",
        views.ServePaymentReceiptView.as_view(),
        name="serve-payment-receipt",
    ),
]
