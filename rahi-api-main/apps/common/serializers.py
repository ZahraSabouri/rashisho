from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_str
from rest_framework.serializers import SlugRelatedField


class CustomSlugRelatedField(SlugRelatedField):
    def __init__(self, use_on_select=True, is_many=False, slug_field=None, **kwargs):
        self.use_on_select = use_on_select
        self.is_many = is_many

        super().__init__(slug_field, **kwargs)

    def to_internal_value(self, data):
        queryset = self.get_queryset()
        try:
            return queryset.get(id=data)
        except ObjectDoesNotExist:
            self.fail("does_not_exist", slug_name=self.slug_field, value=smart_str(data))
        except (TypeError, ValueError):
            self.fail("invalid")

    def to_representation(self, obj):
        if not self.use_on_select:
            return super().to_representation(obj)

        data = {"value": getattr(obj, "id"), "text": super().to_representation(obj)}

        if self.is_many:
            return data

        return [data]
