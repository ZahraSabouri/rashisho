from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.account.models import User
from apps.api.permissions import CommunityPermission, IsSysgod, IsUser
from apps.community import models
from apps.community.api.serializers import community
from apps.community.services import generate_random_code
from apps.utils.utility import paginated_response

from apps.api.schema import TaggedAutoSchema

class CommunityViewSet(viewsets.ModelViewSet):
    schema = TaggedAutoSchema(tags=["Community"])
    serializer_class = community.CommunitySerializer
    queryset = models.Community.objects.all()
    permission_classes = [CommunityPermission]

    def get_object(self):
        if self.action == "my_community":
            return self.request.user.created_communities
        return super().get_object()

    @action(["GET"], detail=False)
    def my_community(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        if models.Community.objects.filter(manager=user).exists():
            raise ValidationError("شما قبلا یک انجمن ایجاد کرده اید!")

        code = generate_random_code()
        while models.Community.objects.filter(code=code).exists():
            code = generate_random_code()

        serializer.save(code=code, manager=user)
        super().perform_create(serializer)

    @action(methods=["get"], detail=False, url_path="add-to-community")
    def add_user_to_community(self, request, *args, **kwargs):
        user = self.request.user
        community_code = request.query_params.get("code", None)
        community = models.Community.objects.filter(code=community_code).first()
        if not community:
            return Response({"message": "انجمن با این کد وجود ندارد! "}, status=status.HTTP_200_OK)

        _user: User = User.objects.get(id=user.id)
        if _user.community:
            return Response(
                {"message": f"شما قبلا عضو انجمن {_user.community.title} بوده اید"}, status=status.HTTP_200_OK
            )

        _user.community = community
        _user.save()
        return Response({"message": "شما عضو انجمن مورد نظر شده اید."}, status=status.HTTP_200_OK)

    @action(methods=["get"], detail=False)
    def has_community(self, request, *args, **kwargs):
        user = self.request.user
        user_community = models.Community.objects.filter(manager=user).first()
        return Response({"user_has_community": True if user_community else False}, status=status.HTTP_200_OK)

    @action(methods=["post"], detail=True, url_path="add-file", serializer_class=community.CommunityResourceSerializer)
    def add_community_file(self, request, pk, *args, **kwargs):
        user = self.request.user
        data = request.data
        community = models.Community.objects.filter(id=pk).first()
        if community.manager != user:
            return Response(data={"فقط مدیر انجمن اجازه ارسال فایل دارد!"}, status=status.HTTP_403_FORBIDDEN)

        if not community:
            return Response(data={"انجمن مورد نظر یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)

        file_data = {"title": data["title"], "file": data["file"], "community": community.id}
        serializer = self.serializer_class(data=file_data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"عملیات با موفقیت انجام شد!"}, status=status.HTTP_200_OK)

    @action(
        methods=["get"],
        detail=False,
        url_path="get-community-files",
        permission_classes=[IsSysgod | IsUser],
        serializer_class=community.CommunityResourceSerializer,
    )
    def get_community_files(self, request, *args, **kwargs):
        community_id = self.request.query_params.get("community_id")
        community = models.Community.objects.filter(id=community_id).first()

        if request.user.role == 1 and not community:
            return Response(data={"انجمن یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.role == 1 and not community.manager == request.user:
            return Response(data={"شما اجازه انجام این دستور را ندارید!"}, status=status.HTTP_400_BAD_REQUEST)

        files = models.CommunityResource.objects.all()
        if community:
            files = files.filter(community=community)

        return paginated_response(self, files)

    @action(
        methods=["get"],
        detail=False,
        url_path="delete-community-files",
        permission_classes=[IsUser],
        serializer_class=community.CommunityResourceSerializer,
    )
    def delete_community_files(self, request, *args, **kwargs):
        _user = self.request.user
        file_id = request.query_params.get("file_id", None)
        file = models.CommunityResource.objects.filter(id=file_id).first()
        community_manager = file.community.manager
        if not _user == community_manager:
            return Response({"message": "فقط مدیر انجمن اجازه انجام این عملیات را دارد!"})

        if not file_id or not file:
            return Response(data={"فایل یافت نشد!"}, status=status.HTTP_400_BAD_REQUEST)

        file.delete()
        return Response({"message": "فایل مورد نظر حذف شد."}, status=status.HTTP_200_OK)
