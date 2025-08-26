import datetime
from typing import Dict
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.account.models import User
from apps.exam import models
from apps.exam.models import NeoQuestion, UserAnswer

# belbin question
MAX_SCORE = 10


def belbin_question_by_number() -> list[models.BelbinQuestion]:
    return list(models.BelbinQuestion.objects.all().order_by("number"))


def parse_user_answer(data: Dict[str, str | UUID]) -> Dict:
    """
    data : {"answer": UUID, "score": "5"}
    """
    return {str(data["answer"]): data["score"]}


def question_answer(user_answer: models.UserAnswer, question: models.BelbinQuestion) -> None | dict:
    question_id = str(question.id)
    answers = user_answer.belbin_answer["answers"]
    return answers.get(question_id)


def save_belbin_answer(user_answer: models.UserAnswer, answer: dict, question: models.BelbinQuestion):
    answers = user_answer.belbin_answer["answers"]
    question_id = str(question.id)
    if question_answer(user_answer, question) is None:
        answers[question_id] = {}
    answers[question_id].update(answer)
    all_questions = belbin_question_by_number()
    if all_questions.index(question) == 0 and question_score(user_answer, question) != MAX_SCORE:
        user_answer.belbin_answer["started"] = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
    elif all_questions[-1] == question and question_score(user_answer, question) == MAX_SCORE:
        user_answer.belbin_answer["finished"] = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        user_answer.belbin_answer["status"] = "finished"
    user_answer.save()


def question_score(user_answer: models.UserAnswer, question: models.BelbinQuestion) -> int:
    question_answers = question_answer(user_answer, question)
    if question_answers is None:
        return 0
    score = sum(score for score in question_answers.values())
    return score


def get_answer_score(user_answer: models.UserAnswer, answer: models.BelbinAnswer) -> int:
    question_answers = question_answer(user_answer, answer.question)
    if question_answers is None:
        return 0
    return question_answers.get(str(answer.id), 0)


def valid_question(user_answer, question: models.BelbinQuestion) -> bool:
    all_questions = belbin_question_by_number()
    question_index = all_questions.index(question)
    if question_index == 0:
        return True
    previous_question = all_questions[question_index - 1]
    question_scores = question_score(user_answer, previous_question)
    return question_scores == MAX_SCORE


def valid_score(user_answer: models.UserAnswer, answer: models.BelbinAnswer, score: int) -> bool:
    MAX_SCORE = 10
    total_score: int = question_score(user_answer, answer.question)
    current_answer_score: int = get_answer_score(user_answer, answer)
    return total_score - current_answer_score + int(score) <= MAX_SCORE


def belbin_finished(user: User):
    user_answer: UserAnswer | None = UserAnswer.objects.filter(user=user).first()
    if user_answer:
        if user_answer.answer["belbin"]["status"] == "finished":
            return True
    return False


# Here we save the user neo answers
def get_neo_question(user_answer, question: NeoQuestion) -> None | dict:
    question_id = str(question.id)
    answers = user_answer.neo_answer["answers"]
    return answers.get(question_id)


def save_neo_answer(user_answer: UserAnswer, question: NeoQuestion, answer: str):
    number = question.number
    last_neo_question = NeoQuestion.objects.order_by("number").last()

    if last_neo_question is not None and number == last_neo_question.number:
        user_answer.neo_answer["status"] = "finished"

    answers = user_answer.neo_answer["answers"]

    if get_neo_question(user_answer, question) is None:
        answers[str(question.id)] = {}

    answers[str(question.id)] = answer

    user_answer.save()


# Here we calculate the user Neo Exam score
def get_question_ids_by_type(question_type):
    return [
        str(uuid)
        for uuid in models.NeoQuestion.objects.filter(question_type=question_type).values_list("id", flat=True)
    ]


def calculate_score(answers, question_ids):
    options = models.NeoOption.objects.filter(id__in=[answers[key] for key in question_ids if key in answers])
    return sum(option.option_score for option in options)


def user_neo_score(user: User):
    user_answer: models.UserAnswer | None = models.UserAnswer.objects.filter(user=user).first()
    if not user_answer:
        raise ValidationError("آزمونی برای این کاربر یافت نشد!")

    answers: dict = user_answer.answer["neo"]["answers"]

    experience = get_question_ids_by_type("ES")
    duty = get_question_ids_by_type("DS")
    objective = get_question_ids_by_type("OS")
    compatible = get_question_ids_by_type("CS")
    neuro = get_question_ids_by_type("NS")

    result = {
        "experience_score": calculate_score(answers, experience),
        "duty_score": calculate_score(answers, duty),
        "objective_score": calculate_score(answers, objective),
        "compatible_score": calculate_score(answers, compatible),
        "neuro_score": calculate_score(answers, neuro),
    }
    return result


# general question
def parse_general_answer(data: Dict):
    """
    example data : {"question": "something", "answer" : "something" }
    """
    return {str(data["question"]): str(data["answer"])}


def save_general_answer(user_answer: models.UserAnswer, parsed_date: dict, exam: models.GeneralExam):
    exam_answers: dict = user_answer.get_general_by_exam(exam)
    if exam_answers == {}:
        raise ValidationError("شروع آزمون ثبت نشده است!")

    exam_answers.update(parsed_date)
    user_answer.answer["general"]["answers"][str(exam.id)] = exam_answers
    # finish_general_answer(user_answer, exam)
    user_answer.save()


# Checking the next question and return it
def check_user_next_question(user, exam, model):
    user_answer, _ = models.UserAnswer.objects.get_or_create(user=user)
    answered_question = user_answer.answer[exam]["answers"]
    answered_question_list = list(answered_question.keys())

    if len(answered_question_list) == 0:
        next_question = model.objects.order_by("number").first()
        if not next_question:
            raise ValidationError("سوالی برای این آزمون وجود تدارد!")
        return next_question

    answered_question_list.sort(key=lambda qid: model.objects.get(id=UUID(qid)).number)
    _question = model.objects.filter(id=UUID(answered_question_list[-1])).first()

    if not _question:
        raise ValidationError("سوال یافت نشد!")

    next_question = model.objects.order_by("number").filter(number__gt=_question.number).first()

    if not next_question:
        raise ValidationError("سوال ها به پایان رسیده است!")

    return next_question


def check_valid_time(user_answer: models.UserAnswer, exam: models.GeneralExam) -> bool:
    exam_answers: dict = user_answer.get_general_by_exam(exam)
    if exam_answers == {}:
        return True
    started_datetime = datetime.datetime.strptime(exam_answers["started"], "%d/%m/%Y, %H:%M:%S")
    valid_time = started_datetime + datetime.timedelta(minutes=exam.time)
    if datetime.datetime.now() > valid_time:
        return False
    return True


def finish_general_answer(user_answer: models.UserAnswer, exam: models.GeneralExam):
    # NON_QUESTION_KEY_COUNT = 2
    # exam_question_number = models.GeneralQuestion.objects.filter(exam=exam).count()
    # answer_question_number = len(user_answer.get_general_by_exam(exam).keys()) - NON_QUESTION_KEY_COUNT
    if user_answer.get_general_by_exam(exam):
        # start_time = user_answer.get_general_by_exam(exam)["started"]
        # remain = calc_exam_remain_time(start_time, exam.time)
        # if remain <= 0 or exam_question_number == answer_question_number:
        user_answer.get_general_by_exam(exam)["status"] = "finished"
        user_answer.get_general_by_exam(exam)["finished"] = datetime.datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
        user_answer.save()
        return True
    return False


def calculate_general_exam_score(user_answer: models.UserAnswer, exam: models.GeneralExam) -> None | int:
    total_score: int = 0
    answers = user_answer.get_general_by_exam(exam)
    if answers != {} and answers["status"] == "finished":
        for question, answer in answers.items():
            try:
                answer_id = UUID(answer)
                question_id = UUID(question)
            except ValueError:
                continue
            option = models.GeneralQuestionOption.objects.filter(
                id=answer_id, question_id=question_id, correct_answer=True
            ).first()
            if option is not None:
                total_score += option.question.score
        return total_score


# For returning the next or previous closest question.
def get_question(current_question, exam, state):
    if exam == "belbin":
        model = models.BelbinQuestion
    else:
        model = models.NeoQuestion

    question_numbers = model.objects.all().values_list("number", flat=True)
    last_question_number = max(question_numbers)

    if state == "next":
        if current_question.number == last_question_number:
            return Response("سوال ها به پایان رسیده است!")

        next_question = model.objects.order_by("number").filter(number__gt=current_question.number).first()
        if next_question:
            return next_question

    if state == "previous":
        previous_question = model.objects.order_by("number").filter(number__lt=current_question.number).last()
        if previous_question:
            return previous_question
        else:
            return current_question

    return None


# For create and update the general exam question and its options in same time
def create_general_question(exam_id, question_data, serializer):
    question_data.update({"exam": exam_id})
    question_serializer = serializer(data=question_data)
    question_serializer.is_valid(raise_exception=True)
    question = question_serializer.save()
    return question


def create_general_option(option_data, question, serializer):
    errors = []
    valid_options = []
    for key, value in option_data.items():
        value.update({"question": question.id})
        option_serializer = serializer(data=value)
        if not option_serializer.is_valid():
            errors.append(f"Error in option number {key}: {option_serializer.errors}")
        else:
            valid_options.append(option_serializer)

    if errors:
        return {"status": False, "detail": errors}

    for option_serializer in valid_options:
        option_serializer.save()
    return {"status": True, "data": [serializer.data for serializer in valid_options]}


def update_general_question(exam_id, question_data, serializer):
    question_data.update({"exam": exam_id})
    question_instance = get_object_or_404(models.GeneralQuestion, pk=question_data["id"])
    question_serializer = serializer(instance=question_instance, data=question_data, partial=True)
    question_serializer.is_valid(raise_exception=True)
    question = question_serializer.save()
    return question


def update_general_option(question, option_data, serializer):
    valid_options = []
    errors = []
    for value in option_data.values():
        value.update({"question": question.id})
        if not value.get("id", None):
            option_serializer = serializer(data=value)
        else:
            option_serializer = serializer(data=value)

        if not option_serializer.is_valid():
            errors.append(f"Error in option with ID {value['id']}: {option_serializer.errors}")
        else:
            valid_options.append(option_serializer)

    if errors:
        return {"status": False, "detail": errors}

    models.GeneralQuestionOption.objects.filter(question=question).delete()
    for option_serializer in valid_options:
        option_serializer.save()

    return {"status": True, "data": [serializer.data for serializer in valid_options]}


def calc_exam_remain_time(start_time, exam_time):
    diff = round(
        abs(
            (datetime.datetime.strptime(start_time, "%d/%m/%Y, %H:%M:%S") - datetime.datetime.now()).total_seconds()
            / 60
        )
    )
    remain = exam_time - diff
    return remain


def get_neo_options_value(question, value):
    for k, v in question.items():
        if k == value:
            return v
    return None


def get_user_exam_status(user, exam_type, exam_id=None):
    """If user finished the desired exam, returns True, else returns False"""

    user_answer = models.UserAnswer.objects.filter(user=user).first()
    if not user_answer:
        return False

    if exam_type == "B":
        answer = user_answer.answer["belbin"]["status"]
        if answer == "started":
            return False

    if exam_type == "N":
        answer = user_answer.answer["neo"]["status"]
        if answer == "started":
            return False

    if exam_type in ["P", "E"]:
        answer = user_answer.answer["general"]["answers"].get(exam_id, None)
        if not answer:
            return False

        answer_status = answer["status"]
        if answer_status == "started":
            return False

    return True
