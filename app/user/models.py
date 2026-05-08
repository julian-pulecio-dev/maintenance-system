import uuid
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, tenant=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        if not password:
            raise ValueError("Password is required")
        if not tenant:
            raise ValueError("Tenant is required")

        email = self.normalize_email(email)

        user = self.model(email=email, tenant=tenant, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # Superuser is global — does not belong to any tenant.
        # Created directly to bypass the tenant validation in create_user.
        email = self.normalize_email(email)
        user = self.model(email=email, tenant=None, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        "tenant.Tenant",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )

    email = (
        models.EmailField()
    )  # unique=True does not apply here, the constraint is per tenant

    name = models.CharField(max_length=255, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "email"], name="unique_user_email_per_tenant"
            ),
            # Only superusers can have no tenant.
            # Regular users (is_superuser=False) must always have a tenant.
            models.CheckConstraint(
                check=(
                    models.Q(tenant__isnull=False)
                    | models.Q(is_superuser=True)
                ),
                name="tenant_required_for_non_superusers",
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.tenant})"


class PasswordResetToken(models.Model):
    # Configurable via settings; defaults to 1 hour.
    TOKEN_EXPIRY_HOURS = getattr(
        settings, "PASSWORD_RESET_TOKEN_EXPIRY_HOURS", 1
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    used_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_valid(self):
        expiry = self.created_at + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        return not self.is_used and timezone.now() < expiry

    def mark_as_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    @classmethod
    def invalidate_existing_tokens(cls, user):
        """
        Invalidates all active tokens for the user before creating a new one.
        Call from the service layer when generating a new reset token.
        """
        now = timezone.now()
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=now)

    @classmethod
    def create_for_user(cls, user):
        """
        Invalidates previous tokens and creates a new one.
        Recommended entry point for generating reset tokens.
        """
        cls.invalidate_existing_tokens(user)
        return cls.objects.create(user=user)
