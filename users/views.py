from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, RegisterSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class CustomTokenRefreshView(TokenRefreshView):
    
    @extend_schema(
        summary="Refresh access token",
        description="Get a new access token using a valid refresh token",
        tags=['Authentication'],
        responses={
            200: OpenApiResponse(description="New access token generated"),
            401: OpenApiResponse(description="Invalid or expired refresh token"),
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = self.user.id
        data['email'] = self.user.email
        data['username'] = self.user.username
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
    @extend_schema(
        summary="Login - Get JWT Tokens",
        description="Authenticate with email/password to receive access and refresh tokens",
        tags=['Authentication'],
        request=TokenObtainPairSerializer,
        responses={
            200: OpenApiResponse(description="Login successful"),
            401: OpenApiResponse(description="Invalid credentials"),
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer
    
    @extend_schema(
        summary="Register new user",
        description="Create a new user account with email and password",
        tags=['Authentication'],
        request=RegisterSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiExample(
                'Validation Error',
                value={
                    "email": ["user with this email already exists."],
                    "password": ["Password fields didn't match."]
                }
            ),
        },
        examples=[
            OpenApiExample(
                'Valid Registration',
                value={
                    "email": "user@example.com",
                    "username": "newuser",
                    "password": "SecurePass123!",
                    "password2": "SecurePass123!"
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    def get_object(self):
        return self.request.user
    
    @extend_schema(
        summary="Get user profile",
        description="Retrieve the profile of the currently authenticated user",
        tags=['Users'],
        responses={
            200: OpenApiResponse(
                response=UserSerializer,
                description="Profile retrieved successfully"
            ),
            401: OpenApiResponse(
                description="Authentication credentials not provided or invalid"
            ),
        },
        examples=[
            OpenApiExample(
                'Successful Response',
                value={
                    'id': 1,
                    'email': 'user@example.com',
                    'username': 'johndoe'
                },
                response_only=True,
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Update user profile",
        description="Update the authenticated user's profile information",
        tags=['Users'],
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Invalid data provided"),
            401: OpenApiResponse(description="Authentication required"),
        },
        examples=[
            OpenApiExample(
                'Update Request',
                value={
                    'username': 'newusername',
                    'email': 'newemail@example.com'
                },
                request_only=True,
            ),
        ]
    )
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
    
    @extend_schema(
        summary="Partially update user profile",
        description="Partially update the authenticated user's profile information",
        tags=['Users'],
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description="Invalid data provided"),
            401: OpenApiResponse(description="Authentication required"),
        }
    )
    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)