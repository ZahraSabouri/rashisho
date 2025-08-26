from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.resume.models import Resume


def find_duplicate_indices(lst) -> list:
    """Takes a list and return the index of duplicate items"""

    index_map = {}
    duplicate_indices = []

    for idx, value in enumerate(lst):
        if value in index_map:
            duplicate_indices.append(idx)
        else:
            index_map[value] = idx

    return duplicate_indices


class ResumeModelViewSet(ModelViewSet):
    @action(methods=["post"], detail=False, url_path="create")
    def create_multi_object(self, request, *args, **kwargs):
        data = request.data
        errors = []
        validated_options = []

        for item in data:
            serializer = self.get_serializer(data=item)
            try:
                serializer.is_valid(raise_exception=True)
                validated_options.append(serializer)

            except ValidationError as e:
                errors.append({"index": item["index"], "errors": e.detail})

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        else:
            for item in validated_options:
                item.save()
        return Response({"status": "عملیات با موفقیت انجام شد!"}, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="update")
    def update_multi_object(self, request, *args, **kwargs):
        data = request.data
        resume = Resume.objects.get(id=kwargs["resume_pk"])
        errors = []
        validated_options = []
        model_class = self.get_queryset().model

        if not isinstance(data, list):
            raise ValidationError("داده ارسالی باید به فرمت لیست باشد!")

        for item in data:
            try:
                serializer = self.serializer_class(data=item, context={"resume": resume})
                serializer.is_valid(raise_exception=True)
                validated_options.append(serializer)

            except ValidationError as e:
                errors.append({"index": item["index"], "errors": e.detail})

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        else:
            model_class.objects.filter(resume_id=kwargs["resume_pk"]).delete()
            for item in validated_options:
                item.save()

        return Response({"status": "عملیات با موفقیت انجام شد!"}, status=status.HTTP_200_OK)


def create_last_step(model_name, serializer, data, resume):
    errors = []
    validated_options = []
    language_titles = []

    if not isinstance(data, list):
        raise ValidationError("داده ارسالی باید به فرمت لیست باشد!")

    # preventing duplicate title for languages
    if model_name == "languages":
        for item in data:
            language_titles.append(item["language_name"])
        ind = find_duplicate_indices(language_titles)

        if ind:
            # for value in ind:
            errors.append(
                {"model": {model_name}, "index": ind[0], "errors": {"language_name": ["عنوان زبان تکرای است!"]}}
            )
            return errors, validated_options

    # Inserting data
    for item in data:
        try:
            serializer_data = serializer(data=item, context={"resume": resume})
            serializer_data.is_valid(raise_exception=True)
            validated_options.append(serializer_data)

        except ValidationError as e:
            errors.append({"model": {model_name}, "index": item["index"], "errors": e.detail})

    return errors, validated_options


def update_last_step(model_name, serializer, data, resume):
    errors = []
    validated_options = []

    if not isinstance(data, list):
        raise ValidationError("داده ارسالی باید به فرمت لیست باشد!")

    for item in data:
        try:
            serializer_data = serializer(data=item, context={"resume": resume})
            serializer_data.is_valid(raise_exception=True)
            validated_options.append(serializer_data)

        except ValidationError as e:
            errors.append({"model": {model_name}, "index": item["index"], "errors": e.detail})

    return errors, validated_options
