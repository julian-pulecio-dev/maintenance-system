from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import WorkOrder

User = get_user_model()


class WorkOrderSerializer(serializers.ModelSerializer):
    asset_detail = serializers.SerializerMethodField()
    work_order_type_detail = serializers.SerializerMethodField()
    assigned_to_detail = serializers.SerializerMethodField()
    created_by_detail = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = (
            "id",
            "asset",
            "asset_detail",
            "work_order_type",
            "work_order_type_detail",
            "assigned_to",
            "assigned_to_detail",
            "created_by",
            "created_by_detail",
            "title",
            "description",
            "status",
            "priority",
            "scheduled_date",
            "due_date",
            "completed_date",
            "notes",
            "estimated_hours",
            "created_at",
            "updated_at",
            "deleted_at",
            "is_deleted",
            "is_active",
            "is_overdue",
        )
        read_only_fields = (
            "id",
            "status",
            "completed_date",
            "created_by",
            "created_at",
            "updated_at",
            "deleted_at",
        )

    def get_asset_detail(self, obj):
        return {
            "id": str(obj.asset_id),
            "name": obj.asset.name,
            "serial_number": obj.asset.serial_number,
            "status": obj.asset.status,
        }

    def get_work_order_type_detail(self, obj):
        return {
            "id": str(obj.work_order_type_id),
            "name": obj.work_order_type.name,
        }

    def get_assigned_to_detail(self, obj):
        return {
            "id": str(obj.assigned_to_id),
            "email": obj.assigned_to.email,
            "name": obj.assigned_to.name,
        }

    def get_created_by_detail(self, obj):
        return {
            "id": str(obj.created_by_id),
            "email": obj.created_by.email,
            "name": obj.created_by.name,
        }

    def get_is_deleted(self, obj):
        return obj.is_deleted

    def get_is_active(self, obj):
        return obj.is_active

    def get_is_overdue(self, obj):
        return obj.is_overdue

    def validate_asset(self, value):
        tenant = self.context["request"].tenant
        if value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "Asset does not belong to your tenant."
            )
        return value

    def validate_work_order_type(self, value):
        tenant = self.context["request"].tenant
        if value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "Work order type does not belong to your tenant."
            )
        return value

    def validate_assigned_to(self, value):
        tenant = self.context["request"].tenant
        if hasattr(value, "tenant_id") and value.tenant_id != tenant.id:
            raise serializers.ValidationError(
                "Assigned user must belong to the same tenant."
            )
        return value

    def validate(self, data):
        tenant = self.context["request"].tenant
        user = self.context["request"].user

        if self.instance:
            instance = self.instance
            for key, value in data.items():
                setattr(instance, key, value)
        else:
            instance = WorkOrder(tenant=tenant, created_by=user, **data)

        try:
            instance.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            raise serializers.ValidationError(exc.messages)

        return data
