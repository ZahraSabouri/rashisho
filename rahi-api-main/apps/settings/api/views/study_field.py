from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action

from apps.api.permissions import SettingsPermission
from apps.settings.api.serializers.study_field import StudyFieldSerializer
from apps.settings.filters.study_field_filters import StudyFieldFilter
from apps.settings.models import StudyField
from apps.project.models import Project
from apps.api.schema import TaggedAutoSchema



class StudyFieldViewSet(ModelViewSet):
    schema = TaggedAutoSchema(tags=["Settings Study Field"])
    serializer_class = StudyFieldSerializer
    queryset = StudyField.objects.all()
    permission_classes = [SettingsPermission]
    filterset_class = StudyFieldFilter

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'get_active_list':
            final_qs = StudyField.objects.none()
            for item in Project.objects.all():
                for sf in item.study_fields.all():
                    if sf in qs:
                        final_qs |=  item.study_fields.filter(id=sf.id)
            return final_qs.distinct('id')
        return qs
    
    @action(['GET'], detail=False)
    def get_active_list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
