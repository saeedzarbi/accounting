from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path(
        "documents/",
        views.AccountingDocumentsListView.as_view(),
        name="accounting-documents-list",
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
        "receipt/<int:payment_id>/",
        views.ServePaymentReceiptView.as_view(),
        name="serve-payment-receipt",
    ),
]
