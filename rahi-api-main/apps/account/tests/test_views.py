import json

from django.urls import reverse
from dotenv import dotenv_values
from factory.faker import faker
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from apps.account.models import User
from apps.settings.models import City
from apps.utils.test_tokens import decode_test_token, generate_test_token

conf = dotenv_values(".env")

FAKE = faker.Faker()


class TestMeUser(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))

    def test_without_token(self):
        response = self.client.get(reverse("account:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.get(reverse("account:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_token(self):
        baker.make(User, user_id=decode_test_token(self.token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("account:me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content)
        self.assertEqual(result["user_info"]["id"], decode_test_token(self.token))

    def test_update(self):
        baker.make(User, user_id=decode_test_token(self.token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        city = baker.make(City)
        data = {
            "address": FAKE.address(),
            "gender": "MA",
            "marriage_status": "SI",
            "birth_date": FAKE.date(),
            "military_status": "EE",
            "city": str(city.id),
        }
        response = self.client.put(reverse("account:me"), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_datetime_invalid(self):
        baker.make(User, user_id=decode_test_token(self.token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        data = {
            "birth_date": FAKE.random_choices(),
        }
        response = self.client.put(reverse("account:me"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_military_status(self):
        baker.make(User, user_id=decode_test_token(self.token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        data = {
            "address": FAKE.address(),
            "gender": "MA",
            "marriage_status": "SI",
        }
        response = self.client.put(reverse("account:me"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_female_military(self):
        baker.make(User, user_id=decode_test_token(self.token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        data = {
            "address": FAKE.address(),
            "gender": "FE",
            "marriage_status": "SI",
            "military_status": "EE",
        }
        result = json.loads(self.client.patch(reverse("account:me"), data=data).content)
        self.assertEqual(result["military_status"], None)


class TestUserList(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))

    def test_without_token(self):
        response = self.client.get(reverse("account:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.get(reverse("account:me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_token(self):
        baker.make(User, user_id=decode_test_token(self.token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("account:me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content)
        self.assertEqual(result["user_info"]["id"], decode_test_token(self.token))

    def test_user_list_for_staff(self):
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token), is_staff=False)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("account:users"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
