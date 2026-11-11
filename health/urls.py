from django.urls import path

from .views import HealthView, LivenessView

urlpatterns = [
    path('', HealthView.as_view(), name='health'),
    path('live/', LivenessView.as_view(), name='health-live'),
]
