from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from api.views import (
    RegisterView, LoginView, MeView,
    LeadViewSet, WhatsAppWebhookView,
    ChannelProviderViewSet, QuickReplyViewSet,
    PlanViewSet, SubscriptionView,
)

router = DefaultRouter()
router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'channels', ChannelProviderViewSet, basename='channel')
router.register(r'quick-replies', QuickReplyViewSet, basename='quickreply')
router.register(r'plans', PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),

    # Auth
    path('auth/register', RegisterView.as_view(), name='register'),
    path('auth/login', LoginView.as_view(), name='login'),
    path('auth/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me', MeView.as_view(), name='me'),

    # Subscription
    path('subscription/', SubscriptionView.as_view(), name='subscription'),

    # Webhook
    path('webhooks/whatsapp/', WhatsAppWebhookView.as_view(), name='whatsapp_webhook'),
]
