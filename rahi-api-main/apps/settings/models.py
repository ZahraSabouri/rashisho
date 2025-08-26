from django.db import models

from apps.common.models import BaseModel


class Province(models.Model):
    title = models.CharField(max_length=30, verbose_name="عنوان")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "استان"
        verbose_name_plural = "استان ها"


class City(models.Model):
    title = models.CharField(max_length=50, verbose_name="عنوان")
    province = models.ForeignKey(Province, related_name="cities", on_delete=models.CASCADE, verbose_name="استان")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "شهرستان"
        verbose_name_plural = "شهرستان ها"


class University(models.Model):
    title = models.CharField(max_length=100, verbose_name="عنوان")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "دانشگاه"
        verbose_name_plural = "دانشگاه ها"


class StudyField(models.Model):
    title = models.CharField(max_length=255, verbose_name="عنوان")

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "رشته تحصیلی"
        verbose_name_plural = "رشته های تحصیلی"


class ForeignLanguage(BaseModel):
    class Meta(BaseModel.Meta):
        verbose_name = "زبان خارجه"
        verbose_name_plural = "زبان های خارجه"

    title = models.CharField(max_length=20, verbose_name="عنوان")

    def __str__(self):
        return self.title


class Skill(BaseModel):
    title = models.CharField(max_length=255, verbose_name="عنوان")

    def __str__(self):
        return self.title

    class Meta(BaseModel.Meta):
        verbose_name = "مهارت"
        verbose_name_plural = "مهارت ها"


class ConnectionWay(BaseModel):
    title = models.CharField(max_length=20, verbose_name="عنوان")

    def __str__(self):
        return self.title

    class Meta(BaseModel.Meta):
        verbose_name = "راه ارتباطی"
        verbose_name_plural = "راههای ارتباطی"


class FeatureActivation(BaseModel):
    FEATURE = [
        ("RE", "رزومه"),
        ("PP", "اولویت بندی پروژه"),
        ("TE", "تیم سازی"),
        ("TA", "کار ویژه"),
        ("BE", "آزمون بلبین"),
        ("NE", "آزمون نئو"),
        ("SC", "سناریو ها"),
        ("PR", "ارائه ها"),
        ("EE", "آزمون ورودی"),
        ("PE", "آزمون عمومی"),
        ("PL", "پروپزال"),
    ]

    feature = models.CharField(max_length=2, choices=FEATURE, unique=True, verbose_name="فیجر")
    active = models.BooleanField("فعال")

    def __str__(self):
        return self.get_feature_display()

    class Meta(BaseModel.Meta):
        verbose_name = "فعال سازی فیچر"
        verbose_name_plural = "فعال سازی فیچر ها"
