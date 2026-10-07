from django.urls import path
from .views import ConversationListView, ConversationDetailView, MessageListCreateView

app_name = 'chat_v1'

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<uuid:uuid>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/messages/', MessageListCreateView.as_view(), name='conversation-messages'),
]