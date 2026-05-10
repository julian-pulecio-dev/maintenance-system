from rest_framework import serializers

from .models import WorkOrderType


class WorkOrderTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkOrderType
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        tenant = self.context["request"].tenant
        qs = WorkOrderType.objects.filter(tenant=tenant, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A work order type with this name already exists."
            )
        return value
