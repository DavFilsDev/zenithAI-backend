from django.contrib import admin
from .models import Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('role', 'content', 'created_at')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'message_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('title', 'user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessageInline]
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Number of Messages'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'short_content', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content', 'conversation__title', 'conversation__user__email')
    readonly_fields = ('created_at',)
    
    def short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'