from rest_framework import serializers

from apps.resume import models
from apps.resume.api.serializers import certificate, connection, education, language, project, skill, work_experience


class ResumeSerializer(serializers.ModelSerializer):
    educations = education.EducationSerializer(many=True, read_only=True)
    jobs = work_experience.WorkExperienceSerializer(many=True, read_only=True)
    skills = skill.SkillSerializer(many=True, read_only=True)
    languages = language.LanguageSerializer(many=True, read_only=True)
    resume_projects = project.ProjectSerializer(many=True, read_only=True)
    certificates = certificate.CertificateSerializer(many=True, read_only=True)
    connections = connection.ConnectionSerializer(many=True, read_only=True)

    class Meta:
        model = models.Resume
        fields = [
            "id",
            "status",
            "educations",
            "jobs",
            "skills",
            "languages",
            "resume_projects",
            "certificates",
            "connections",
            "steps",
            "resume_completed",
        ]
        read_only_fields = ["user", "steps", "resume_completed"]

    def to_representation(self, instance: models.Resume):
        result = super().to_representation(instance)
        user = instance.user
        result["user_info"] = {
            "first_name": user.user_info["first_name"],
            "last_name": user.user_info["last_name"],
            "mobile_number": user.user_info["mobile_number"] if self.context["request"].user == instance.user else None,
            "email": user.user_info["email"] if self.context["request"].user == instance.user else None,
            "city": user.city.title if user.city else None,
            "province": user.city.province.title if user.city else None,
            "address": user.address,
            "birth_date": user.birth_date,
            "gender": user.gender,
            "military_status": user.military_status,
            "marriage_status": user.marriage_status,
            "avatar": user.avatar.url if user.avatar else None,
            "personal_video": user.personal_video.url if user.personal_video else None,
            "telegram_address": user.telegram_address if self.context["request"].user == instance.user else None,
        }
        result["connections"] = (
            connection.ConnectionSerializer(instance.connections.all(), many=True).data
            if self.context["request"].user == instance.user
            else None
        )
        return result
