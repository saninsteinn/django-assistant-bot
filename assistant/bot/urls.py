from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from assistant.bot.api.views import BotViewSet, DialogViewSet, MessageViewSet

router = DefaultRouter()
router.register(r'bots', BotViewSet)
router.register(r'dialogs', DialogViewSet, basename='dialog')

dialogs_router = routers.NestedDefaultRouter(router, r'dialogs', lookup='dialog')
dialogs_router.register(r'messages', MessageViewSet, basename='dialog-messages')

# router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(dialogs_router.urls)),
]
