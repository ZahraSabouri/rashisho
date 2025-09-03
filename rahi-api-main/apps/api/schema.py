from drf_spectacular.extensions import OpenApiAuthenticationExtension


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
