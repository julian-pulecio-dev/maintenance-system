from rest_framework import serializers

from .models import AssetType


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ("id", "name", "description", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        tenant = self.context["request"].tenant
        qs = AssetType.objects.filter(tenant=tenant, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "An asset type with this name already exists."
            )
        return value
