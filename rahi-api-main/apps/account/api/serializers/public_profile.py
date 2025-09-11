from rest_framework import serializers

from apps.account.models import User
from apps.resume.models import Resume
from apps.resume.api.serializers.education import EducationSerializer
from apps.resume.api.serializers.work_experience import WorkExperienceSerializer
from apps.resume.api.serializers.certificate import CertificateSerializer
from apps.resume.api.serializers.skill import SkillSerializer

class PublicProfileSerializer(serializers.ModelSerializer):
    # already-existing public fields remain unchanged...
    # ---
    educations = serializers.SerializerMethodField(read_only=True)
    jobs = serializers.SerializerMethodField(read_only=True)
    certificates = serializers.SerializerMethodField(read_only=True)
    skills = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "full_name", "bio", "avatar", "personal_video",
            "birth_date", "city", "province", "contact", "connection",
            "educations", "jobs", "certificates", "skills",
        ]
        read_only_fields = fields  # defensive: whole thing is read-only

    # --- helpers -------------------------------------------------------------
    def _resume_for(self, user: User):
        # one resume per user in current system; return None if missing
        try:
            return Resume.objects.get(user=user)
        except Resume.DoesNotExist:
            return None

    # --- slices --------------------------------------------------------------
    def get_educations(self, obj: User):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.educations.all().order_by("-start_date", "-id")
        return EducationSerializer(qs, many=True, context=self.context).data

    def get_jobs(self, obj: User):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.jobs.all().order_by("-start_date", "-id")
        return WorkExperienceSerializer(qs, many=True, context=self.context).data

    def get_certificates(self, obj: User):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.certificates.all().order_by("-issue_date", "-id")
        return CertificateSerializer(qs, many=True, context=self.context).data

    def get_skills(self, obj: User):
        resume = self._resume_for(obj)
        if not resume:
            return []
        qs = resume.skills.all().order_by("-created_at")  # stable ordering
        return SkillSerializer(qs, many=True, context=self.context).data
