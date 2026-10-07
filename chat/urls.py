from django.urls import path
from .views import ConversationListView, ConversationDetailView, ChatView

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<uuid:uuid>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/<uuid:conversation_id>/', ChatView.as_view(), name='chat-with-conversation'),
]