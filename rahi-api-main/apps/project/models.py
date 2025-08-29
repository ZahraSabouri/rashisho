import filetype
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from rest_framework.exceptions import ValidationError

from apps.common.models import BaseModel
from apps.project.services import validate_persian
from apps.settings.models import StudyField


class Tag(BaseModel):
    """
    Model for project keywords/tags.
    Allows categorization and discovery of related projects.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="نام تگ",
        help_text="نام کلیدواژه (مثال: python, django, machine-learning)"
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="توضیحات",
        help_text="توضیح مختصری درباره این کلیدواژه"
    )
    
    class Meta(BaseModel.Meta):
        verbose_name = "کلیدواژه"
        verbose_name_plural = "کلیدواژه ها"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Clean and validate tag name"""
        if self.name:
            self.name = self.name.strip().lower()
            if len(self.name) < 2:
                raise ValidationError("نام تگ باید حداقل 2 کاراکتر باشد")


def project_priority() -> dict:
    return {
        "1": None,
        "2": None,
        "3": None,
        "4": None,
        "5": None,
    }


def validate_file_type(value):
    kind = filetype.guess(value.file.read())

    if kind is None:
        raise ValidationError("نوع فایل قابل شناسایی نیست.")

    mime_type = kind.mime

    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    if mime_type not in allowed_types:
        raise ValidationError("نوع فایل غیرمجاز است.")


def validate_user_task_file_type(value):
    kind = filetype.guess(value.file.read())
    max_size = 70 * 1024 * 1024
    if value.size > max_size:
        raise ValidationError("حجم فایل نباید بیشتر از 70 مگابایت باشد.")

    if kind is None:
        raise ValidationError("نوع فایل قابل شناسایی نیست.")

    mime_type = kind.mime

    allowed_types = [
        "application/zip",
        "application/x-rar-compressed",
    ]

    if mime_type not in allowed_types:
        raise ValidationError("نوع فایل غیرمجاز است.")


class Project(BaseModel):
    code = models.CharField(max_length=300, unique=True, null=True, verbose_name="کد")
    title = models.CharField(max_length=300, verbose_name="عنوان")
    image = models.ImageField(upload_to="project/images", verbose_name="تصویر")
    company = models.CharField(max_length=300, verbose_name="شرکت تعریف کننده پروژه")
    leader = models.CharField(max_length=300, null=True, verbose_name="نام راهبر پروژه")
    leader_position = models.CharField(max_length=255, null=True, verbose_name="سمت راهبر پروژه")
    study_fields = models.ManyToManyField(StudyField, verbose_name="رشته های تحصیلی")
    description = models.TextField(verbose_name="توضیحات")
    video = models.FileField(null=True, upload_to="project/videos", verbose_name="ویدئو", blank=True)
    visible = models.BooleanField(default=True, verbose_name="نمایش در صفحه اصلی")
    file = models.FileField(upload_to="project/files", null=True, blank=True, verbose_name="فایل")
    telegram_id = models.CharField(max_length=255, null=True, verbose_name="آدرس تلگرام")

    tags = models.ManyToManyField(
        Tag, 
        blank=True, 
        related_name="projects", 
        verbose_name="کلیدواژه ها",
        help_text="کلیدواژه‌های مرتبط با این پروژه برای بهتر یافت شدن و پیشنهاد پروژه‌های مرتبط"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه ها"

    def __str__(self):
        return self.title
    
    def get_related_projects(self, limit=6):
        """Get projects with shared tags"""
        if not self.tags.exists():
            return Project.objects.none()
        
        return Project.objects.filter(
            tags__in=self.tags.all(),
            visible=True
        ).exclude(
            id=self.id
        ).annotate(
            shared_tags_count=models.Count('tags', filter=models.Q(tags__in=self.tags.all()))
        ).filter(
            shared_tags_count__gt=0
        ).order_by('-shared_tags_count')[:limit]


class ProjectAllocation(BaseModel):
    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="project", verbose_name="کاربر"
    )
    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, null=True, blank=True, related_name="allocations", verbose_name="پروژه"
    )
    priority = models.JSONField(default=project_priority, verbose_name="الویت پروژه ها")

    class Meta(BaseModel.Meta):
        verbose_name = "تخصیص پروژه"
        verbose_name_plural = "تخصیص پروژه ها"

    @property
    def priority_selected(self):
        priority_values = self.priority.values()
        status = False
        for value in priority_values:
            if value:
                status = True
                break

        return status

    def __str__(self):
        return self.user.full_name


class FinalRepresentation(BaseModel):
    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="representations", verbose_name="کاربر"
    )
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="representations", verbose_name="پروژه")
    file = models.FileField(upload_to="project/representations", validators=[validate_file_type], verbose_name="فایل")

    class Meta(BaseModel.Meta):
        verbose_name = "ارائه نهایی"
        verbose_name_plural = "ارائه های نهایی"

    @property
    def has_representation(self):
        status = False
        if self.file:
            status = True
        return status

    def __str__(self):
        return f"{self.project.title} - {self.user.full_name}"


class Scenario(BaseModel):
    number = models.PositiveSmallIntegerField(
        null=True, validators=[MinValueValidator(1), MaxValueValidator(3)], verbose_name="شماره"
    )
    title = models.CharField("عنوان", max_length=150)
    description = models.TextField("توضیحات")
    first_file = models.FileField("فایل اول")
    second_file = models.FileField("فایل دوم")
    project = models.ForeignKey(Project, models.CASCADE, related_name="project_scenario", verbose_name="پروژه")

    class Meta(BaseModel.Meta):
        verbose_name = "سناریو"
        verbose_name_plural = "سناریو ها"

    def __str__(self) -> str:
        return self.title


class Task(BaseModel):
    number = models.PositiveSmallIntegerField(
        null=True, validators=[MinValueValidator(1), MaxValueValidator(3)], verbose_name="شماره"
    )
    title = models.CharField("عنوان", max_length=150)
    description = models.TextField("توضیحات")
    first_file = models.FileField("فایل اول")
    second_file = models.FileField(null=True, blank=True, verbose_name="فایل دوم")
    project = models.ForeignKey(Project, models.CASCADE, related_name="project_task", verbose_name="پروژه")
    is_active = models.BooleanField(default=False, verbose_name="فعال")

    class Meta(BaseModel.Meta):
        verbose_name = "کارویژه"
        verbose_name_plural = "کارویژه ها"

    def __str__(self) -> str:
        return self.title


class ProjectDerivatives(BaseModel):
    # set type
    TYPE = [("P", "پروپوزال"), ("F", "ارائه نهایی")]
    project = models.ForeignKey(Project, models.CASCADE, related_name="project_derivatives", verbose_name="پروژه")
    derivatives_type = models.CharField("نوع مشتقات پروژه", max_length=20, choices=TYPE)

    # set value
    number = models.PositiveSmallIntegerField(
        null=True, validators=[MinValueValidator(1), MaxValueValidator(3)], verbose_name="شماره"
    )
    title = models.CharField("عنوان", max_length=150)
    description = models.TextField("توضیحات")
    first_file = models.FileField("فایل")

    class Meta(BaseModel.Meta):
        verbose_name = "مشتقات پروژه"
        verbose_name_plural = "مشتقات پروژه"

    def __str__(self) -> str:
        return self.title


class UserScenarioTaskFile(BaseModel):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="scenario_task_files", verbose_name="کاربر"
    )
    scenario = models.ForeignKey(
        Scenario, on_delete=models.PROTECT, null=True, blank=True, related_name="scenario_files", verbose_name="سناریو"
    )
    task = models.ForeignKey(
        Task, on_delete=models.PROTECT, null=True, blank=True, related_name="task_files", verbose_name="کارویژه"
    )
    derivatives = models.ForeignKey(
        ProjectDerivatives,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="derivatives_files",
        verbose_name="مشتقات پروژه",
    )

    file = models.FileField(validators=[validate_user_task_file_type], verbose_name="فایل")

    class Meta(BaseModel.Meta):
        verbose_name = "فایل سناریو و کارویژه کاربر"
        verbose_name_plural = "فایل های سناریو و کارویژه کاربر"

    def __str__(self):
        return self.user.full_name


class Team(BaseModel):
    title = models.CharField(max_length=300, validators=[validate_persian, MinLengthValidator(3)], verbose_name="نام")
    description = models.TextField(null=True, verbose_name="توضیحات")
    count = models.PositiveSmallIntegerField(
        null=True, validators=[MinValueValidator(2), MaxValueValidator(6)], verbose_name="تعداد اعضا"
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="teams", verbose_name="پروژه")
    create_date = models.DateField(null=True, verbose_name="تاریخ تشکیل تیم")

    class Meta(BaseModel.Meta):
        verbose_name = "تیم"
        verbose_name_plural = "تیم ها"

    def __str__(self) -> str:
        return self.title


class TeamRequest(BaseModel):
    REQUEST_STATUS = [("A", "قبول"), ("R", "رد"), ("W", "در انتظار")]
    USER_ROLE = [("C", "ایجاد کننده"), ("M", "عضو")]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="requests", verbose_name="تیم")
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="team_requests", verbose_name="کاربر"
    )
    status = models.CharField(max_length=1, choices=REQUEST_STATUS, default="W", verbose_name="وضعیت درخواست")
    user_role = models.CharField(max_length=1, choices=USER_ROLE, verbose_name="نقش در تیم")
    description = models.TextField(null=True, verbose_name="توضیحات")

    class Meta(BaseModel.Meta):
        verbose_name = "درخواست هم تیمی"
        verbose_name_plural = "درخواست های هم تیمی"

    def __str__(self) -> str:
        return f"{self.user.full_name} - {self.team.title}"
