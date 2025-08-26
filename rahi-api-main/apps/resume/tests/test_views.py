import json

from django.urls import reverse
from dotenv import dotenv_values
from factory.faker import faker
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APITestCase

from apps.account.models import User
from apps.resume import models
from apps.settings.models import ConnectionWay, ForeignLanguage, StudyField, University
from apps.settings.models import Skill as SkillName
from apps.utils.test_tokens import decode_test_token, generate_test_token

conf = dotenv_values(".env")

FAKE = faker.Faker()


class TestStartResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))

    def test_without_token(self):
        response = self.client.post(reverse("resume:start-resume"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:start-resume"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:start-resume"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content)
        self.assertEqual(result["steps"], {"1": "finished", "2": "started"})

    def test_invalid_resume(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        baker.make(models.Resume, user=self.user)
        response = self.client.post(reverse("resume:start-resume"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestResumePermission(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token), is_staff=False)
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)

    def test_resume_list_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:resume-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resume_detail_permission(self):
        fake_resume = baker.make(models.Resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:resume-detail", args=[fake_resume.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TestMyResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)

    def test_get(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:my-resume"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_without_resume(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("resume:my-resume"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestEducationResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)

    def test_without_token(self):
        response = self.client.post(reverse("resume:education-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:education-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_resume(self):
        other_resume = baker.make(models.Resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:education-list", args=[other_resume.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_without_resume(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.post(reverse("resume:education-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        baker.make(models.Education, resume=self.resume)
        baker.make(models.Education)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:education-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        university = baker.make(University)
        field = baker.make(StudyField)
        data = {
            "grade": "BA",
            "field": field.id,
            "university": university.id,
            "start_date": FAKE.date(),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:education-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create(self):
        university = baker.make(University)
        field = baker.make(StudyField)
        data = {
            "grade": "BA",
            "field": field.id,
            "university": university.id,
            "start_date": FAKE.date(),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:education-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_end_date(self):
        university = baker.make(University)
        field = baker.make(StudyField)
        data = {
            "grade": "BA",
            "field": field.id,
            "university": university.id,
            "start_date": "2023-02-02",
            "end_date": "2023-01-02",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:education-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update(self):
        data = {
            "grade": "BA",
        }
        education = baker.make(models.Education, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(reverse("resume:education-detail", args=[self.resume.id, education.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(
                reverse("resume:education-detail", args=[self.resume.id, education.id]), data=data
            ).content
        )
        self.assertEqual(result["grade"], "BA")

    def test_delete(self):
        education = baker.make(models.Education, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:education-detail", args=[self.resume.id, education.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestWorkExperienceResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)
        self.resume.next_step(2)

    def test_without_token(self):
        response = self.client.post(reverse("resume:work-experience-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:work-experience-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        data = {
            "job_title": "عنوان شغلی",
            "start_date": "1403-02-05",
            "company_name": "نام شرکت",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:work-experience-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_with_resume(self):
        data = {
            "job_title": "عنوان شغلی",
            "company_name": "نام شرکت",
            "start_date": FAKE.date(),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:work-experience-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_work_list(self):
        baker.make(models.WorkExperience, resume=self.resume)
        baker.make(models.WorkExperience)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:work-experience-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_update_work(self):
        data = {
            "job_title": "job title",
        }
        job = baker.make(models.WorkExperience, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(reverse("resume:work-experience-detail", args=[self.resume.id, job.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(
                reverse("resume:work-experience-detail", args=[self.resume.id, job.id]), data=data
            ).content
        )
        self.assertEqual(result["job_title"], "job title")

    def test_delete_work(self):
        job = baker.make(models.WorkExperience, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:work-experience-detail", args=[self.resume.id, job.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_invalid_end_date(self):
        data = {
            "job_title": "sample job title",
            "company_name": "sample company",
            "start_date": "2023-02-02",
            "end_date": "2023-01-02",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:work-experience-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestSkillResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)

    def test_without_token(self):
        response = self.client.post(reverse("resume:skill-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:skill-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        skill_name = baker.make(SkillName)
        data = {
            "skill_name": skill_name.id,
            "level": "AD",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:skill-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_with_resume(self):
        skill_name = baker.make(SkillName)
        data = {
            "skill_name": skill_name.id,
            "level": "AD",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:skill-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_get_skill_list(self):
        baker.make(models.Skill, resume=self.resume)
        baker.make(models.Skill)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:skill-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_update_skill(self):
        data = {
            "text": FAKE.text(20),
        }
        skill = baker.make(models.Skill, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(reverse("resume:skill-detail", args=[self.resume.id, skill.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(reverse("resume:skill-detail", args=[self.resume.id, skill.id]), data=data).content
        )
        self.assertEqual(result["text"], data["text"])

    def test_delete_skill(self):
        skill = baker.make(models.Skill, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:skill-detail", args=[self.resume.id, skill.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestLanguageResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)
        self.resume.finish_flow()

    def test_without_token(self):
        response = self.client.post(reverse("resume:language-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:language-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        skill_name = baker.make(ForeignLanguage)
        data = {
            "language_name": skill_name.id,
            "level": "AD",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:language-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_with_resume(self):
        language_name = baker.make(ForeignLanguage)
        data = {
            "language_name": language_name.id,
            "level": "AD",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:language-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = json.loads(self.client.get(reverse("resume:my-resume")).content)
        self.assertEqual(response["steps"]["5"]["language"], "finished")

    def test_get_language_list(self):
        baker.make(models.Language, resume=self.resume)
        baker.make(models.Language)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:language-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_update_skill(self):
        data = {
            "level": "AD",
        }
        language = baker.make(models.Language, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(reverse("resume:language-detail", args=[self.resume.id, language.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(reverse("resume:language-detail", args=[self.resume.id, language.id]), data=data).content
        )
        self.assertEqual(result["level"], data["level"])

    def test_delete_language(self):
        language = baker.make(models.Language, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:language-detail", args=[self.resume.id, language.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestCertificateResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)
        self.resume.finish_flow()

    def test_without_token(self):
        response = self.client.post(reverse("resume:certificate-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:certificate-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        data = {
            "certificate_title": "عنوان گواهی نامه",
            "institution": "نام موسسه",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:certificate-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_with_resume(self):
        data = {
            "certificate_title": FAKE.text(10),
            "institution": FAKE.text(10),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:certificate-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = json.loads(self.client.get(reverse("resume:my-resume")).content)
        self.assertEqual(response["steps"]["5"]["certification"], "finished")

    def test_get_certificate_list(self):
        baker.make(models.Certificate, resume=self.resume)
        baker.make(models.Certificate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:certificate-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_update_certificate(self):
        data = {
            "certificate_title": "عنوان گواهی نامه",
        }
        certificate = baker.make(models.Certificate, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(
            reverse("resume:certificate-detail", args=[self.resume.id, certificate.id]), data=data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(
                reverse("resume:certificate-detail", args=[self.resume.id, certificate.id]), data=data
            ).content
        )
        self.assertEqual(result["certificate_title"], "عنوان گواهی نامه")

    def test_delete_certificate(self):
        certificate = baker.make(models.Certificate, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:certificate-detail", args=[self.resume.id, certificate.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestConnectionResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)
        self.resume.finish_flow()

    def test_without_token(self):
        response = self.client.post(reverse("resume:connection-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:connection-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        connection = baker.make(ConnectionWay)
        data = {
            "title": connection.id,
            "link": "www.google.com",
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:connection-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_with_resume(self):
        connection = baker.make(ConnectionWay)
        data = {
            "title": connection.id,
            "link": FAKE.url(),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:connection-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = json.loads(self.client.get(reverse("resume:my-resume")).content)
        self.assertEqual(response["steps"]["5"]["connection_ways"], "finished")

    def test_get_connection_list(self):
        baker.make(models.Connection, resume=self.resume)
        baker.make(models.Connection)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:connection-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_update_connection(self):
        data = {
            "link": FAKE.url(),
        }
        connection = baker.make(models.Connection, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(
            reverse("resume:connection-detail", args=[self.resume.id, connection.id]), data=data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(
                reverse("resume:connection-detail", args=[self.resume.id, connection.id]), data=data
            ).content
        )
        self.assertEqual(result["link"], data["link"])

    def test_delete_connection(self):
        connection = baker.make(models.Connection, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:connection-detail", args=[self.resume.id, connection.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TestProjectResume(APITestCase):
    def setUp(self) -> None:
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        self.resume = baker.make(models.Resume, user=self.user)
        self.resume.next_step(1)
        self.resume.next_step(2)
        self.resume.next_step(3)
        self.resume.finish_flow()

    def test_without_token(self):
        response = self.client.post(reverse("resume:resume-project-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
        response = self.client.post(reverse("resume:resume-project-list", args=[self.resume.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_out_resume(self):
        fake_resume = baker.make(models.Resume)
        data = {
            "title": "عنوان پروژه",
            "end_date": FAKE.date(),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:resume-project-list", args=[fake_resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_with_resume(self):
        data = {
            "title": "عنوان پروژه",
            "end_date": FAKE.date(),
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.post(reverse("resume:resume-project-list", args=[self.resume.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = json.loads(self.client.get(reverse("resume:my-resume")).content)
        self.assertEqual(response["steps"]["5"]["project"], "finished")

    def test_get_project_list(self):
        baker.make(models.Project, resume=self.resume)
        baker.make(models.Project)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("resume:resume-project-list", args=[self.resume.id]))
        result = json.loads(response.content)
        self.assertEqual(result["count"], 1)

    def test_update_project(self):
        data = {
            "title": "عنوان پروژه",
        }
        project = baker.make(models.Project, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.patch(
            reverse("resume:resume-project-detail", args=[self.resume.id, project.id]), data=data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(
                reverse("resume:resume-project-detail", args=[self.resume.id, project.id]), data=data
            ).content
        )
        self.assertEqual(result["title"], "عنوان پروژه")

    def test_delete_project(self):
        project = baker.make(models.Project, resume=self.resume)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.delete(reverse("resume:resume-project-detail", args=[self.resume.id, project.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
