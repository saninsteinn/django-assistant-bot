"""assistant URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from rest_framework.authentication import TokenAuthentication

# from assistant.admin.admin import admin_site
from assistant.bot.views import TelegramAssistantBotView


class BothHttpAndHttpsSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request, public)
        schema.schemes = ["https", "http"]
        return schema


schema_view = get_schema_view(
    openapi.Info(
        title="Assistant API",
        default_version='v1',
        description="API documentation for AI Assistant",
    ),
    generator_class=BothHttpAndHttpsSchemaGenerator,
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[TokenAuthentication],
)


urlpatterns = [
    # path('admin/', admin_site.urls),
    # path('admins/', admin.site.urls),
    path('telegram/<str:codename>/', TelegramAssistantBotView.as_view(), name='telegram_bot'),
    path('api/v1/', include('assistant.storage.urls')),
    path('api/v1/', include('assistant.bot.urls')),
    path('api/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # path('api-token-auth/', obtain_auth_token, name='api_token_auth'),

]
