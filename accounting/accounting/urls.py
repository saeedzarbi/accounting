from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny
from users.views import pwa_manifest

schema_view = get_schema_view(
    openapi.Info(
        title="API Schema RealEstate-Accounting",
        default_version="v1",
        description="API documentation",
    ),
    public=True,
    permission_classes=[AllowAny],
)

urlpatterns = [
    path("manifest.json", pwa_manifest),
    path("", RedirectView.as_view(url="/login/", permanent=False)),
    path("manager/", admin.site.urls),
    path("deals/", include("transactions.urls")),
    path("finance/", include("finance.urls")),
    path("", include("users.urls")),
    path(
        "api/swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
