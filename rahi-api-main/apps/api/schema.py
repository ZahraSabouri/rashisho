from drf_spectacular.extensions import OpenApiAuthenticationExtension


class GetUserProfileAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'apps.api.authentication.GetUserProfileAuthentication'  
    name = 'GetUserProfileAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',  
            'description': 'JWT Authentication with SSO user profile. Format: `Bearer <token>`'
        }