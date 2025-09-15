from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from apps.settings.models import Province

from apps.common.models import BaseModel
from apps.settings.models import ConnectionWay, ForeignLanguage, StudyField, University


def default_resume_step() -> dict:
    return {"1": "started"}


def default_last_step() -> dict:
    return {
        "project": "started",
        "language": "started",
        "certification": "started",
        "connection_ways": "started",
    }


SKILL_LEVEL = [("EL", "مبتدی"), ("IN", "متوسط"), ("AD", "پیشرفته")]


class Resume(BaseModel):
    RESUME_STATUS = [("CR", "ایجاد شده"), ("CO", "تایید شده")]

    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, verbose_name="کاربر", related_name="resume")
    status = models.CharField(max_length=2, choices=RESUME_STATUS, default="CR", verbose_name="وضعیت")
    steps = models.JSONField(default=default_resume_step)
    team_formation_province = models.ForeignKey(
        Province,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='team_formation_resumes',
        verbose_name="استان محل تشکیل تیم",
        help_text="استان محل سکونت/کار برای تشکیل تیم. این فیلد برای برنامه‌ریزی جلسات حضوری استانی استفاده می‌شود."
    )

    @property
    def resume_completed(self):
        second_step = "2"

        if second_step not in self.steps or self.steps[f"{second_step}"] == "started":
            return False

        return True

    def next_step(self, current_step: int) -> None:
        FIRST_STEP = 1

        if current_step != "4" and self.steps.get(str(current_step - 1)) != "finished" and current_step != FIRST_STEP:
            raise FieldDoesNotExist("این مرحله، مرحله قبلی ندارد")

        self.steps[str(current_step)] = "finished"

        if self.steps.get(str(current_step + 1)) != "finished":
            self.steps[str(current_step + 1)] = "started"

        self.save()

    def finish_flow(self) -> None:
        LAST_STEP = 5
        last_confirmed_step = list(self.steps.keys())[-1]
        if int(last_confirmed_step) == (LAST_STEP - 1):
            self.steps[last_confirmed_step] = "finished"
            self.steps[str(LAST_STEP)] = default_last_step()
            self.save()

    def finish_sub_step(self, sub_step: str) -> None:
        LAST_STEP = "5"
        if LAST_STEP not in self.steps:
            self.steps[LAST_STEP] = {}
        self.steps[LAST_STEP][sub_step] = "finished"
        self.save()

    def __str__(self):
        return str(self.user)

    class Meta(BaseModel.Meta):
        verbose_name = "رزومه"
        verbose_name_plural = "رزومه ها"


class Education(BaseModel):
    GRADE = [
        ("DI", "دیپلم"),
        ("AD", "کاردانی"),
        ("BA", "کارشناسی"),
        ("MA", "کارشناسی ارشد"),
        ("PD", "دکتری"),
    ]

    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="educations",
        verbose_name="رزومه(کاربر)",
    )
    grade = models.CharField(max_length=3, choices=GRADE, verbose_name="مقطع تحصیلی")
    field = models.ForeignKey(StudyField, on_delete=models.PROTECT, verbose_name="رشته تحصیلی")
    university = models.ForeignKey(
        University,
        on_delete=models.PROTECT,
        related_name="resumes",
        verbose_name="دانشگاه",
    )
    start_date = models.DateField(verbose_name="تاریخ شروع")
    end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ پایان")

    class Meta(BaseModel.Meta):
        verbose_name = "مقطع تحصیلی"
        verbose_name_plural = "مقاطع تحصیلی"


class WorkExperience(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="jobs",
        verbose_name="رزومه(کاربر)",
    )
    job_title = models.CharField(max_length=255, verbose_name="عنوان شغلی")
    company_name = models.CharField(max_length=255, verbose_name="نام شرکت")
    start_date = models.DateField(verbose_name="تاریخ شروع")
    end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ پایان")

    class Meta(BaseModel.Meta):
        verbose_name = "سابقه شغلی"
        verbose_name_plural = "سوابق شغلی"

    @property
    def until_now(self):
        return self.end_date is not None


class Skill(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="skills",
        verbose_name="رزومه(کاربر)",
    )
    skill_name = models.ForeignKey("settings.Skill", on_delete=models.PROTECT, null=True, verbose_name="نام مهارت")
    level = models.CharField(max_length=2, choices=SKILL_LEVEL, verbose_name="سطح تسلط")

    class Meta(BaseModel.Meta):
        verbose_name = "مهارت"
        verbose_name_plural = "مهارت ها"


class Language(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="languages",
        verbose_name="رزومه(کاربر)",
    )
    language_name = models.ForeignKey(ForeignLanguage, on_delete=models.PROTECT, verbose_name="نام زبان")
    level = models.CharField(max_length=2, choices=SKILL_LEVEL, verbose_name="سطح تسلط")

    class Meta(BaseModel.Meta):
        verbose_name = "زبان خارجی"
        verbose_name_plural = "زبان های خارجی"


class Certificate(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name="رزومه(کاربر)",
    )
    certificate_title = models.CharField(max_length=255, verbose_name="عنوان گواهی نامه")
    institution = models.CharField(max_length=255, verbose_name="موسسه صادرکننده")
    issue_date = models.DateField(null=True, blank=True, verbose_name="تاریخ صدور")
    description = models.TextField(null=True, blank=True, verbose_name="توضیحات")
    link = models.URLField(max_length=255, null=True, blank=True, verbose_name="لینک گواهی نامه")
    file = models.FileField(
        upload_to="resume/certificates",
        null=True,
        blank=True,
        verbose_name="فایل گواهی نامه",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "گواهی نامه"
        verbose_name_plural = "گواهی نامه ها"


class Connection(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="connections",
        verbose_name="رزومه(کاربر)",
    )
    title = models.ForeignKey(ConnectionWay, on_delete=models.PROTECT, null=True, blank=True, verbose_name="عنوان")
    link = models.CharField(null=True, blank=True, max_length=255, verbose_name="لینک")
    telegram = models.CharField(max_length=50, null=True, verbose_name="لینک تلگرام")

    class Meta(BaseModel.Meta):
        verbose_name = "راه ارتباطی"
        verbose_name_plural = "راه های ارتباطی"


class Project(BaseModel):
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name="resume_projects",
        verbose_name="رزومه(کاربر)",
    )
    title = models.CharField(max_length=255, verbose_name="عنوان پروژه")
    description = models.TextField(null=True, blank=True, verbose_name="توضیحات")
    start_date = models.DateField(null=True, verbose_name="تاریخ شروع پروژه")
    end_date = models.DateField(verbose_name="تاریخ پایان پروژه")

    class Meta(BaseModel.Meta):
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه ها"
