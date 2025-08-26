import datetime

import jdatetime
import pytz
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet


def paginated_response(self, queryset, context=None):
    if not context:
        context = {"request": self.request}

    page = self.paginate_queryset(queryset)
    if page is not None:
        serializer = self.serializer_class(page, many=True, context=context)
        return self.get_paginated_response(serializer.data)

    serializer = self.serializer_class(queryset, many=True, context=context)
    return Response(serializer.data)


def mobile_validator(value):
    if len(value) != 11:
        raise ValidationError("شماره موبایل باید 11 رقم باشد!")

    if not str(value).startswith("09"):
        raise ValidationError("شماره موبایل باید با 09 شروع شود!")

    if not str(value).isdigit():
        raise ValidationError("نمیتوان در شماره موبایل از حروف استفاده کرد!")


class CustomModelViewSet(ModelViewSet):
    @action(methods=["post"], detail=False, url_path="create")
    def create_multi_object(self, request, *args, **kwargs):
        """We create this action to create multiple objects in one request"""

        data = request.data
        errors = []
        created_objects = []

        for item in data:
            serializer = self.get_serializer(data=item)
            try:
                serializer.is_valid(raise_exception=True)
                created_objects.append(serializer.save())

            except ValidationError as e:
                errors.append({"index": item["index"], "errors": e.detail})

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(created_objects, many=True).data, status=status.HTTP_201_CREATED)

    @action(methods=["post"], detail=False, url_path="update")
    def update_multi_object(self, request, *args, **kwargs):
        """We create this action for update multiple object in one request"""

        data = request.data
        model_class = self.get_queryset().model
        errors = []

        for item in data:
            try:
                instance = model_class.objects.get(id=item["id"])
                serializer = self.serializer_class(instance, data=item, partial=True)
                serializer.is_valid(raise_exception=True)
                serializer.save()

            except model_class.DoesNotExist:
                errors.append({"id": item["id"], "error": "رکورد مورد نظر برای ویرایش یافت نشد."})

            except ValidationError as e:
                errors.append({"id": item["id"], "errors": e.detail})

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "success"}, status=status.HTTP_200_OK)


def convert_to_jalali(date: datetime):
    tehran_tz = pytz.timezone("Asia/Tehran")
    local_date = date.astimezone(tehran_tz)
    date_time = jdatetime.datetime.fromgregorian(datetime=local_date).strftime("%Y/%m/%d %H:%M:%S").split()
    return date_time[0], date_time[1]
