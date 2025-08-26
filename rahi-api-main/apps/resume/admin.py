from django.contrib import admin

from apps.resume import models

admin.site.register(models.Resume)
admin.site.register(models.Education)
admin.site.register(models.WorkExperience)
admin.site.register(models.Skill)
admin.site.register(models.Language)
admin.site.register(models.Certificate)
admin.site.register(models.Connection)
admin.site.register(models.Project)
