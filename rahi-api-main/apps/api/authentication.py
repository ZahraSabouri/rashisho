from django.conf import settings
from django.utils.translation import gettext_lazy as _
from jwt import InvalidTokenError, decode
from rest_framework_simplejwt.authentication import AuthUser, JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import Token

from apps.account.services import get_sso_user_info


class OauthToken:
    token_type = "access"

    def __init__(self, raw_token) -> None:
        self.raw_token = raw_token

    def validated_token(self):
        with open("keys/public_key.pem", "rb") as f:
            public_key = f.read()
        try:
            decoded_payload = decode(self.raw_token, public_key, algorithms=["RS256"], audience=settings.CLIENT_ID)
            decoded_payload["raw"] = self.raw_token
            return decoded_payload
        except InvalidTokenError:
            raise InvalidTokenError("invalid token")

    def validate_test_token(self):
        with open("keys/test/public_key.pem", "rb") as f:
            public_key = f.read()

        try:
            decoded_payload = decode(self.raw_token, public_key, algorithms=["RS256"])
            return decoded_payload
        except InvalidTokenError:
            raise InvalidTokenError("invalid token")


class GetUserProfileAuthentication(JWTAuthentication):
    def get_user(self, validated_token: Token) -> AuthUser:
        token_user = self.user_model.objects.filter(user_info__id=validated_token["sub"]).first()
        if token_user is None:
            user_info = get_sso_user_info(str(validated_token.get("raw"), "utf-8"))
            if self.user_model.objects.filter(username=user_info["username"]).first():
                token_user = self.user_model.objects.filter(username=user_info["username"]).first()    
            else:
                token_user = self.user_model.objects.create(username=user_info["username"], user_info=user_info)
        validated_token["user_id"] = token_user.pk
        return super().get_user(validated_token)

    def get_validated_token(self, raw_token: bytes) -> Token:
        messages = []
        try:
            token = OauthToken(raw_token)
            if settings.IS_TEST:
                return token.validate_test_token()
            return token.validated_token()
        except InvalidTokenError as e:
            messages.append(
                {
                    "token_class": OauthToken.__name__,
                    "token_type": OauthToken.token_type,
                    "message": e.args[0],
                }
            )

        raise InvalidToken(
            {
                "detail": _("Given token not valid for any token type"),
                "messages": messages,
            }
        )
