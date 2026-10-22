from typing import Any, cast

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer, TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .serializers import RegisterSerializer, UserSerializer


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
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)

class LogoutView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(
        summary="Logout",
        description="Blacklist the presented refresh token so it can no longer be used",
        tags=['Authentication'],
        request=TokenBlacklistSerializer,
        responses={
            204: OpenApiResponse(description="Refresh token blacklisted"),
            400: OpenApiResponse(description="Refresh token missing or malformed"),
            401: OpenApiResponse(description="Invalid or expired refresh token"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = TokenBlacklistSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e
        return Response(status=status.HTTP_204_NO_CONTENT)

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = super().validate(attrs)
        user = self.user
        assert user is not None
        data['user_id'] = user.id
        data['email'] = user.email
        data['username'] = user.username
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
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)

class RegisterView(generics.CreateAPIView):
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
                    "error": {
                        "code": "validation_error",
                        "message": "The request payload is invalid.",
                        "details": {
                            "email": ["user with this email already exists."],
                            "password": ["Password fields didn't match."]
                        }
                    }
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
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    http_method_names = ('get', 'patch', 'head', 'options')
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self) -> User:
        return cast(User, self.request.user)

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
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self.retrieve(request, *args, **kwargs)

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
    def patch(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self.partial_update(request, *args, **kwargs)
