import os

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

from apps.api.roles import SetUpRole
from apps.settings.models import FeatureActivation

username = os.getenv("ADMINISTRATOR_USERNAME", "superuser")
password = os.getenv("ADMINISTRATOR_PASSWORD", "superuser")
email = os.getenv("ADMINISTRATOR_EMAIL", "sysgodforeal@example.com")

get_user_model().objects.get_or_create(
    username=username,
    defaults=dict(email=email, password=make_password(password), is_superuser=True, is_staff=True),
)

SetUpRole()

# Creating default activation tables.
# for item in FeatureActivation.FEATURE:
#     FeatureActivation.objects.create(feature=item[0], active=True)
