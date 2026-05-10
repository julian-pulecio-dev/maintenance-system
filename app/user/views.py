from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView

from tenant.permissions import TenantHeaderRequired
from .models import PasswordResetToken
from .serializers import (
    ForgotPasswordSerializer,
    MeSerializer,
    ResetPasswordSerializer,
    TenantAwareTokenSerializer,
    UserSerializer,
)


@extend_schema(
    request=TenantAwareTokenSerializer,
    summary="Obtain JWT token pair",
    description=(
        "Authenticates a user and returns an `access` token and a `refresh` "
        "token.\n\n"
        "**Required fields:**\n"
        "- `email` — Registered email address.\n"
        "- `password` — Account password.\n\n"
        "**Header:**\n"
        "- `X-Tenant-ID` — Required for regular users. Superusers can omit "
        "this header.\n\n"
        "The `access` token should be sent as "
        "`Authorization: Bearer <token>` on all subsequent requests. "
        "It expires after a short period — use the `refresh` token at "
        "`POST /api/token/refresh/` to obtain a new one without "
        "re-authenticating.\n\n"
        "**Errors:**\n"
        "- `400` — Invalid `X-Tenant-ID` format.\n"
        "- `401` — Wrong credentials, or user does not belong to the "
        "specified tenant."
    ),
)
class TenantAwareTokenObtainPairView(TokenObtainPairView):
    serializer_class = TenantAwareTokenSerializer


class BaseUserView:
    serializer_class = UserSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(
    summary="Register a new user",
    description=(
        "Creates a new user account associated with the tenant specified in "
        "the `X-Tenant-ID` header. No authentication is required — this "
        "endpoint is public.\n\n"
        "**Required fields:**\n"
        "- `email` — Must be unique within the tenant.\n"
        "- `password` — Minimum 8 characters.\n"
        "- `name` — Display name.\n\n"
        "**Header:**\n"
        "- `X-Tenant-ID` — Required. Associates the new user with a tenant.\n\n"
        "**Errors:**\n"
        "- `400` — Email already registered in this tenant, password too "
        "short, or missing required fields.\n"
        "- `403` — Missing `X-Tenant-ID` header."
    ),
)
class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny, TenantHeaderRequired]

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get current user profile",
        description=(
            "Returns the profile of the authenticated user (the user "
            "identified by the JWT token).\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token."
        ),
    ),
    partial_update=extend_schema(
        summary="Update current user profile",
        description=(
            "Updates one or more fields of the authenticated user's own "
            "profile. All fields are optional.\n\n"
            "**Editable fields:** `name`, `password`.\n\n"
            "**Errors:**\n"
            "- `400` — Validation error (e.g., password too short).\n"
            "- `401` — Missing or invalid JWT token."
        ),
    ),
    destroy=extend_schema(
        summary="Delete current user account",
        description=(
            "Permanently deletes the authenticated user's account. This "
            "action is irreversible.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token."
        ),
    ),
)
class MeView(BaseUserView, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]


@extend_schema(
    summary="List users in the current tenant",
    description=(
        "Returns all users that belong to the tenant specified in the "
        "`X-Tenant-ID` header.\n\n"
        "**Errors:**\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header."
    ),
)
class ListUsersView(generics.ListAPIView):
    serializer_class = UserSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def get_queryset(self):
        return get_user_model().objects.filter(tenant=self.request.tenant)


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        request=ForgotPasswordSerializer,
        summary="Request a password reset",
        description=(
            "Sends a password reset token to the user's registered email "
            "address. For security, the response is always `200 OK` "
            "regardless of whether the email exists, preventing user "
            "enumeration.\n\n"
            "**Required fields:**\n"
            "- `email` — The registered email address.\n\n"
            "**Header:**\n"
            "- `X-Tenant-ID` — Required to scope the lookup to the correct "
            "tenant.\n\n"
            "The emailed token is valid for 1 hour. Pass it to "
            "`POST /api/user/reset-password/` to set a new password.\n\n"
            "**Errors:**\n"
            "- `400` — Invalid email format or missing field."
        ),
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        tenant = request.tenant

        try:
            user = get_user_model().objects.get(email=email, tenant=tenant)
            reset_token = PasswordResetToken.objects.create(user=user)
            send_mail(
                subject="Password reset request",
                message=(
                    f"Use the following token to reset your password:\n\n"
                    f"{reset_token.token}\n\n"
                    f"This token expires in "
                    f"{PasswordResetToken.TOKEN_EXPIRY_HOURS} hour(s)."
                ),
                from_email=None,
                recipient_list=[user.email],
            )
        except get_user_model().DoesNotExist:
            pass

        return Response(
            {
                "detail": (
                    "If an account with that email exists, "
                    "a reset link has been sent."
                )
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        request=ResetPasswordSerializer,
        summary="Reset password with token",
        description=(
            "Sets a new password using a token previously issued by "
            "`POST /api/user/forgot-password/`. The token is single-use "
            "and expires after 1 hour. On success, all other pending reset "
            "tokens for the user are invalidated.\n\n"
            "**Required fields:**\n"
            "- `token` — UUID token received via email.\n"
            "- `password` — New password (minimum 8 characters).\n\n"
            "**Errors:**\n"
            "- `400` — Token not found, already used, expired, password too "
            "short, or missing required fields."
        ),
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
