import uuid

from django.db import models

from tenant.models import Tenant


class AssetType(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="asset_types",
        db_index=True,
    )

    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Human readable asset type name",
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "asset_types"

        ordering = ["name"]

        indexes = [
            models.Index(
                fields=["tenant", "name"],
                name="idx_asset_type_tenant_name",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uq_asset_type_tenant_name",
            ),
        ]

    def __str__(self):
        return self.name
