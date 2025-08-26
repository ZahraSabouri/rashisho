from django.contrib import admin
from django.db.models import Q

from apps.exam import models

admin.site.register(models.NeoQuestion)
admin.site.register(models.NeoOption)
admin.site.register(models.BelbinQuestion)
admin.site.register(models.BelbinAnswer)
admin.site.register(models.GeneralExam)
admin.site.register(models.GeneralQuestion)
admin.site.register(models.GeneralQuestionOption)
admin.site.register(models.ExamResult)


class UserAnswerAdmin(admin.ModelAdmin):
    search_fields = ["user__user_info__first_name", "user__user_info__last_name"]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        if " " in search_term:
            first_name, last_name = search_term.split(" ", 1)
            queryset |= self.model.objects.filter(
                Q(user__user_info__first_name=first_name) & Q(user__user_info__last_name=last_name)
            )

        return queryset, use_distinct


admin.site.register(models.UserAnswer, UserAnswerAdmin)
