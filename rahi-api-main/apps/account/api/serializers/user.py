from rest_framework import serializers

from apps.account import models
from apps.common.serializers import CustomSlugRelatedField
from apps.resume.models import Resume
from apps.settings.models import City
from apps.project.models import TeamRequest

from django.db.models import Q
from apps.account.models import Connection

from django.db.models import Prefetch

from apps.resume.api.serializers.education import EducationSerializer
from apps.resume.api.serializers.work_experience import WorkExperienceSerializer
from apps.resume.api.serializers.certificate import CertificateSerializer
from apps.resume.api.serializers.skill import SkillSerializer
from apps.account.models import PeerFeedback


class PublicProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()
    personal_video = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    province = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    connection = serializers.SerializerMethodField()

    educations = serializers.SerializerMethodField()
    jobs = serializers.SerializerMethodField()
    certificates = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()

    class Meta:
        model = models.User
        fields = [
            "id", "full_name", "bio",
            "avatar", "personal_video",
            "birth_date", "city", "province",
            "contact", "connection",
            "educations", "jobs", "certificates", "skills",
        ]
        read_only_fields = fields

    def get_avatar(self, obj): return obj.avatar.url if obj.avatar else None
    def get_personal_video(self, obj): return obj.personal_video.url if obj.personal_video else None
    def get_city(self, obj): return obj.city.title if obj.city else None
    def get_province(self, obj):
        if not obj.city:
            return None
        city = City.objects.filter(id=obj.city_id).select_related("province").first()
        return {"id": str(city.province.id), "title": city.province.title} if city else None

    # ---- resume helpers ----
    def _resume_for(self, user):
        # Users may not have started resume yet.
        return Resume.objects.filter(user=user).first()

    def get_educations(self, obj):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.educations.all().order_by("-end_date", "-created_at")
        return EducationSerializer(qs, many=True, context=self.context).data

    def get_jobs(self, obj):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.jobs.all().order_by("-end_date", "-created_at")
        return WorkExperienceSerializer(qs, many=True, context=self.context).data

    def get_certificates(self, obj):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.certificates.all().order_by("-created_at")
        return CertificateSerializer(qs, many=True, context=self.context).data

    def get_skills(self, obj):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.skills.all().order_by("-created_at")
        return SkillSerializer(qs, many=True, context=self.context).data

    def _viewer(self):
        req = self.context.get("request")
        return getattr(req, "user", None)

    def _conn_between(self, viewer, target):
        # Symmetric lookup: pending/accepted/rejected between two users
        return (
            Connection.objects
            .filter(Q(from_user=viewer, to_user=target) | Q(from_user=target, to_user=viewer))
            .order_by("-created_at")
            .first()
        )

    def get_contact(self, obj):
        viewer = self._viewer()
        if not viewer or not viewer.is_authenticated:
            return None
        # Always see your own contact
        if viewer.id == obj.id:
            return {"mobile_number": obj.mobile_number, "telegram_address": obj.telegram_address}

        conn = self._conn_between(viewer, obj)
        if conn and conn.status == "accepted":
            # Requirement: once accepted, both sides see each other's phones. :contentReference[oaicite:6]{index=6}
            return {"mobile_number": obj.mobile_number, "telegram_address": obj.telegram_address}
        return None

    def get_connection(self, obj):
        """
        Returns current relationship between viewer and target, to drive UI:
        - status: self|none|pending|accepted|rejected
        - direction: sent|received (only when pending)
        - can_send_request: bool
        - id: pending connection id (if any)
        """
        viewer = self._viewer()
        if not viewer or not viewer.is_authenticated:
            return {"status": "none", "can_send_request": False}

        if viewer.id == obj.id:
            return {"status": "self", "can_send_request": False}

        conn = self._conn_between(viewer, obj)
        if not conn:
            return {"status": "none", "can_send_request": True}

        payload = {"status": conn.status, "can_send_request": False}
        if conn.status == "pending":
            payload.update({
                "direction": "sent" if conn.from_user_id == viewer.id else "received",
                "id": str(conn.id),
            })
        return payload


class MeSerializer(serializers.ModelSerializer):
    city = CustomSlugRelatedField(slug_field="title", queryset=City.objects.all())
    email = serializers.EmailField(required=False, allow_null=True)
    my_permissions = serializers.SerializerMethodField()

    class Meta:
        model = models.User
        fields = [
            "id",
            "user_info",
            "user_id",
            "avatar",
            "personal_video",
            "city",
            "address",
            "gender",
            "birth_date",
            "military_status",
            "marriage_status",
            "created_at",
            "updated_at",
            "resume",
            "role",
            "email",
            "telegram_address",
            "is_accespted_terms",
            "my_permissions",
        ]
        read_only_fields = ["id", "user_info", "user_id", "resume", "role"]

    def validate(self, attrs):
        MALE = "MA"
        FEMALE = "FE"
        if attrs["gender"] == MALE and attrs.get("military_status") is None:
            raise serializers.ValidationError("لطفا وضعیت نظام وظیه خود را وارد کنید.")
        if attrs["gender"] == FEMALE:
            attrs["military_status"] = None
        return super().validate(attrs)

    def update(self, instance, validated_data):
        email = validated_data.get("email", None)
        if email:
            instance.user_info["email"] = email
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["avatar"] = instance.avatar.url if instance.avatar else None
        representation["personal_video"] = instance.personal_video.url if instance.personal_video else None
        user_resume = Resume.objects.filter(user=instance).first()
        representation["resume_completed"] = instance.resume.resume_completed if user_resume else False
        if instance.city:
            city = City.objects.filter(id=instance.city.id).first()
            representation["province"] = [{"value": city.province.id, "text": city.province.title}]
        qs = (
            TeamRequest.objects
            .filter(user=instance, status="A")
            .select_related("team__project")
        )
        representation["teams"] = [
            {
                "team": {"id": str(tr.team.id), "title": tr.team.title},
                "project": (
                    {"id": str(tr.team.project.id), "title": tr.team.project.title}
                    if tr.team and tr.team.project else None
                ),
                "role": tr.user_role,  # keep existing code values ('C','M') to avoid breaking clients
            }
            for tr in qs
        ]

        return representation

    def get_my_permissions(self, instance):
        return {
            "groups": [g.name for g in instance.groups.all().order_by("name")],
            "perms": sorted(list(instance.get_all_permissions())),
            "is_admin": bool(instance.is_superuser or instance.is_staff or instance.role == 0),
        }


class UserBriefInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ["user_id", "full_name"]
        read_only_fields = ["user_id", "full_name"]


class PeerFeedbackPublicSerializer(serializers.ModelSerializer):
    author_full_name = serializers.SerializerMethodField()
    author_avatar = serializers.SerializerMethodField()

    class Meta:
        model = PeerFeedback
        fields = ["author_full_name", "author_avatar", "text", "phase", "created_at"]

    def get_author_full_name(self, obj):
        u = obj.author
        return getattr(u, "full_name", None) if u else None

    def get_author_avatar(self, obj):
        u = obj.author
        request = self.context.get("request")
        if u and getattr(u, "avatar", None):
            try:
                return request.build_absolute_uri(u.avatar.url)
            except Exception:
                return None
        return None