from django.urls import path

from . import views

urlpatterns = [
    path(
        "<int:deal_id>/generate-contract/",
        views.generate_contract_view,
        name="generate_contract",
    ),
    path("<int:deal_id>/property/", views.deal_property_view, name="deal_property"),
    path("<int:pk>/edit/", views.ContractUpdateView.as_view(), name="contract_edit"),
    path("<int:pk>/print/", views.contract_print_view, name="contract_print"),
    path("<int:pk>/pdf/", views.contract_pdf_view, name="contract_pdf"),
    path("create", views.create_deal_view, name="create_deal_view"),
    path("<int:deal_id>/edit-deal/", views.edit_deal_view, name="edit_deal"),
    path("clients/search/", views.client_search_api, name="client_search_api"),
    path(
        "clients/quick-create/", views.quick_create_client, name="quick_create_client"
    ),
    path("<int:pk>/finalize/", views.finalize_contract_view, name="finalize_contract"),
    path(
        "<int:pk>/save-template/",
        views.save_contract_as_template_view,
        name="save_contract_as_template",
    ),
]
