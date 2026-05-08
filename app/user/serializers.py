from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from tenant.models import Tenant
from .models import PasswordResetToken

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "password", "name", "tenant")
        read_only_fields = ("id",)
        extra_kwargs = {
            "password": {"write_only": True, "min_length": 5},
            "tenant": {"required": True, "allow_null": False},
        }

    def validate(self, attrs):
        if User.objects.filter(tenant=attrs.get("tenant"), email=attrs.get("email")).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "name", "tenant", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "email", "tenant", "is_active", "created_at", "updated_at")


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    tenant = serializers.PrimaryKeyRelatedField(queryset=Tenant.objects.all())


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(min_length=5, write_only=True)

    def validate_token(self, value):
        try:
            reset_token = PasswordResetToken.objects.select_related("user").get(token=value)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid or expired token.")

        if not reset_token.is_valid:
            raise serializers.ValidationError("Invalid or expired token.")

        self._reset_token = reset_token
        return value

    def save(self):
        reset_token = self._reset_token
        user = reset_token.user
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        reset_token.mark_as_used()


class TenantAwareTokenSerializer(TokenObtainPairSerializer):
    tenant = serializers.PrimaryKeyRelatedField(
        queryset=Tenant.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs[self.username_field],
            password=attrs["password"],
            tenant=attrs.get("tenant"),
        )

        if not user:
            raise AuthenticationFailed()

        refresh = self.get_token(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }