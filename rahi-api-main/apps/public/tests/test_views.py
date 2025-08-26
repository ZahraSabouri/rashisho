import json

from django.contrib.auth.models import Group
from django.urls import reverse
from dotenv import dotenv_values
from factory.faker import faker
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from apps.account.models import User
from apps.api.roles import Roles
from apps.utils.test_tokens import decode_test_token, generate_test_token

conf = dotenv_values(".env")

FAKE = faker.Faker()


class TestUserProfileProcess(APITestCase):
    def setUp(self) -> None:
        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)
        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("public:user-profile-process"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        post_response = self.client.post(reverse("public:user-profile-process"))
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.get(reverse("public:user-profile-process"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertIn("resume_completed", response_data)
