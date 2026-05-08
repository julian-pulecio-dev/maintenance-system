from django.core.exceptions import ValidationError


ASSET_METADATA_SCHEMAS = {
    "generator": {
        1: {
            "required": {
                "motor": {
                    "rpm": int,
                },
            },
            "optional": {
                "electrical": {
                    "voltage": int,
                },
            },
        },
    },
    "pump": {
        1: {
            "required": {
                "flow": {
                    "liters_per_minute": int,
                },
            },
            "optional": {},
        },
    },
}


def validate_metadata_section(data, schema, *, required=True, path=""):
    """
    Recursively validates a metadata section.

    Example schema:

    {
        "motor": {
            "rpm": int,
        }
    }
    """

    for field, expected in schema.items():
        full_path = f"{path}.{field}" if path else field

        if field not in data:
            if required:
                raise ValidationError({
                    "metadata": f"Missing required field: '{full_path}'."
                })
            continue

        value = data[field]

        # Nested object
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                raise ValidationError({
                    "metadata": (
                        f"Field '{full_path}' must be an object."
                    )
                })

            validate_metadata_section(
                value,
                expected,
                required=True,
                path=full_path,
            )

        # Primitive type
        else:
            if not isinstance(value, expected):
                raise ValidationError({
                    "metadata": (
                        f"Field '{full_path}' must be "
                        f"{expected.__name__}."
                    )
                })


def validate_asset_metadata(asset):
    """
    Validates metadata against the schema defined for the asset type.

    Expected metadata shape:

    {
        "spec_version": 1,
        ...
    }
    """

    metadata = asset.metadata or {}

    if not isinstance(metadata, dict):
        raise ValidationError({
            "metadata": "Metadata must be a JSON object."
        })

    spec_version = metadata.get("spec_version")

    if spec_version is None:
        raise ValidationError({
            "metadata": "Field 'spec_version' is required."
        })

    if not isinstance(spec_version, int):
        raise ValidationError({
            "metadata": "'spec_version' must be an integer."
        })

    asset_type_slug = getattr(asset.asset_type, "slug", None)

    if not asset_type_slug:
        return

    type_schemas = ASSET_METADATA_SCHEMAS.get(asset_type_slug)

    if not type_schemas:
        return

    schema = type_schemas.get(spec_version)

    if not schema:
        raise ValidationError({
            "metadata": (
                f"Unsupported spec_version={spec_version} "
                f"for asset type '{asset_type_slug}'."
            )
        })

    validate_metadata_section(
        metadata,
        schema["required"],
        required=True,
    )

    validate_metadata_section(
        metadata,
        schema["optional"],
        required=False,
    )