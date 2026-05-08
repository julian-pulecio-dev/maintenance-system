from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Asset


class AssetSerializer(serializers.ModelSerializer):
    next_maintenance_date = serializers.SerializerMethodField()
    is_maintenance_overdue = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = (
            "id",
            "serial_number",
            "name",
            "asset_type",
            "location",
            "installation_date",
            "status",
            "description",
            "last_maintenance_date",
            "recommended_maintenance_interval_days",
            "metadata",
            "created_at",
            "updated_at",
            "deleted_at",
            "next_maintenance_date",
            "is_maintenance_overdue",
            "is_deleted",
        )
        read_only_fields = ("id", "created_at", "updated_at", "deleted_at")

    def get_next_maintenance_date(self, obj):
        return obj.next_maintenance_date

    def get_is_maintenance_overdue(self, obj):
        return obj.is_maintenance_overdue

    def get_is_deleted(self, obj):
        return obj.is_deleted

    def validate_asset_type(self, value):
        tenant = self.context["request"].tenant
        if value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "Asset type does not belong to your tenant."
            )
        return value

    def validate(self, data):
        tenant = self.context["request"].tenant
        if self.instance:
            instance = self.instance
            for key, value in data.items():
                setattr(instance, key, value)
        else:
            instance = Asset(tenant=tenant, **data)

        try:
            instance.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError(exc.messages)

        return data
