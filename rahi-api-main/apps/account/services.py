import requests
from django.conf import settings


def get_sso_user_info(token):
    try:
        response = requests.get(
            url=f"{settings.SSO_BASE_URL}/api/v1/user/me/",
            headers={"Authorization": f"Bearer {token}"},
        )
        return response.json()

    except Exception:
        return {}
