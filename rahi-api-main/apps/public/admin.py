from django.contrib import admin

from . import models

admin.site.register(models.Announcement) 
admin.site.register(models.AnnouncementReceipt)    
admin.site.register(models.UserNotification)
# admin.site.register(models.Notification)
admin.site.register(models.ContactInformation)
admin.site.register(models.ContactUs)
admin.site.register(models.CommonQuestions)
admin.site.register(models.CompetitionRule)
admin.site.register(models.Footer)
admin.site.register(models.AboutUs)
admin.site.register(models.Comment)
admin.site.register(models.Ticket)
admin.site.register(models.Department)
