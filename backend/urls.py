from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/chat/', include('chat.urls_v1')),
    path('api/v1/health/', include('health.urls')),

    # Contract documentation
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Legacy documentation, removed with the legacy routes in P1.9
    path('api/schema/', SpectacularAPIView.as_view(), name='legacy-schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='legacy-schema'), name='legacy-swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='legacy-schema'), name='legacy-redoc'),
]