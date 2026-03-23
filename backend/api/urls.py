from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from api.views import (
    RegisterView, LoginView, MeView,
    LeadViewSet, WhatsAppWebhookView, MetaWebhookView,
    ChannelProviderViewSet,
    QuickReplyCategoryViewSet, QuickReplyViewSet,
    PlanViewSet, SubscriptionView,
    AgentConfigView, KnowledgeBaseView, KnowledgeBaseDetailView,
    TrainingDataExportView,
    InitialMessageMediaView, InitialMessageMediaDetailView,
    MessageTemplateViewSet,
    UploadMediaView,
    ServerConfigView,
    GalleryMediaViewSet,
    ContractViewSet,
    PublicContractView, PublicContractFillView, PublicContractSignView,
    GenericNoteViewSet,
    DogViewSet, LitterViewSet,
    DogHealthRecordViewSet, LitterHealthRecordViewSet,
)

router = DefaultRouter()
router.register(r'leads', LeadViewSet, basename='lead')
router.register(r'channels', ChannelProviderViewSet, basename='channel')
router.register(r'quick-reply-categories', QuickReplyCategoryViewSet, basename='quickreplycategory')
router.register(r'quick-replies', QuickReplyViewSet, basename='quickreply')
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'message-templates', MessageTemplateViewSet, basename='messagetemplate')
router.register(r'gallery', GalleryMediaViewSet, basename='gallery')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'notes', GenericNoteViewSet, basename='note')
router.register(r'dogs', DogViewSet, basename='dog')
router.register(r'litters', LitterViewSet, basename='litter')
router.register(r'dog-health', DogHealthRecordViewSet, basename='doghealthrecord')
router.register(r'litter-health', LitterHealthRecordViewSet, basename='litterhealthrecord')

urlpatterns = [
    path('', include(router.urls)),

    # Auth
    path('auth/register', RegisterView.as_view(), name='register'),
    path('auth/login', LoginView.as_view(), name='login'),
    path('auth/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me', MeView.as_view(), name='me'),

    # Subscription
    path('subscription/', SubscriptionView.as_view(), name='subscription'),

    # Webhooks
    path('webhooks/whatsapp/', WhatsAppWebhookView.as_view(), name='whatsapp_webhook'),
    path('webhooks/meta/', MetaWebhookView.as_view(), name='meta_webhook'),

    # RAG — Agent Config
    path('agent-config/', AgentConfigView.as_view(), name='agent_config'),

    # RAG — Knowledge Base
    path('knowledge-base/', KnowledgeBaseView.as_view(), name='knowledge_base'),
    path('knowledge-base/<str:entry_id>/', KnowledgeBaseDetailView.as_view(), name='knowledge_base_detail'),

    # RAG — Training Data Export
    path('training-data/export/', TrainingDataExportView.as_view(), name='training_data_export'),

    # Initial Message Media
    path('initial-media/', InitialMessageMediaView.as_view(), name='initial_media'),
    path('initial-media/<int:media_id>/', InitialMessageMediaDetailView.as_view(), name='initial_media_detail'),

    # Generic media upload (templates)
    path('upload-media/', UploadMediaView.as_view(), name='upload_media'),

    # Server configuration (read-only, for frontend info)
    path('server-config/', ServerConfigView.as_view(), name='server_config'),

    # Public contract endpoints (no authentication required)
    path('contracts/public/<uuid:token>/', PublicContractView.as_view(), name='contract_public'),
    path('contracts/public/<uuid:token>/fill/', PublicContractFillView.as_view(), name='contract_public_fill'),
    path('contracts/public/<uuid:token>/sign/', PublicContractSignView.as_view(), name='contract_public_sign'),
]
