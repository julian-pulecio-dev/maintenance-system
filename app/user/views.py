from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import PasswordResetToken
from .serializers import ForgotPasswordSerializer, MeSerializer, UserSerializer


class BaseUserView:
    serializer_class = UserSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]


class MeView(BaseUserView, generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer
    http_method_names = ["get", "patch", "head", "options"]


class ListUsersView(BaseUserView, generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
    queryset = get_user_model().objects.all()


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=ForgotPasswordSerializer, responses={200: None})
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user_model = get_user_model()

        try:
            user = user_model.objects.get(email=email)
        except user_model.DoesNotExist:
            return Response(status=status.HTTP_200_OK)

        reset_token = PasswordResetToken.objects.create(user=user)

        send_mail(
            subject="Password Reset Request",
            message=(
                f"You requested a password reset.\n\n"
                f"Use the following token to reset your password:\n\n"
                f"{reset_token.token}\n\n"
                f"Token expires in {PasswordResetToken.TOKEN_EXPIRY_HOURS} hour(s).\n\n"
                f"If you did not request this, please ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        return Response(status=status.HTTP_200_OK)
