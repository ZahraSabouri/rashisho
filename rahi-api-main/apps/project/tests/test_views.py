import json
from io import BytesIO

import requests
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from dotenv import dotenv_values
from factory.faker import faker
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from apps.account.models import User
from apps.api.roles import Roles
from apps.project import models
from apps.project.models import ProjectDerivatives, TeamRequest, UserScenarioTaskFile
from apps.resume.models import Resume
from apps.settings.models import StudyField
from apps.utils.test_tokens import decode_test_token, generate_test_token
from conf import settings

conf = dotenv_values(".env")

FAKE = faker.Faker()


class TestProject(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        image_response = requests.get("https://sample-videos.com/img/Sample-jpg-image-50kb.jpg")
        if image_response.status_code == 200:
            self.dummy_image = SimpleUploadedFile(
                "Sample-jpg-image-50kb.jpg",
                image_response.content,
                content_type=image_response.headers.get("Content-Type", "image/jpeg"),
            )
        else:
            raise ValueError("تصویر بارگیری نشد!")

        video_response = requests.get("https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4")
        if video_response.status_code == 200:
            self.dummy_video = SimpleUploadedFile(
                "big_buck_bunny_720p_1mb.mp4",
                video_response.content,
                content_type=video_response.headers.get("Content-Type", "video/mp4"),
            )
        else:
            raise ValueError("ویدئو بارگیری نشد!")

        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        baker.make(models.Project)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:detail-list"))
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        post_response = self.client.post(reverse("project:detail-list"))
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.get(reverse("project:detail-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {
            "code": FAKE.text(20),
            "title": FAKE.text(20),
            "image": self.dummy_image,
            "company": FAKE.text(50),
            "leader": FAKE.text(20),
            "leader_position": FAKE.text(20),
            "study_fields[]": [baker.make(StudyField).id, baker.make(StudyField).id],
            "description": FAKE.text(50),
            "video": self.dummy_video,
        }
        response = self.client.post(reverse("project:detail-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        project = baker.make(models.Project)
        data = {
            "title": "some title for patch",
            "study_fields[]": [baker.make(StudyField).id, baker.make(StudyField).id],
            "video": self.dummy_video,
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.patch(reverse("project:detail-detail", args=[project.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        get_response = self.client.get(reverse("project:detail-detail", args=[project.id]))
        result = json.loads(get_response.content)
        self.assertEqual(result["title"], data["title"])

    def test_delete(self):
        project = baker.make(models.Project)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.delete(reverse("project:detail-detail", args=[project.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestProjectPriority(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        self.study_fields = [baker.make(StudyField), baker.make(StudyField)]
        self.project_1 = baker.make(models.Project, study_fields=self.study_fields)
        self.project_2 = baker.make(models.Project, study_fields=self.study_fields)
        self.project_3 = baker.make(models.Project, study_fields=self.study_fields)
        self.project_4 = baker.make(models.Project, study_fields=self.study_fields)
        self.project_5 = baker.make(models.Project, study_fields=self.study_fields)

        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))

        data = {
            "priority": {
                "1": self.project_1.id,
                "2": self.project_2.id,
                "3": self.project_3.id,
                "4": self.project_4.id,
                "5": self.project_5.id,
            }
        }

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:project-priority-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        post_response = self.client.post(reverse("project:project-priority-list"), data=data, format="json")
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("project:project-priority-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

        data = {
            "priority": {
                "1": self.project_1.id,
                "2": self.project_2.id,
                "3": self.project_3.id,
                "4": self.project_4.id,
                "5": self.project_5.id,
            }
        }
        response = self.client.post(reverse("project:project-priority-list"), data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        project_priority = baker.make(models.ProjectAllocation, user=self.user)

        project_1 = baker.make(models.Project, study_fields=self.study_fields)
        project_2 = baker.make(models.Project, study_fields=self.study_fields)
        project_3 = baker.make(models.Project, study_fields=self.study_fields)
        project_4 = baker.make(models.Project, study_fields=self.study_fields)
        project_5 = baker.make(models.Project, study_fields=self.study_fields)
        data = {
            "priority": {
                "1": str(project_1.id),
                "2": str(project_2.id),
                "3": str(project_3.id),
                "4": str(project_4.id),
                "5": str(project_5.id),
            }
        }

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(
            reverse("project:project-priority-detail", args=[project_priority.id]), data=data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete(self):
        project_priority = baker.make(models.ProjectAllocation, user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("project:project-priority-detail", args=[project_priority.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestFinalRepresentation(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        file = requests.get("https://www.buds.com.ua/images/Lorem_ipsum.pdf")
        file_content = BytesIO(file.content)
        self.dummy_file = SimpleUploadedFile("Lorem_ipsum.pdf", file_content.read(), content_type="application/pdf")
        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:final-rep-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        post_response = self.client.post(reverse("project:final-rep-list"))
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("project:final-rep-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_validate(self):
        project = baker.make(models.Project)
        baker.make(models.ProjectAllocation, user=self.user, project=project)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        data = {
            "file": self.dummy_file,
        }
        response = self.client.post(reverse("project:final-rep-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("فقط سر تیم می تواند فایل ارائه نهایی را ارسال کند!", response.data["non_field_errors"])

    def test_create(self):
        project = baker.make(models.Project)
        baker.make(models.ProjectAllocation, user=self.user, project=project)
        team = baker.make(models.Team, project=project)
        baker.make(models.TeamRequest, user=self.user, team=team, user_role="C", status="A")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        data = {
            "user": self.user.id,
            "project": project.id,
            "file": self.dummy_file,
        }
        response = self.client.post(reverse("project:final-rep-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        project = baker.make(models.Project)
        baker.make(models.ProjectAllocation, user=self.user, project=project)
        team = baker.make(models.Team, project=project)
        baker.make(models.TeamRequest, user=self.user, team=team, user_role="C", status="A")
        final_rep = baker.make(models.FinalRepresentation, user=self.user, project=project)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        data = {
            "file": self.dummy_file,
        }
        response = self.client.patch(
            reverse("project:final-rep-detail", args=[final_rep.id]), data=data, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        get_response = self.client.get(reverse("project:final-rep-detail", args=[final_rep.id]))
        result = json.loads(get_response.content)
        file_prefix = f"/{settings.MEDIA_URL}project/representations/Lorem_ipsum"
        self.assertTrue(result["file"].startswith(file_prefix))

    def test_delete(self):
        final_rep = baker.make(models.FinalRepresentation)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.delete(reverse("project:final-rep-detail", args=[final_rep.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestScenario(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        file = self.client.get("https://pmo.innostart.ir/static/mobin_system.jpg")
        self.dummy_file = SimpleUploadedFile("mobin_system.jpg", file.content, content_type="image/jpeg")
        self.second_dummy_file = SimpleUploadedFile("mobin_system.jpg", file.content, content_type="image/jpeg")
        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        baker.make(models.Scenario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:scenario-list"))
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        post_response = self.client.post(reverse("project:scenario-list"))
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        baker.make(models.Scenario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("project:scenario-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        project = baker.make(models.Project)
        data = {
            "title": FAKE.text(20),
            "description": FAKE.text(50),
            "first_file": self.dummy_file,
            "second_file": self.second_dummy_file,
            "project": str(project.id),
        }
        response = self.client.post(reverse("project:scenario-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        scenario = baker.make(models.Scenario)
        data = {
            "title": "title | edited",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.patch(reverse("project:scenario-detail", args=[scenario.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("project:scenario-detail", args=[scenario.id]))
        result = json.loads(response.content)
        self.assertEqual(result["title"], data["title"])

    def test_delete(self):
        scenario = baker.make(models.Scenario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.delete(reverse("project:scenario-detail", args=[scenario.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestTask(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        file = self.client.get("https://pmo.innostart.ir/static/mobin_system.jpg")
        self.dummy_file = SimpleUploadedFile("mobin_system.jpg", file.content, content_type="image/jpeg")
        self.second_dummy_file = SimpleUploadedFile("mobin_system.jpg", file.content, content_type="image/jpeg")
        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        baker.make(models.Task)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:task-list"))
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        post_response = self.client.post(reverse("project:task-list"))
        self.assertEqual(post_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        baker.make(models.Task)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("project:task-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        project = baker.make(models.Project)
        data = {
            "title": FAKE.text(20),
            "description": FAKE.text(50),
            "first_file": self.dummy_file,
            "second_file": self.second_dummy_file,
            "project": str(project.id),
        }
        response = self.client.post(reverse("project:task-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        task = baker.make(models.Task)
        data = {
            "title": "title | edited",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.patch(reverse("project:task-detail", args=[task.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("project:task-detail", args=[task.id]))
        result = json.loads(response.content)
        self.assertEqual(result["title"], data["title"])

    def test_delete(self):
        task = baker.make(models.Task)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.delete(reverse("project:task-detail", args=[task.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestProjectParticipantsList(APITestCase):
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
        get_response = self.client.get(reverse("project:project-members-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        project = baker.make(models.Project)
        baker.make(models.ProjectAllocation, user=self.user, project=project)
        team = baker.make(models.Team, project=project)
        baker.make(models.TeamRequest, user=self.user, user_role="C", team=team)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.get(reverse("project:project-members-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)["results"]
        user_ids = [user["user_id"] for user in response_data]
        self.assertNotIn(self.user.user_id, user_ids)


class TestTeamBuild(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:team-build-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        get_response = self.client.post(reverse("project:team-build-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("project:team-build-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        token = generate_test_token()
        user = baker.make(User, user_id=decode_test_token(token))
        role = Group.objects.get(name=Roles.user.name)
        user.groups.add(role)

        project = baker.make(models.Project)
        baker.make(models.ProjectAllocation, user=self.user, project=project)
        baker.make(models.ProjectAllocation, user=user, project=project)
        baker.make(Resume, user=self.user)
        data = {"title": "عنوان تیم", "teammate": [user.user_info["id"]]}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.post(reverse("project:team-build-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        team = baker.make(models.Team)
        data = {
            "title": "عنوان جدید تیم",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.patch(reverse("project:team-build-detail", args=[team.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("project:team-build-detail", args=[team.id]))
        result = json.loads(response.content)
        self.assertEqual(result["title"], data["title"])

    def test_fail_delete(self):
        team = baker.make(models.Team)
        baker.make(models.TeamRequest, user=self.user, team=team, user_role="M")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.delete(reverse("project:team-build-detail", args=[team.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("شما اجازه حذف این تیم را ندارید!", response.data)

    def test_success_delete(self):
        team = baker.make(models.Team)
        baker.make(models.TeamRequest, user=self.user, team=team, user_role="C")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.delete(reverse("project:team-build-detail", args=[team.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_validate(self):
        project = baker.make(models.Project)
        baker.make(models.ProjectAllocation, user=self.user, project=project)
        team = baker.make(models.Team)
        baker.make(models.TeamRequest, user=self.user, status="A", team=team)
        data = {"title": "تیم تست", "project": project.id}
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.post(reverse("project:team-build-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("شما عضو یک تیم هستید!", response.data["non_field_errors"])


class TestTeamRequest(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        get_response = self.client.get(reverse("project:team-request-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)
        get_response = self.client.post(reverse("project:team-request-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        response = self.client.get(reverse("project:team-request-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestProposalInfoVS(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        file = requests.get("https://www.buds.com.ua/images/Lorem_ipsum.pdf")
        file_content = BytesIO(file.content)
        self.dummy_file = SimpleUploadedFile("Lorem_ipsum.pdf", file_content.read(), content_type="application/pdf")

    def test_admin_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        get_response = self.client.get(reverse("project:proposal-info-list"))
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)

    def test_user_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        get_response = self.client.get(reverse("project:proposal-info-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        user = baker.make(User)
        baker.make(TeamRequest, user=user, status="A")
        derivatives = baker.make(ProjectDerivatives, derivatives_type="P")
        baker.make(UserScenarioTaskFile, derivatives=derivatives, user=user, file=self.dummy_file)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("project:proposal-info-list"))
        file_prefix = f"/{settings.MEDIA_URL}Lorem_ipsum"
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserScenarioTaskFile.objects.count(), 1)
        self.assertTrue(response.data["results"][0]["file"].startswith(file_prefix))
        self.assertEqual(response.data["results"][0]["scenario"], None)
        self.assertEqual(response.data["results"][0]["task"], None)
        self.assertEqual(response.data["results"][0]["derivatives"], derivatives.id)


class TestFinalRepInfoV2(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)

        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        role = Group.objects.create(name=Roles.user.name)
        self.user.groups.add(role)

        file = requests.get("https://www.buds.com.ua/images/Lorem_ipsum.pdf")
        file_content = BytesIO(file.content)
        self.dummy_file = SimpleUploadedFile("Lorem_ipsum.pdf", file_content.read(), content_type="application/pdf")

    def test_admin_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        get_response = self.client.get(reverse("project:final-rep-info-list"))
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)

    def test_user_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        get_response = self.client.get(reverse("project:final-rep-info-list"))
        self.assertEqual(get_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        user = baker.make(User)
        baker.make(TeamRequest, user=user, status="A")
        derivatives = baker.make(ProjectDerivatives, derivatives_type="F")
        baker.make(UserScenarioTaskFile, derivatives=derivatives, user=user, file=self.dummy_file)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("project:final-rep-info-list"))
        file_prefix = f"/{settings.MEDIA_URL}Lorem_ipsum"
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserScenarioTaskFile.objects.count(), 1)
        self.assertTrue(response.data["results"][0]["file"].startswith(file_prefix))
        self.assertEqual(response.data["results"][0]["scenario"], None)
        self.assertEqual(response.data["results"][0]["task"], None)
        self.assertEqual(response.data["results"][0]["derivatives"], derivatives.id)
