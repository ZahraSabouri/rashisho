from datetime import timezone
from django.conf import settings
import filetype
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from rest_framework.exceptions import ValidationError

from apps.common.models import BaseModel
from apps.project.services import validate_persian
from apps.settings.models import StudyField

from django.contrib.contenttypes.fields import GenericRelation

class Tag(BaseModel):
    """
    Model for project keywords/tags.
    Allows categorization and discovery of related projects.
    """
    class TagCategory(models.TextChoices):
        SKILL = "SKILL", "مهارت"
        TECHNOLOGY = "TECH", "فناوری"
        DOMAIN = "DOMAIN", "حوزه"
        KEYWORD = "KEYWORD", "کلیدواژه"
    
    name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="نام تگ",
        help_text="نام کلیدواژه (مثال: python, django, machine-learning)"
    )
    category = models.CharField(
        max_length=10,
        choices=TagCategory.choices,
        default=TagCategory.KEYWORD,
        verbose_name="دسته‌بندی",
        help_text="نوع تگ: مهارت، فناوری، حوزه یا کلیدواژه عمومی"
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
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
    
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


class ProjectPhase(models.TextChoices):
    BEFORE_SELECTION = "BEFORE", "قبل از انتخاب"
    SELECTION_ACTIVE = "ACTIVE", "در حال انتخاب" 
    SELECTION_FINISHED = "FINISHED", "پایان انتخاب"


class ProjectSelection(BaseModel):
    """
    Normalized table for tracking user project selections.
    Replaces complex JSONB queries with simple relational queries.
    """
    user = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE, 
        related_name='project_selections',
        verbose_name="کاربر"
    )
    project = models.ForeignKey(
        'Project', 
        on_delete=models.CASCADE, 
        related_name='selections',
        verbose_name="پروژه"
    )
    priority = models.IntegerField(
        choices=[(1, '1st'), (2, '2nd'), (3, '3rd'), (4, '4th'), (5, '5th')],
        verbose_name="اولویت"
    )
    
    class Meta(BaseModel.Meta):
        unique_together = [
            ('user', 'priority'),  # User can't select 2 projects for same priority
            ('user', 'project'),   # User can't select same project twice
        ]
        verbose_name = "انتخاب پروژه"
        verbose_name_plural = "انتخاب‌های پروژه"
    
    def __str__(self):
        return f"{self.user.full_name} - {self.project.title} (اولویت {self.priority})"

class ProjectAttractiveness(BaseModel):
    """
    One row == one user's 'heart' on one project.
    - Users may heart multiple projects
    - A user can only heart a project once
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_attractiveness_votes",
        verbose_name="کاربر",
    )
    project = models.ForeignKey(
        "project.Project",
        on_delete=models.CASCADE,
        related_name="attractiveness_votes",
        verbose_name="پروژه",
    )

    class Meta(BaseModel.Meta):
        unique_together = ("user", "project")
        verbose_name = "رأی جذابیت"
        verbose_name_plural = "رأی‌های جذابیت"

    def __str__(self) -> str:
        return f"{self.user_id} ❤️ {self.project_id}"


class Project(BaseModel):
    code = models.CharField(max_length=300, unique=True, null=True, verbose_name="کد")
    title = models.CharField(max_length=300, verbose_name="عنوان")
    summary = models.TextField(
    max_length=200,  # Approximately 2 lines of text
    blank=True,
    null=True,
    verbose_name="خلاصه پروژه",
    help_text="خلاصه کوتاه و جذاب پروژه در حداکثر دو خط (200 کاراکتر)"
    )
    image = models.ImageField(upload_to="project/images", verbose_name="تصویر")
    company = models.CharField(max_length=300, verbose_name="شرکت تعریف کننده پروژه")
    leader = models.CharField(max_length=300, null=True, verbose_name="نام راهبر پروژه")
    leader_position = models.CharField(max_length=255, null=True, verbose_name="سمت راهبر پروژه")
    study_fields = models.ManyToManyField(StudyField, verbose_name="رشته های تحصیلی")
    description = models.TextField(verbose_name="توضیحات")
    video = models.FileField(null=True, upload_to="project/videos", verbose_name="ویدئو", blank=True)
    visible = models.BooleanField("قابل مشاهده", default=True, help_text="پروژه برای کاربران قابل مشاهده باشد")
    file = models.FileField(upload_to="project/files", null=True, blank=True, verbose_name="فایل")
    # start_date = models.DateField(null=True, blank=True, verbose_name="تاریخ شروع")
    # end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ پایان")
    tags = models.ManyToManyField(
        Tag, 
        blank=True, 
        related_name="projects", 
        verbose_name="کلیدواژه ها",
        help_text="کلیدواژه‌های مرتبط با این پروژه برای بهتر یافت شدن و پیشنهاد پروژه‌های مرتبط"
    )
    is_active = models.BooleanField(
        "فعال", 
        default=True,
        help_text="وضعیت فعال/غیرفعال پروژه. پروژه‌های غیرفعال قابل انتخاب نیستند اما مشاهده می‌شوند."
    )
    selection_phase = models.CharField(
        max_length=10,
        choices=ProjectPhase.choices,
        default=ProjectPhase.BEFORE_SELECTION,
        verbose_name="فاز انتخاب"
    )
    selection_start = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="شروع انتخاب"
    )
    selection_end = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="پایان انتخاب"
    )
    auto_phase_transition = models.BooleanField(
        default=True,
        verbose_name="تغییر خودکار فاز",
        help_text="آیا فاز بر اساس تاریخ شروع و پایان تغییر کند؟"
    )
    
    
    @property
    def current_phase(self):
        """
        Get current phase for this project.
        Auto-calculates based on dates if auto_phase_transition is True,
        otherwise uses manual selection_phase.
        """
        if self.auto_phase_transition and self.selection_start and self.selection_end:
            now = timezone.now()
            if now < self.selection_start:
                return ProjectPhase.BEFORE_SELECTION
            elif now <= self.selection_end:
                return ProjectPhase.SELECTION_ACTIVE
            else:
                return ProjectPhase.SELECTION_FINISHED
        
        # Use manually set phase
        return self.selection_phase
    
    @property
    def can_be_selected(self):
        """Can users select this project right now?"""
        return self.current_phase == ProjectPhase.SELECTION_ACTIVE and self.is_active and self.visible
    
    @property
    def show_attractiveness(self):
        """Should attractiveness count be shown?"""
        return self.current_phase in [ProjectPhase.SELECTION_ACTIVE, ProjectPhase.SELECTION_FINISHED]
    
    @property
    def phase_display(self):
        """Human readable phase status"""
        phase = self.current_phase
        if self.auto_phase_transition and self.selection_start and self.selection_end:
            return f"{ProjectPhase(phase).label} (خودکار)"
        return ProjectPhase(phase).label
    
    def update_phase_if_needed(self):
        """
        Update the database phase if auto-transition is enabled and phase changed.
        Call this periodically or in views to keep DB in sync.
        """
        if self.auto_phase_transition:
            current = self.current_phase
            if current != self.selection_phase:
                self.selection_phase = current
                self.save(update_fields=['selection_phase'])

    @property 
    def comments_count(self):
        """تعداد نظرات تایید شده این پروژه"""
        try:
            from apps.comments.utils import get_comment_count
            return get_comment_count('project.project', self.id)
        except ImportError:
            return 0
    
    @property
    def pending_comments_count(self):
        """تعداد نظرات در انتظار تایید این پروژه"""
        try:
            from apps.comments.utils import get_comment_count
            return get_comment_count('project.project', self.id, 'PENDING')
        except ImportError:
            return 0
    
    def get_comments(self, status='APPROVED', limit=None):
        """دریافت نظرات این پروژه"""
        try:
            from apps.comments.services import ProjectCommentService
            comments = ProjectCommentService.get_project_comments(self.id)
            if limit:
                return comments[:limit]
            return comments
        except ImportError:
            return []
    
    def get_latest_comments(self, limit=5):
        """دریافت آخرین نظرات این پروژه"""
        return self.get_comments(limit=limit)
    
    def get_comment_statistics(self):
        """دریافت آمار نظرات این پروژه"""
        try:
            from apps.comments.services import ProjectCommentService
            return ProjectCommentService.get_project_comment_summary(self.id)
        except ImportError:
            return {
                'total': 0,
                'approved': 0,
                'pending': 0,
                'rejected': 0,
                'total_likes': 0,
                'total_dislikes': 0
            }
    
    @property
    def has_comments(self):
        """آیا این پروژه نظراتی دارد؟"""
        return self.comments_count > 0
    
    @property
    def comment_engagement_rate(self):
        """نرخ مشارکت در نظرات (نظرات به ازای هر بازدید - اگر سیستم view tracking داشته باشیم)"""
        # این محاسبه نیاز به سیستم tracking بازدید دارد
        # فعلاً یک نسبت ساده برمی‌گردانیم
        comments = self.comments_count
        if comments == 0:
            return 0
        # فرض می‌کنیم هر پروژه حداقل 100 بازدید دارد (می‌تواند از سیستم analytics واقعی بیاید)
        estimated_views = max(100, comments * 10)  
        return round((comments / estimated_views) * 100, 2)



    class Meta(BaseModel.Meta):
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه ها"
        indexes = [
            models.Index(fields=['is_active', 'visible']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        """Validate project data"""
        super().clean()
        # if self.start_date and self.end_date:
        #     if self.start_date >= self.end_date:
        #         raise ValidationError("تاریخ شروع باید کمتر از تاریخ پایان باشد")

    def save(self, *args, **kwargs):
        if not self.code:
            from apps.project.services import generate_project_unique_code
            self.code = generate_project_unique_code()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def can_be_selected(self):
        """Check if project can be selected by users"""
        return self.visible and self.is_active

    @property
    def status_display(self):
        """Return user-friendly status"""
        if not self.visible:
            return "مخفی"
        elif not self.is_active:
            return "غیرفعال"
        else:
            return "فعال"

    @property
    def tags_list(self):
        """Return list of tag names"""
        return [tag.name for tag in self.tags.all()]

    def get_related_projects(self, limit=5):
        """Find related projects based on shared tags"""
        if not self.tags.exists():
            return self.__class__.objects.none()
        
        return self.__class__.objects.filter(
            tags__in=self.tags.all(),
            visible=True,
            is_active=True  # Only show active projects in recommendations
        ).exclude(
            id=self.id
        ).annotate(
            shared_tags_count=models.Count('tags', filter=models.Q(tags__in=self.tags.all()))
        ).filter(
            shared_tags_count__gt=0
        ).order_by('-shared_tags_count')[:limit]

    @property
    def status_display(self):
        """Return user-friendly status"""
        if not self.visible:
            return "مخفی"
        elif not self.is_active:
            return "غیرفعال"
        else:
            return "فعال"

    def activate(self):
        """Activate the project"""
        self.is_active = True
        self.save(update_fields=['is_active'])

    def deactivate(self):
        """Deactivate the project"""
        self.is_active = False
        self.save(update_fields=['is_active'])

    # def __str__(self):
    #     return self.title

    def __str__(self) -> str:
        status_emoji = "✅" if self.is_active else "❌"
        return f"{status_emoji} {self.title}"
    
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
