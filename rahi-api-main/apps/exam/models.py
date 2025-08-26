from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import BaseModel
from apps.project.models import Project

User = get_user_model()


def default_user_answer():
    return {
        "belbin": {"status": "started", "answers": {}, "started": None},
        "neo": {"status": "started", "answers": {}},
        "general": {"status": "started", "answers": {}, "started": None},
    }


def default_neo_options() -> dict:
    return {
        "1": "کاملا موافقم",
        "2": "موافقم",
        "3": "نظری ندارم",
        "4": "مخالفم",
        "5": "کاملا مخالفم",
    }


EXAM_TYPE = (
    ("P", "عمومی"),
    ("E", "ورودی"),
    ("B", "بلبین"),
    ("N", "نئو"),
)


class BelbinQuestion(BaseModel):
    title = models.CharField("عنوان", max_length=200, unique=True)
    number = models.PositiveIntegerField("شماره", unique=True)

    class Meta(BaseModel.Meta):
        verbose_name = "سوال آزمون بلبین"
        verbose_name_plural = "سوال های آزمون بلبین"

    def __str__(self) -> str:
        return self.title


class BelbinAnswer(BaseModel):
    answer = models.TextField("جواب")
    question = models.ForeignKey(
        BelbinQuestion, on_delete=models.CASCADE, related_name="belbin_answer_question", verbose_name="جواب ها"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "گزینه آزمون بلبین"
        verbose_name_plural = "گزینه های آزمون بلبین"

    def __str__(self) -> str:
        return f"{self.answer} {self.question.title}"


class NeoQuestion(BaseModel):
    QUESTION_TYPE = (
        ("ES", "تجربه پذیری"),
        ("DS", "وظیفه شناسی"),
        ("OS", "برونگرایی"),
        ("CS", "سازگاری"),
        ("NS", "روان رنجوری"),
    )
    question_type = models.CharField(max_length=2, choices=QUESTION_TYPE, default="ES", verbose_name="نوع سوال")
    number = models.PositiveIntegerField(unique=True, verbose_name="شماره")
    title = models.CharField(max_length=200, unique=True, verbose_name="عنوان سوال")
    options = models.JSONField(default=default_neo_options, null=True, verbose_name="گزینه ها")

    class Meta(BaseModel.Meta):
        verbose_name = "سوال آزمون نئو"
        verbose_name_plural = "سوال های آزمون نئو"

    def __str__(self):
        return f"{self.number} - {self.title}"


class NeoOption(BaseModel):
    question = models.ForeignKey(NeoQuestion, on_delete=models.CASCADE, verbose_name="سوال")
    option_number = models.PositiveSmallIntegerField(verbose_name="شماره")
    option = models.CharField(max_length=100, verbose_name="گزینه")
    option_score = models.PositiveSmallIntegerField(verbose_name="نمره")

    class Meta(BaseModel.Meta):
        verbose_name = "گزینه آزمون نئو"
        verbose_name_plural = "گزینه های آزمون نئو"

    def __str__(self):
        return f"{self.option_number} - {self.option}"


class GeneralExam(BaseModel):
    MODE = [("PU", "عمومی"), ("EN", "ورودی")]

    title = models.CharField("عنوان", unique=True, max_length=150)
    time = models.PositiveIntegerField("زمان")
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        verbose_name="پروژه",
        related_name="general_exam_project",
        null=True,
        blank=True,
    )
    mode = models.CharField("نوع", choices=MODE, max_length=2)

    class Meta(BaseModel.Meta):
        verbose_name = "آزمون عمومی"
        verbose_name_plural = "آزمون های عمومی"


class GeneralQuestion(BaseModel):
    title = models.TextField("عنوان")
    number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)], verbose_name="شماره")
    exam = models.ForeignKey(
        GeneralExam,
        on_delete=models.CASCADE,
        verbose_name="سوال های عمومی",
        related_name="general_question_exam",
    )
    score = models.PositiveSmallIntegerField(null=True, verbose_name="امتیاز")

    class Meta(BaseModel.Meta):
        verbose_name = "سوال آزمون عمومی"
        verbose_name_plural = "سوال های آزمون عمومی"

    def __str__(self):
        return f"{self.number} - {self.title}"


class GeneralQuestionOption(BaseModel):
    title = models.TextField("عنوان گزینه")
    question = models.ForeignKey(GeneralQuestion, on_delete=models.CASCADE, related_name="general_question_answer")
    correct_answer = models.BooleanField("جواب درست", default=False)

    class Meta(BaseModel.Meta):
        verbose_name = "گزینه آزمون عمومی"
        verbose_name_plural = "گزینه های آزمون عمومی"

    def __str__(self) -> str:
        return f"{self.question.title} | {self.title} | {self.question.exam.get_mode_display()}"


class UserAnswer(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="user_answer", verbose_name="کاربر")
    answer = models.JSONField(default=default_user_answer)

    class Meta(BaseModel.Meta):
        verbose_name = "پاسخ کاربر"
        verbose_name_plural = "پاسخ های کاربران"

    @property
    def belbin_answer(self):
        return self.answer["belbin"]

    @property
    def neo_answer(self):
        return self.answer["neo"]

    @property
    def general_answer(self):
        return self.answer["general"]

    @property
    def belbin_finished(self):
        if self.belbin_answer["status"] == "finished":
            return True
        return False

    @property
    def neo_finished(self):
        if self.neo_answer["status"] == "finished":
            return True
        return False

    def get_general_by_exam(self, exam: GeneralExam) -> dict:
        return self.answer["general"]["answers"].get(str(exam.id), {})

    def __str__(self):
        return self.user.full_name


class ExamResult(BaseModel):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="exam_results", verbose_name="کاربر"
    )
    exam_type = models.CharField(max_length=1, choices=EXAM_TYPE, verbose_name="نوع آزمون")
    exam = models.ForeignKey(
        "exam.GeneralExam", on_delete=models.PROTECT, null=True, related_name="results", verbose_name="آزمون"
    )
    result = models.CharField(null=True, verbose_name="آدرس نتیجه آزمون")

    class Meta(BaseModel.Meta):
        verbose_name = "نتیجه آزمون"
        verbose_name_plural = "نتایج آزمون ها"

    def __str__(self):
        return f"{self.user.full_name} - {self.get_exam_type_display()}"
