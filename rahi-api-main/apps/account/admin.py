from django.contrib import admin
from django.db.models import Q

from apps.account import models

class UserAdmin(admin.ModelAdmin):
    search_fields = [
        "user_info__first_name",
        "user_info__last_name",
        "user_info__national_id",
        "user_info__id",
        "id",
        "user_info__mobile_number",
    ]

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        if " " in search_term:
            first_name, last_name = search_term.split(" ", 1)
            queryset |= self.model.objects.filter(
                Q(user_info__first_name=first_name) & Q(user_info__last_name=last_name)
            )

        return queryset, use_distinct

@admin.register(models.PeerFeedback)
class PeerFeedbackAdmin(admin.ModelAdmin):
    list_display = ("to_user", "author", "is_public", "created_at")
    list_filter = ("is_public", "phase",)
    search_fields = ("text", "to_user__username", "author__username")

admin.site.register(models.User, UserAdmin)
