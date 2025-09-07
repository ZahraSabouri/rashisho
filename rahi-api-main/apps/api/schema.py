from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema

class TaggedAutoSchema(AutoSchema):
    """Allow setting fixed tags via constructor."""
    def __init__(self, *args, tags=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fixed_tags = tags or []

    def get_tags(self, *args, **kwargs):
        base = super().get_tags(*args, **kwargs)
        return self._fixed_tags or base

class GetUserProfileAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "apps.api.authentication.GetUserProfileAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        # Standard HTTP Bearer (JWT) scheme
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Paste your JWT here. You may exclude the 'Bearer ' prefix or just the token."
            ),
        }

    def get_security_requirement(self, auto_schema):
        return {"BearerAuth": []}
