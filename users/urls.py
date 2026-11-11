from django.urls import path

from .views import CustomTokenObtainPairView, CustomTokenRefreshView, LogoutView, RegisterView, UserProfileView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path('logout/', LogoutView.as_view(), name='logout'),
]
