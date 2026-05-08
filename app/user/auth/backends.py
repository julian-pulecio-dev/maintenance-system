from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class TenantAwareBackend(BaseBackend):
    def authenticate(
        self, request, username=None, password=None, tenant=None, **kwargs
    ):
        if username is None or password is None:
            return None

        try:
            if tenant is None:
                # Superusers have no tenant
                user = User.objects.get(
                    email=username, tenant__isnull=True, is_superuser=True
                )
            else:
                user = User.objects.get(email=username, tenant=tenant)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and user.is_active:
            return user

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
