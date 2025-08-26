from django.contrib import admin

from apps.settings import models

admin.site.register(models.Province)
admin.site.register(models.City)
admin.site.register(models.University)
admin.site.register(models.StudyField)
admin.site.register(models.ForeignLanguage)
admin.site.register(models.Skill)
admin.site.register(models.ConnectionWay)
admin.site.register(models.FeatureActivation)
