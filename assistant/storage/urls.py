from django.urls import include, path
from rest_framework.routers import DefaultRouter

from assistant.storage.api.views import WikiDocumentViewSet
# from assistant.bot.api.views import BotViewSet

router = DefaultRouter()
router.register(r'documents', WikiDocumentViewSet)
# router.register(r'bots', BotViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
