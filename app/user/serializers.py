from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the users object."""

    class Meta:
        model = get_user_model()
        fields = ("email", "password", "name", "tenant")
        read_only_fields = ["id"]
        extra_kwargs = {
            "password": {"write_only": True, "min_length": 5},
            "tenant": {"required": True, "allow_null": False},
        }

    def create(self, validated_data):
        """Create a new user with encrypted password and return it."""
        return get_user_model().objects.create_user(**validated_data)


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("email", "name", "tenant")
        read_only_fields = ("email", "tenant")


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(min_length=5, write_only=True)
