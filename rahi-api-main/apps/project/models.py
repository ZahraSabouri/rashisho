from django.utils import timezone
from django.conf import settings
import filetype
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from rest_framework.exceptions import ValidationError

from apps.common.models import BaseModel
from apps.project.services import validate_persian
from apps.settings.models import StudyField

from django.contrib.contenttypes.fields import GenericRelation


class TagCategory(BaseModel):
    code = models.SlugField(max_length=50, unique=True, verbose_name="کد")
    title = models.CharField(max_length=100, verbose_name="عنوان")

    class Meta(BaseModel.Meta):
        verbose_name = "دسته‌بندی تگ"
        verbose_name_plural = "دسته‌بندی‌های تگ"
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Tag(BaseModel):
    # class TagCategory(models.TextChoices):
    #     SKILL = "SKILL", "مهارت"
    #     TECHNOLOGY = "TECH", "فناوری"
    #     DOMAIN = "DOMAIN", "حوزه"
    #     KEYWORD = "KEYWORD", "کلیدواژه"

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="نام تگ",
        help_text="نام کلیدواژه (مثال: python, django, machine-learning)"
    )
    category = models.CharField(
        max_length=50,  # was 10; widen so no truncation with dynamic codes
        verbose_name="کد دسته‌بندی (سازگاری قدیمی)",
        help_text="به صورت خودکار از category_ref پر می‌شود."
    )

    category_ref = models.ForeignKey(
        "TagCategory",
        related_name="tags",
        on_delete=models.PROTECT,
        null=False,  # was nullable; we enforce it now
        blank=False,
        verbose_name="دسته‌بندی",
        help_text="ارجاع به دسته‌بندی دینامیک"
    )

    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")

    class Meta(BaseModel.Meta):
        verbose_name = "کلیدواژه"
        verbose_name_plural = "کلیدواژه ها"
        ordering = ['category', 'name']

    def __str__(self):
        label = self.category_ref.title if self.category_ref_id else self.get_category_display()
        return f"{self.name} ({label})"

    def clean(self):
        if self.name:
            self.name = self.name.strip().lower()
            if len(self.name) < 2:
                raise ValidationError("نام تگ باید حداقل 2 کاراکتر باشد")

    def save(self, *args, **kwargs):
        if self.category_ref_id:
            self.category = self.category_ref.code
        super().save(*args, **kwargs)

    def get_category_display(self):
        return self.category_ref.title if self.category_ref_id else (self.category or "")


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
            ('user', 'project'),  # User can't select same project twice
        ]
        verbose_name = "انتخاب پروژه"
        verbose_name_plural = "انتخاب‌های پروژه"

    def __str__(self):
        return f"{self.user.full_name} - {self.project.title} (اولویت {self.priority})"


class ProjectAttractiveness(BaseModel):
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
        max_length=200,
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
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="projects",
        verbose_name="گروه‌های کاربری مرتبط",
        help_text="فقط کاربران این گروه‌ها می‌توانند پروژه را ببینند/انتخاب کنند. خالی یعنی همه گروه‌ها.",
    )
    deactivation_reason = models.CharField(
        max_length=200, blank=True,
        verbose_name="علت غیرفعالسازی",
        help_text="دلیل کوتاه که در صفحه پروژه نمایش داده می‌شود وقتی پروژه غیرفعال است."
    )
    admin_message = models.TextField(
        blank=True,
        verbose_name="پیام ادمین برای صفحه پروژه",
        help_text="پیام اختیاری که روی صفحه پروژه نمایش داده می‌شود."
    )

    @property
    def current_phase(self):
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
        return self.current_phase == ProjectPhase.SELECTION_FINISHED
        # return self.current_phase in [ProjectPhase.SELECTION_ACTIVE, ProjectPhase.SELECTION_FINISHED]

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=["is_active"])

    def activate(self):
        self.is_active = True
        # Keep admin_message (it’s independent), clear reason
        self.deactivation_reason = ""
        self.save(update_fields=["is_active", "deactivation_reason"])

    @property
    def phase_display(self):
        phase = self.current_phase
        if self.auto_phase_transition and self.selection_start and self.selection_end:
            return f"{ProjectPhase(phase).label} (خودکار)"
        return ProjectPhase(phase).label

    def update_phase_if_needed(self):
        if self.auto_phase_transition:
            current = self.current_phase
            if current != self.selection_phase:
                self.selection_phase = current
                self.save(update_fields=['selection_phase'])

    @property
    def comments_count(self):
        try:
            from apps.comments.utils import get_comment_count
            return get_comment_count('project.project', self.id)
        except ImportError:
            return 0

    @property
    def pending_comments_count(self):
        try:
            from apps.comments.utils import get_comment_count
            return get_comment_count('project.project', self.id, 'PENDING')
        except ImportError:
            return 0

    def get_comments(self, status='APPROVED', limit=None):
        try:
            from apps.comments.services import ProjectCommentService
            comments = ProjectCommentService.get_project_comments(self.id)
            if limit:
                return comments[:limit]
            return comments
        except ImportError:
            return []

    def get_latest_comments(self, limit=5):
        return self.get_comments(limit=limit)

    def get_comment_statistics(self):
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
        return self.comments_count > 0

    @property
    def comment_engagement_rate(self):
        comments = self.comments_count
        if comments == 0:
            return 0
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
        return self.visible and self.is_active

    @property
    def status_display(self):
        if not self.visible:
            return "مخفی"
        elif not self.is_active:
            return "غیرفعال"
        else:
            return "فعال"

    @property
    def tags_list(self):
        return [tag.name for tag in self.tags.all()]

    def get_related_projects(self, limit=5):
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
        if not self.visible:
            return "مخفی"
        elif not self.is_active:
            return "غیرفعال"
        else:
            return "فعال"

    def activate(self):
        self.is_active = True
        self.save(update_fields=['is_active'])

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=['is_active'])

    # def __str__(self):
    #     return self.title

    def __str__(self) -> str:
        status_emoji = "✅" if self.is_active else "❌"
        return f"{status_emoji} {self.title}"

    def get_related_projects(self, limit=6):
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
    title = models.CharField(
        max_length=300, 
        validators=[validate_persian, MinLengthValidator(3)], 
        verbose_name="نام"
    )
    description = models.TextField(null=True, verbose_name="توضیحات")
    count = models.PositiveSmallIntegerField(
        null=True, 
        validators=[MinValueValidator(2), MaxValueValidator(6)], 
        verbose_name="تعداد اعضا"
    )
    project = models.ForeignKey(
        'Project', 
        on_delete=models.CASCADE, 
        related_name="teams", 
        verbose_name="پروژه"
    )

    create_date = models.DateField(null=True, verbose_name="تاریخ تشکیل تیم")
    team_code = models.CharField(
        max_length=10, 
        unique=True, 
        blank=True,
        verbose_name="کد تیم",
        help_text="کد تیم به صورت خودکار تولید می‌شود"
    )
    
    TEAM_STAGES = [
        (1, "مرحله اول - ناپایدار"),
        (2, "مرحله دوم - ناپایدار"), 
        (3, "مرحله سوم - ناپایدار"),
        (4, "مرحله پایدار"),
    ]
    
    team_building_stage = models.IntegerField(
        choices=TEAM_STAGES,
        default=4,
        verbose_name="مرحله تیم‌سازی"
    )
    
    dissolution_requested_by = models.ForeignKey(
        get_user_model(), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="dissolution_requests",
        verbose_name="درخواست کننده انحلال"
    )
    dissolution_requested_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="زمان درخواست انحلال"
    )
    is_dissolution_in_progress = models.BooleanField(
        default=False,
        verbose_name="در حال انحلال"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "تیم"
        verbose_name_plural = "تیم ها"

    def __str__(self) -> str:
        return f"{self.title} ({self.team_code})" if self.team_code else self.title
    
    def save(self, *args, **kwargs):
        if not self.team_code:
            self.team_code = self.generate_team_code()
        super().save(*args, **kwargs)

    def generate_team_code(self):
        # Get team leader's province phone code
        leader_province_code = "21"  # Default Tehran
        
        leader_request = self.requests.filter(
            user_role='C', status='A', request_type='JOIN'
        ).select_related('user').first()
        
        if leader_request and hasattr(leader_request.user, 'resume'):
            resume = leader_request.user.resume
            if hasattr(resume, 'team_formation_province') and resume.team_formation_province:
                # Assuming Province model has phone_code field
                province = resume.team_formation_province
                if hasattr(province, 'phone_code'):
                    leader_province_code = province.phone_code
        
        # Get stage number
        stage = self.team_building_stage
        
        # Get sequence number for this province+stage combination
        existing_teams_count = Team.objects.filter(
            team_code__startswith=f"{leader_province_code}{stage}"
        ).count()
        
        sequence = str(existing_teams_count + 1).zfill(3)
        
        return f"{leader_province_code}{stage}{sequence}"

    def get_leader_user(self):
        leader_request = self.requests.filter(user_role="C", status="A", request_type="JOIN").first()
        return leader_request.user if leader_request else None
    
    def get_leader(self):
        return self.requests.filter(user_role="C", status="A", request_type="JOIN").first()
    
    def get_deputy(self):
        return self.requests.filter(user_role="D", status="A", request_type="JOIN").first()
    
    def get_deputy_user(self):
        deputy_request = self.get_deputy()
        return deputy_request.user if deputy_request else None
    
    def get_leadership(self):
        return self.requests.filter(
            user_role__in=["C", "D"], 
            status="A", 
            request_type="JOIN"
        )
    
    def has_deputy(self):
        return self.get_deputy() is not None
    
    def can_user_manage_team(self, user):
        leadership = self.get_leadership().filter(user=user)
        return leadership.exists()
    
    def promote_to_deputy(self, user, promoted_by):
        from django.db import transaction
        
        # Check if user is a member
        membership = self.requests.filter(
            user=user, 
            status='A', 
            request_type='JOIN',
            user_role='M'
        ).first()
        
        if not membership:
            raise ValueError("کاربر عضو این تیم نیست")
        
        # Check if deputy already exists
        if self.has_deputy():
            raise ValueError("این تیم قائم مقام دارد")
        
        with transaction.atomic():
            # Update user role to deputy
            membership.user_role = 'D'
            membership.save()
            
            # Import here to avoid circular import
            from apps.project.models import TeamRequest
            
            # Create promotion request record
            TeamRequest.objects.create(
                team=self,
                user=user,
                request_type='PROMOTE_DEPUTY',
                user_role='D',
                status='A',
                requested_by=promoted_by,
                description=f'ارتقا به قائم مقام توسط {promoted_by.full_name}'
            )
    
    def demote_deputy(self, demoted_by):
        from django.db import transaction
        
        deputy = self.get_deputy()
        if not deputy:
            raise ValueError("این تیم قائم مقام ندارد")
        
        with transaction.atomic():
            # Update role to member
            deputy.user_role = 'M'
            deputy.save()
            
            # Import here to avoid circular import
            from apps.project.models import TeamRequest
            
            # Create demotion request record
            TeamRequest.objects.create(
                team=self,
                user=deputy.user,
                request_type='DEMOTE_DEPUTY',
                user_role='M',
                status='A',
                requested_by=demoted_by,
                description=f'تنزل از قائم مقام توسط {demoted_by.full_name}'
            )
    
    def get_members(self):
        return get_user_model().objects.filter(
            team_requests__team=self, 
            team_requests__status="A",
            team_requests__request_type="JOIN"
        )
    
    def get_member_count(self):
        return self.requests.filter(
            status="A", 
            request_type="JOIN"
        ).count()
    
    def can_dissolve(self):
        if not self.is_dissolution_in_progress:
            return False
        
        member_requests = self.requests.filter(
            status="A", 
            request_type="JOIN"
        ).exclude(user_role="C")
        
        # Import here to avoid circular import
        from apps.project.models import TeamRequest
        
        leave_requests = TeamRequest.objects.filter(
            team=self,
            request_type="LEAVE",
            status="A",
            user__in=[req.user for req in member_requests]
        )
        
        return leave_requests.count() == member_requests.count()

    def get_latest_chat_messages(self, limit=10):
        return self.chat_messages.select_related('user').order_by('-created_at')[:limit]

    def get_active_meeting_links(self):
        return self.online_meetings.filter(is_active=True).order_by('-created_at')

    def get_pending_unstable_tasks(self):
        return self.unstable_tasks.filter(is_completed=False).order_by('due_date')

    def get_team_member_details(self):
        from apps.account.models import Resume
        
        members = []
        active_memberships = self.requests.filter(status='A', request_type='JOIN').select_related('user')
        
        for membership in active_memberships:
            user = membership.user
            resume = getattr(user, 'resume', None)
            
            # Get latest education
            latest_education = None
            if resume:
                latest_education = resume.educations.order_by('-graduation_year').first()
            
            member_info = {
                'id': user.id,
                'full_name': user.full_name,
                'avatar': user.avatar.url if user.avatar else None,
                'role': membership.get_user_role_display(),
                'role_code': membership.user_role,
                'is_leader': membership.user_role == 'C',
                'is_deputy': membership.user_role == 'D',
                'latest_education': {
                    'degree_level': latest_education.degree_level if latest_education else None,
                    'field_of_study': latest_education.field_of_study if latest_education else None,
                    'university': latest_education.university if latest_education else None,
                } if latest_education else None,
                'joined_at': membership.created_at
            }
            members.append(member_info)
        
        return members

    def _have_been_teammates(self, user1, user2):
        from django.db.models import Q
        
        # Get all teams where user1 was a member
        user1_teams = TeamRequest.objects.filter(
            user=user1,
            status='A',
            request_type='JOIN'
        ).values_list('team_id', flat=True)
        
        # Check if user2 was also in any of those teams
        return TeamRequest.objects.filter(
            user=user2,
            status='A', 
            request_type='JOIN',
            team_id__in=user1_teams
        ).exists()

    def _get_available_new_users_for_inviter(self, inviting_user):
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        
        User = get_user_model()
        
        # Get all users this person has been teammates with
        previous_teammate_teams = TeamRequest.objects.filter(
            user=inviting_user,
            status='A',
            request_type='JOIN'
        ).values_list('team_id', flat=True)
        
        previous_teammate_ids = TeamRequest.objects.filter(
            team_id__in=previous_teammate_teams,
            status='A',
            request_type='JOIN'
        ).exclude(user=inviting_user).values_list('user_id', flat=True)
        
        # Get users who are not currently in a team and are not previous teammates
        available_users = User.objects.filter(
            ~Q(id__in=previous_teammate_ids),
            ~Q(id=inviting_user.id)
        ).exclude(
            team_requests__status='A',
            team_requests__request_type='JOIN'
        )
        
        return available_users.exists()

    def can_invite_user(self, inviting_user, target_user):
        # Check if repeat teammate prevention is enabled
        stage_settings = TeamBuildingSettings.objects.filter(
            stage=self.team_building_stage,
            prevent_repeat_teammates=True
        ).first()
        
        if not stage_settings:
            return True, ""
        
        # Check if there are available new participants
        available_new_users = self._get_available_new_users_for_inviter(inviting_user)
        
        if not available_new_users:
            # No new users available, allow inviting previous teammates
            return True, ""
        
        # Check if these users have been teammates before
        have_been_teammates = self._have_been_teammates(inviting_user, target_user)
        
        if have_been_teammates and available_new_users:
            return False, "این فرد برای شما کراری محسوب می‌شود در حالی که شرکت‌کننده‌های جدیدی برای تیم‌سازی وجود دارند"
        
        return True, ""

    def is_formation_allowed(self):
        return TeamBuildingSettings.is_stage_formation_enabled(self.team_building_stage)
    
    def is_team_page_accessible(self):
        return TeamBuildingSettings.is_stage_page_enabled(self.team_building_stage)
    
    def get_stage_settings(self):
        return TeamBuildingSettings.get_stage_settings(self.team_building_stage)
    
    def is_unstable_team(self):
        return self.team_building_stage in [1, 2, 3]
    
    def is_stable_team(self):
        return self.team_building_stage == 4
    
    def can_be_auto_completed(self):
        if not self.is_unstable_team():
            return False
        
        stage_settings = TeamBuildingSettings.objects.filter(
            stage=self.team_building_stage,
            control_type='formation',
            allow_auto_completion=True
        ).first()
        
        return bool(stage_settings)
    
    def get_formation_deadline(self):
        stage_settings = TeamBuildingSettings.objects.filter(
            stage=self.team_building_stage,
            control_type='formation'
        ).first()
        
        if stage_settings:
            from datetime import timedelta
            return self.created_at + timedelta(hours=stage_settings.formation_deadline_hours)
        
        return None


class ProvinceExtension:
    """
    Add this field to apps/settings/models.py Province model if not exists:
    
    phone_code = models.CharField(
        max_length=3,
        default="21", 
        verbose_name="کد تلفن استان",
        help_text="کد تلفن استان برای تولید کد تیم"
    )
    """
    pass


class TeamRequest(BaseModel):
    REQUEST_STATUS = [
        ("A", "قبول"), 
        ("R", "رد"), 
        ("W", "در انتظار")
    ]
    
    USER_ROLE = [
        ("C", "سرگروه"),  # Captain/Leader
        ("D", "قائم مقام"),  # Deputy  
        ("M", "عضو")       # Member
    ]
    
    REQUEST_TYPE = [
        ("JOIN", "درخواست عضویت"),
        ("LEAVE", "درخواست خروج"),
        ("INVITE", "دعوت به عضویت"),
        ("PROPOSE", "پیشنهاد تشکیل تیم"),
        ("DISSOLVE", "درخواست انحلال تیم"),
        ("PROMOTE_DEPUTY", "ارتقا به قائم مقام"),
        ("DEMOTE_DEPUTY", "تنزل از قائم مقام"),
        ("TRANSFER_LEADERSHIP", "انتقال رهبری")
    ]

    team = models.ForeignKey(
        "Team", 
        on_delete=models.CASCADE, 
        related_name="requests", 
        verbose_name="تیم"
    )
    user = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE, 
        related_name="team_requests", 
        verbose_name="کاربر"
    )
    status = models.CharField(
        max_length=1, 
        choices=REQUEST_STATUS, 
        default="W", 
        verbose_name="وضعیت درخواست"
    )
    user_role = models.CharField(
        max_length=1, 
        choices=USER_ROLE, 
        verbose_name="نقش در تیم"
    )
    request_type = models.CharField(
        max_length=25,
        choices=REQUEST_TYPE,
        default="JOIN",
        verbose_name="نوع درخواست"
    )
    requested_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_requests",
        verbose_name="درخواست کننده"
    )
    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "درخواست تیم"
        verbose_name_plural = "درخواست‌های تیم"
        
        # Ensure only one active membership per user per team
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'user', 'request_type'],
                condition=models.Q(status='A', request_type='JOIN'),
                name='unique_active_team_membership'
            ),
            # Ensure only one leader per team
            models.UniqueConstraint(
                fields=['team'],
                condition=models.Q(status='A', user_role='C', request_type='JOIN'),
                name='unique_team_leader'
            ),
            # Ensure only one deputy per team
            models.UniqueConstraint(
                fields=['team'],
                condition=models.Q(status='A', user_role='D', request_type='JOIN'),
                name='unique_team_deputy'
            )
        ]

    def __str__(self):
        return f"{self.user.full_name} - {self.get_request_type_display()} ({self.get_status_display()})"
    
    def is_leadership_role(self):
        return self.user_role in ['C', 'D']
    
    def can_approve_requests(self):
        return self.user_role in ['C', 'D'] and self.status == 'A'


class TeamBuildingAnnouncement(BaseModel):
    title = models.CharField(max_length=200, verbose_name="عنوان")
    content = models.TextField(verbose_name="متن اطلاعیه")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    
    class Meta(BaseModel.Meta):
        verbose_name = "اطلاعیه تیم‌سازی"
        verbose_name_plural = "اطلاعیه‌های تیم‌سازی"
        ordering = ['order', '-created_at']
    
    def __str__(self):
        return self.title


class TeamBuildingVideoButton(BaseModel):
    announcement = models.ForeignKey(
        TeamBuildingAnnouncement,
        on_delete=models.CASCADE,
        related_name='video_buttons',
        verbose_name="اطلاعیه"
    )
    title = models.CharField(max_length=100, verbose_name="عنوان دکمه")
    video_url = models.URLField(verbose_name="لینک ویدیو")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    
    class Meta(BaseModel.Meta):
        verbose_name = "دکمه ویدیوی آموزشی"
        verbose_name_plural = "دکمه‌های ویدیوی آموزشی"
        ordering = ['order']
    
    def __str__(self):
        return f"{self.announcement.title} - {self.title}"


class TeamChatMessage(BaseModel):
    team = models.ForeignKey(
        'Team', 
        on_delete=models.CASCADE, 
        related_name='chat_messages',
        verbose_name="تیم"
    )
    user = models.ForeignKey(
        get_user_model(), 
        on_delete=models.CASCADE,
        related_name='team_messages',
        verbose_name="کاربر"
    )
    message = models.TextField(verbose_name="پیام")
    is_edited = models.BooleanField(default=False, verbose_name="ویرایش شده")
    edited_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ویرایش")
    
    class Meta(BaseModel.Meta):
        verbose_name = "پیام چت تیم"
        verbose_name_plural = "پیام‌های چت تیم"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} در {self.team.title}: {self.message[:50]}..."


class TeamOnlineMeeting(BaseModel):
    team = models.ForeignKey(
        'Team', 
        on_delete=models.CASCADE, 
        related_name='online_meetings',
        verbose_name="تیم"
    )
    title = models.CharField(max_length=200, verbose_name="عنوان جلسه")
    meeting_url = models.URLField(verbose_name="لینک جلسه آنلاین")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    scheduled_for = models.DateTimeField(null=True, blank=True, verbose_name="زمان برنامه‌ریزی شده")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="ایجاد شده توسط"
    )
    
    class Meta(BaseModel.Meta):
        verbose_name = "جلسه آنلاین تیم"
        verbose_name_plural = "جلسات آنلاین تیم"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.team.title}: {self.title}"


class TeamUnstableTask(BaseModel):
    team = models.ForeignKey(
        'Team', 
        on_delete=models.CASCADE, 
        related_name='unstable_tasks',
        verbose_name="تیم"
    )
    title = models.CharField(max_length=200, verbose_name="عنوان کار")
    description = models.TextField(verbose_name="توضیحات")
    file = models.FileField(
        upload_to='team_unstable_files/', 
        blank=True, 
        null=True,
        verbose_name="فایل"
    )
    assigned_to = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="واگذار شده به"
    )
    due_date = models.DateField(null=True, blank=True, verbose_name="مهلت انجام")
    is_completed = models.BooleanField(default=False, verbose_name="تکمیل شده")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تکمیل")
    
    class Meta(BaseModel.Meta):
        verbose_name = "کار بخش ناپایدار"
        verbose_name_plural = "کارهای بخش ناپایدار"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.team.title}: {self.title}"


class TeamBuildingSettings(BaseModel):
    STAGE_CHOICES = [
        (1, "مرحله ناپایدار اول"),
        (2, "مرحله ناپایدار دوم"), 
        (3, "مرحله ناپایدار سوم"),
        (4, "مرحله پایدار")
    ]
    
    CONTROL_TYPE_CHOICES = [
        ('formation', 'صفحه تشکیل تیم'),
        ('team_page', 'صفحه تیم'),
    ]
    
    stage = models.IntegerField(
        choices=STAGE_CHOICES,
        verbose_name="مرحله تیم‌سازی"
    )
    control_type = models.CharField(
        max_length=20,
        choices=CONTROL_TYPE_CHOICES,
        verbose_name="نوع کنترل"
    )
    is_enabled = models.BooleanField(
        default=False,
        verbose_name="فعال"
    )
    custom_description = models.TextField(
        blank=True,
        verbose_name="توضیحات سفارشی"
    )
    
    # Team formation rules
    min_team_size = models.IntegerField(
        default=2,
        verbose_name="حداقل اعضای تیم"
    )
    max_team_size = models.IntegerField(
        default=6,
        verbose_name="حداکثر اعضای تیم"
    )
    
    # Prevent repeat teammates rule (کراری منع)
    prevent_repeat_teammates = models.BooleanField(
        default=True,
        verbose_name="قانون منع همتیمی کراری"
    )
    
    # Auto completion settings for unstable teams
    allow_auto_completion = models.BooleanField(
        default=True,
        verbose_name="تکمیل خودکار تیم‌های ناپایدار"
    )
    
    # Time limits
    formation_deadline_hours = models.IntegerField(
        default=24,
        verbose_name="مهلت تشکیل تیم (ساعت)"
    )
    
    class Meta(BaseModel.Meta):
        verbose_name = "تنظیمات تیم‌سازی"
        verbose_name_plural = "تنظیمات تیم‌سازی"
        unique_together = ['stage', 'control_type']
    
    def __str__(self):
        return f"{self.get_stage_display()} - {self.get_control_type_display()}"
    
    @classmethod
    def is_stage_formation_enabled(cls, stage):
        return cls.objects.filter(
            stage=stage, 
            control_type='formation', 
            is_enabled=True
        ).exists()
    
    @classmethod
    def is_stage_page_enabled(cls, stage):
        return cls.objects.filter(
            stage=stage, 
            control_type='team_page', 
            is_enabled=True
        ).exists()
    
    @classmethod
    def get_stage_settings(cls, stage):
        return cls.objects.filter(stage=stage)


class TeamBuildingStageDescription(BaseModel):
    PAGE_CHOICES = [
        ('unstable_1_formation', 'صفحه تشکیل تیم ناپایدار مرحله 1'),
        ('unstable_2_formation', 'صفحه تشکیل تیم ناپایدار مرحله 2'),
        ('unstable_3_formation', 'صفحه تشکیل تیم ناپایدار مرحله 3'),
        ('stable_formation', 'صفحه تشکیل تیم پایدار'),
        ('team_page', 'صفحه تیم')
    ]
    
    page_type = models.CharField(
        max_length=30,
        choices=PAGE_CHOICES,
        unique=True,
        verbose_name="نوع صفحه"
    )
    title = models.CharField(
        max_length=200,
        verbose_name="عنوان"
    )
    description = models.TextField(
        verbose_name="توضیحات"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال"
    )
    
    class Meta(BaseModel.Meta):
        verbose_name = "توضیحات مراحل تیم‌سازی" 
        verbose_name_plural = "توضیحات مراحل تیم‌سازی"
    
    def __str__(self):
        return f"{self.get_page_type_display()}"
