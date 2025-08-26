from rest_framework import serializers

from apps.account import models
from apps.common.serializers import CustomSlugRelatedField
from apps.resume.models import Resume
from apps.settings.models import City


class MeSerializer(serializers.ModelSerializer):
    city = CustomSlugRelatedField(slug_field="title", queryset=City.objects.all())
    email = serializers.EmailField(required=False, allow_null=True)

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
        return representation


class UserBriefInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = ["user_id", "full_name"]
        read_only_fields = ["user_id", "full_name"]
