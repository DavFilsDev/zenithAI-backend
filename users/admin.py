from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserProfile

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'username', 'is_premium', 'is_staff', 'is_active')
    list_filter = ('is_premium', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Account info', {'fields': ('is_premium',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'is_premium'),
        }),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'language', 'created_at')
    list_filter = ('theme', 'language')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')