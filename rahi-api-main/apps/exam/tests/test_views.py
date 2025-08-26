import datetime
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
from apps.exam import models
from apps.resume.models import Resume
from apps.utils.test_tokens import decode_test_token, generate_test_token

conf = dotenv_values(".env")

FAKE = faker.Faker()

TEN_MINUTE_LATER = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%d/%m/%Y, %H:%M:%S")


class TestBelbinQuestion(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        user = baker.make(User, user_id=decode_test_token(token))
        baker.make(Resume, user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("exam:belbin-question-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("exam:belbin-question-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"title": FAKE.text(20), "number": 1}
        response = self.client.post(reverse("exam:belbin-question-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        data = {
            "title": FAKE.text(20),
        }
        question = baker.make(models.BelbinQuestion)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.patch(reverse("exam:belbin-question-detail", args=[question.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(
            self.client.patch(reverse("exam:belbin-question-detail", args=[question.id]), data=data).content
        )
        self.assertEqual(result["title"], data["title"])

    def test_delete(self):
        question = baker.make(models.BelbinQuestion)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.delete(reverse("exam:belbin-question-detail", args=[question.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_unique(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"title": FAKE.text(20), "number": 1}
        self.client.post(reverse("exam:belbin-question-list"), data=data)
        response = self.client.post(reverse("exam:belbin-question-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TestBelbinMultiCreate(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        return super().setUp()

    def test_permission(self):
        token = generate_test_token()
        baker.make(User, user_id=decode_test_token(token))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get(reverse("exam:belbin-multi-question-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {
            "question": {"title": "question title", "number": "1"},
            "answers": ["option1", "option2", "option3", "option4"],
        }
        response = self.client.post(reverse("exam:belbin-multi-question-list"), data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {
            "question": {"title": "question title", "number": 1},
            "answers": ["option1", "option2", "option3", "option4"],
        }
        self.client.post(reverse("exam:belbin-multi-question-list"), data=data, format="json")
        created_question = models.BelbinQuestion.objects.filter(number=data["question"]["number"]).first()

        new_data = {
            "question": {"id": created_question.id, "title": "new question title", "number": "1"},
            "answers": ["new_option1", "option2", "new_option3", "option4"],
        }
        response = self.client.post(
            reverse("exam:belbin-multi-question-update-question-options"), data=new_data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["question"]["title"], new_data["question"]["title"])
        self.assertEqual(response.data["answers"][0], new_data["answers"][0])


class TestBelbinUserAnswer(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        self.question = baker.make(models.BelbinQuestion, number=1)
        role = Group.objects.create(name=Roles.sys_god.name)
        self.admin_user.groups.add(role)
        self.answer = baker.make(models.BelbinAnswer, question=self.question)
        return super().setUp()

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("exam:belbin-user-answer-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_user_answer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"question": str(self.question.id), "answers": [{"answer": str(self.answer.id), "score": 5}]}
        response = self.client.post(reverse("exam:belbin-user-answer-list"), data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_max_score(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        other_answer = baker.make(models.BelbinAnswer, question=self.question)
        data = {
            "question": str(self.question.id),
            "answers": [{"answer": self.answer.id, "score": 5}, {"answer": other_answer.id, "score": 5}],
        }
        response = self.client.post(reverse("exam:belbin-user-answer-list"), data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        other_other_answer = baker.make(models.BelbinAnswer, question=self.question)
        data = {"question": str(self.question.id), "answers": [{"answer": other_other_answer.id, "score": 5}]}
        response = self.client.post(reverse("exam:belbin-user-answer-list"), data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order(self):
        question = baker.make(models.BelbinQuestion, number=2)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        answer = baker.make(models.BelbinAnswer, question=question)
        data = {"answer": answer.id, "score": 5}
        response = self.client.post(reverse("exam:belbin-user-answer-list"), data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class GeneralExam(APITestCase):
    def setUp(self) -> None:
        self.admin_token = generate_test_token()
        self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
        role = Group.objects.create(name=Roles.sys_god.name)
        self.token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.token))
        baker.make(Resume, user=self.user)
        self.admin_user.groups.add(role)

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.get(reverse("exam:general-exam-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"title": FAKE.text(20), "time": 2, "mode": "PU"}
        response = self.client.post(reverse("exam:general-exam-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update(self):
        data = {"title": FAKE.text(20)}
        exam = baker.make(models.GeneralExam)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.patch(reverse("exam:general-exam-detail", args=[exam.id]), data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(self.client.patch(reverse("exam:general-exam-detail", args=[exam.id]), data=data).content)
        self.assertEqual(result["title"], data["title"])

    def test_delete(self):
        exam = baker.make(models.GeneralExam)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        response = self.client.delete(reverse("exam:general-exam-detail", args=[exam.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_unique(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"title": FAKE.text(20), "time": 20, "mode": "PU"}
        self.client.post(reverse("exam:general-exam-list"), data=data)
        response = self.client.post(reverse("exam:general-exam-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_without_belbin_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        response = self.client.get(reverse("exam:general-exam-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_entrance_mode(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        data = {"title": FAKE.text(20), "time": 2, "mode": "EN"}
        response = self.client.post(reverse("exam:general-exam-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        project = baker.make(models.Project)
        data = {"title": FAKE.text(20), "time": 2, "mode": "EN", "project": str(project.id)}
        response = self.client.post(reverse("exam:general-exam-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_question_option(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        exam = baker.make(models.GeneralExam)
        data = {
            "question": {"title": FAKE.text(30), "number": "1", "exam": exam.id, "score": "1"},
            "options": {
                "1": {"title": FAKE.text(20), "correct_answer": "true"},
                "2": {"title": FAKE.text(20), "correct_answer": "false"},
            },
        }
        response = self.client.post(
            reverse("exam:general-exam-create-question-option", kwargs={"pk": exam.id}), data=data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content)
        self.assertEqual(data["options"]["1"]["title"], result["data"][0]["title"])

    def test_update_question_option(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        exam = baker.make(models.GeneralExam)
        question = baker.make(models.GeneralQuestion, exam=exam)
        baker.make(models.GeneralQuestionOption, question=question)
        baker.make(models.GeneralQuestionOption, question=question)
        data = {
            "question": {
                "id": question.id,
                "title": FAKE.text(30),
                "number": question.number,
                "exam": exam.id,
                "score": "1",
            },
            "options": {
                "1": {"title": FAKE.text(30), "correct_answer": "true"},
            },
        }
        response = self.client.post(
            reverse("exam:general-exam-update-question-option", kwargs={"pk": exam.id}), data=data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content)
        self.assertEqual(data["options"]["1"]["title"], result["data"][0]["title"])
        new_question = models.GeneralQuestion.objects.get(id=result["data"][0]["question"])
        self.assertEqual(data["question"]["id"], new_question.id)

    def test_delete_question_option(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
        question = baker.make(models.GeneralQuestion)
        baker.make(models.GeneralQuestionOption, question=question)
        response = self.client.delete(reverse("exam:general-exam-delete-question-option", args=[question.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TestGeneralUserAnswer(APITestCase):
    def setUp(self) -> None:
        self.user_token = generate_test_token()
        self.user = baker.make(User, user_id=decode_test_token(self.user_token))
        self.exam = baker.make(models.GeneralExam, time=5)
        self.question_score = 5
        self.question = baker.make(models.GeneralQuestion, exam=self.exam, score=self.question_score)
        self.option = baker.make(models.GeneralQuestionOption, question=self.question, correct_answer=True)
        user_answer = baker.make(models.UserAnswer, user=self.user)
        user_answer.belbin_answer["status"] = "finished"
        user_answer.save()

    def test_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
        resume = baker.make(Resume, user=self.user)
        resume.steps["5"] = {}
        resume.steps["5"]["language"] = "finished"
        resume.steps["5"]["connection_ways"] = "finished"
        response = self.client.get(reverse("exam:general-answer-list", args=[self.exam.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(response.data)

    # def test_answer_question(self):
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #     response = self.client.get(reverse("exam:general-answer-list", args=[self.exam.id]))
    #     self.assertEqual(json.loads(response.content)[str(self.question.id)], str(self.option.id))

    # def test_invalid_question(self):
    #     question = baker.make(models.GeneralQuestion)
    #     data = {"question": question.id, "answer": self.option.id}
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # def test_invalid_option(self):
    #     option = baker.make(models.GeneralQuestionOption)
    #     data = {"question": self.question.id, "answer": option.id}
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # @freeze_time(TEN_MINUTE_LATER)
    # def test_time_empty_answer(self):
    #     baker.make(Resume, user=self.user)
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # def test_invalid_time(self):
    #     baker.make(Resume, user=self.user)
    #     other_question = baker.make(models.GeneralQuestion, exam=self.exam)
    #     other_option = baker.make(models.GeneralQuestionOption, question=other_question)
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     data = {"question": other_question.id, "answer": other_option.id}
    #     self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     with freeze_time(TEN_MINUTE_LATER):
    #         response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # def test_valid_time(self):
    #     baker.make(Resume, user=self.user)
    #     other_question = baker.make(models.GeneralQuestion, exam=self.exam)
    #     other_option = baker.make(models.GeneralQuestionOption, question=other_question)
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     data = {"question": other_question.id, "answer": other_option.id}
    #     self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # def test_finish_exam(self):
    #     baker.make(Resume, user=self.user)
    #     other_question = baker.make(models.GeneralQuestion, exam=self.exam)
    #     other_option = baker.make(models.GeneralQuestionOption, question=other_question)
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     status = json.loads(self.client.get(reverse("exam:general-answer-list", args=[self.exam.id])).content)["status"]
    #     self.assertEqual(status, "started")
    #     data = {"question": other_question.id, "answer": other_option.id}
    #     self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     status = json.loads(self.client.get(reverse("exam:general-answer-list", args=[self.exam.id])).content)["status"]
    #     self.assertEqual(status, "finished")

    # def test_score(self):
    #     baker.make(Resume, user=self.user)
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     score = json.loads(self.client.get(reverse("exam:general-answer-list", args=[self.exam.id])).content)[
    #         "total_score"
    #     ]
    #     self.assertEqual(score, self.question_score)

    # def test_finish_permission(self):
    #     baker.make(Resume, user=self.user)
    #     self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.user_token}")
    #     data = {"question": self.question.id, "answer": self.option.id}
    #     self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     response = self.client.post(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #     response = self.client.get(reverse("exam:general-answer-list", args=[self.exam.id]), data=data)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)


# class TestNeoQuestion(APITestCase):
#     def setUp(self) -> None:
#         self.admin_token = generate_test_token()
#         self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
#         self.user_answer = baker.make(models.UserAnswer, user=self.admin_user)
#         role = Group.objects.create(name=Roles.sys_god.name)
#         self.admin_user.groups.add(role)
#         return super().setUp()
#
#     def test_permission(self):
#         token = generate_test_token()
#         baker.make(User, user_id=decode_test_token(token))
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
#         response = self.client.get(reverse("exam:neo-question-list"))
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
#
#     def test_list(self):
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         response = self.client.get(reverse("exam:neo-question-list"))
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#     def test_create(self):
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         data = {"title": FAKE.text(20), "number": 1}
#         response = self.client.post(reverse("exam:neo-question-list"), data=data)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#
#     def test_update(self):
#         data = {
#             "title": FAKE.text(20),
#         }
#         question = baker.make(models.NeoQuestion)
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         response = self.client.patch(reverse("exam:neo-question-detail", args=[question.id]), data=data)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         result = json.loads(
#             self.client.patch(reverse("exam:neo-question-detail", args=[question.id]), data=data).content
#         )
#         self.assertEqual(result["title"], data["title"])
#
#     def test_delete(self):
#         question = baker.make(models.NeoQuestion)
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         response = self.client.delete(reverse("exam:neo-question-detail", args=[question.id]))
#         self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
#
#     def test_unique(self):
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         data = {"title": FAKE.text(20), "number": 1}
#         self.client.post(reverse("exam:neo-question-list"), data=data)
#         response = self.client.post(reverse("exam:neo-question-list"), data=data)
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
#
#
# class TestNeoOption(APITestCase):
#     def setUp(self):
#         self.admin_token = generate_test_token()
#         self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
#         self.user_answer = baker.make(models.UserAnswer, user=self.admin_user)
#         role = Group.objects.create(name=Roles.sys_god.name)
#         self.admin_user.groups.add(role)
#         self.question = baker.make(models.NeoQuestion)
#         return super().setUp()
#
#     def test_permission(self):
#         token = generate_test_token()
#         user = baker.make(User, user_id=decode_test_token(token))
#         baker.make(models.UserAnswer, user=user)
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
#         response = self.client.get(reverse("exam:neo-option-list", args=[self.question.id]))
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
#
#     def test_list(self):
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         response = self.client.get(reverse("exam:neo-option-list", args=[self.question.id]))
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#
#     def test_create(self):
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         data = {"option": "A", "option_score": 10, "option_number": 1}
#         response = self.client.post(reverse("exam:neo-option-list", args=[self.question.id]), data=data)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         question_id = json.loads(response.content)["question"]
#         self.assertEqual(question_id, str(self.question.id))
#
#     def test_update(self):
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         option = baker.make(models.NeoOption, question=self.question)
#         data = {"option": "QA"}
#         response = self.client.patch(reverse("exam:neo-option-detail", args=[self.question.id, option.id]), data=data)
#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         result = json.loads(response.content)
#         self.assertEqual(result["option"], data["option"])
#
#     def test_delete(self):
#         option = baker.make(models.NeoOption, question=self.question)
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_token}")
#         response = self.client.delete(reverse("exam:neo-option-detail", args=[self.question.id, option.id]))
#         self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


# class TestNeoUserNextQuestion(APITestCase):
#     def setUp(self):
#         self.admin_token = generate_test_token()
#         self.admin_user = baker.make(User, user_id=decode_test_token(self.admin_token))
#         self.user_answer = baker.make(models.UserAnswer, user=self.admin_user)
#         role = Group.objects.create(name=Roles.sys_god.name)
#         self.admin_user.groups.add(role)
#         self.question = baker.make(models.NeoQuestion)
#         return super().setUp()
#
#     def test_permission(self):
#         token = generate_test_token()
#         user = baker.make(User, user_id=decode_test_token(token))
#         baker.make(models.UserAnswer, user=user)
#         self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
#         response = self.client.get(reverse("exam:neo-user-next-question", args=[self.question.id]))
#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
