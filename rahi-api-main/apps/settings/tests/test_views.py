from django.contrib.auth.models import Group
from django.urls import reverse
from factory.faker import faker
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from apps.account.models import User
from apps.api.roles import Roles
from apps.settings import models
from apps.utils.test_tokens import decode_test_token, generate_test_token

FAKE = faker.Faker()


class TestProvince(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        return super().setUp()

    def test_without_token(self):
        response = self.client.post(reverse("settings:province-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("settings:province-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("settings:province-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permission_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        province = baker.make(models.Province)
        data = {
            "title": FAKE.text(30),
        }
        response = self.client.patch(reverse("settings:province-detail", args=[province.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("settings:province-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"title": FAKE.text(30)}
        response = self.client.post(reverse("settings:province-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TestCity(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        return super().setUp()

    def test_without_token(self):
        response = self.client.post(reverse("settings:city-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("settings:city-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("settings:city-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permission_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        province = baker.make(models.Province)
        city = baker.make(models.City, province=province)
        data = {
            "title": FAKE.text(50),
        }
        response = self.client.patch(reverse("settings:city-detail", args=[city.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("settings:city-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")

        province = baker.make(models.Province)
        data = {"title": FAKE.text(50), "province": province.id}
        response = self.client.post(reverse("settings:city-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TestUniversity(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        return super().setUp()

    def test_without_token(self):
        response = self.client.post(reverse("settings:university-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("settings:university-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("settings:university-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_permission_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        university = baker.make(models.University)
        data = {
            "title": FAKE.text(30),
        }
        response = self.client.patch(reverse("settings:university-detail", args=[university.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("settings:university-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")

        data = {"title": FAKE.text(20)}
        response = self.client.post(reverse("settings:university-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TestDeActive(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("exam:general-exam-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"feature": "BE", "active": True}
        response = self.client.post(reverse("settings:feature-activation-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.get(reverse("exam:belbin-question-list"))
        self.assertEqual(response.status_code, status.HTTP_423_LOCKED)
