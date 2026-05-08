from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import PasswordResetToken
from .serializers import (
    ForgotPasswordSerializer,
    MeSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)


class BaseUserView:
    serializer_class = UserSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]


class MeView(BaseUserView, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]


class ListUsersView(BaseUserView, generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
    queryset = get_user_model().objects.all()


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(request=ForgotPasswordSerializer)
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        tenant = serializer.validated_data["tenant"]

        try:
            user = get_user_model().objects.get(email=email, tenant=tenant)
            reset_token = PasswordResetToken.objects.create(user=user)
            send_mail(
                subject="Password reset request",
                message=(
                    f"Use the following token to reset your password:\n\n"
                    f"{reset_token.token}\n\n"
                    f"This token expires in {PasswordResetToken.TOKEN_EXPIRY_HOURS} hour(s)."
                ),
                from_email=None,
                recipient_list=[user.email],
            )
        except get_user_model().DoesNotExist:
            pass

        return Response(
            {"detail": "If an account with that email exists, a reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
