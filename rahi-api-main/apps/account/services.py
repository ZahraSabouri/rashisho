import requests
from django.conf import settings
from dataclasses import dataclass
from django.contrib.auth import get_user_model
from dataclasses import dataclass
from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.account.models import Connection

def get_sso_user_info(token):
    try:
        response = requests.get(
            url=f"{settings.SSO_BASE_URL}/api/v1/user/me/",
            headers={"Authorization": f"Bearer {token}"},
        )
        return response.json()

    except Exception:
        return {}



@dataclass
class ConnectionService:
    @transaction.atomic
    def send_request(self, from_user_id: int, to_user_id: int) -> Connection:
        User = get_user_model()

        if from_user_id == to_user_id:
            raise ValidationError({"to_user": "نمی‌توانید به خودتان درخواست بدهید."})

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            raise ValidationError({"to_user": "کاربر مقصد پیدا نشد."})

        # جلوگیری از تکرار درخواست مشابه
        if Connection.objects.filter(from_user_id=from_user_id, to_user_id=to_user_id).exists():
            raise ValidationError({"detail": "درخواست قبلاً ارسال شده است."})

        return Connection.objects.create(
            from_user_id=from_user_id,
            to_user=to_user,
            status="pending",
        )

    def list_pendings(self, user_id: int, box: str | None = None):
        """
        box: 'received' | 'sent' | None
        - None => هر دو سمت را برمی‌گرداند (sent/received) با status=pending
        """
        qs = Connection.objects.select_related("from_user", "to_user").filter(status="pending")
        if box == "received":
            qs = qs.filter(to_user_id=user_id)
        elif box == "sent":
            qs = qs.filter(from_user_id=user_id)
        else:
            qs = qs.filter(models.Q(to_user_id=user_id) | models.Q(from_user_id=user_id))
        return qs.order_by("-created_at")

    @transaction.atomic
    def decide(self, *, connection_id: int, actor_user_id: int, decision: str) -> Connection:
        """
        decision: 'accepted' | 'rejected'
        فقط گیرنده‌ی درخواست می‌تواند تصمیم بگیرد.
        """
        if decision not in ("accepted", "rejected"):
            raise ValidationError({"decision": "decisions مجاز: accepted | rejected"})

        try:
            conn = Connection.objects.select_for_update().get(id=connection_id)
        except Connection.DoesNotExist:
            raise ValidationError({"detail": "درخواست یافت نشد."})

        if conn.to_user_id != actor_user_id:
            # مشابه Authorization در .NET (Policy/Filter)
            raise PermissionDenied("فقط گیرنده‌ی درخواست می‌تواند تصمیم بگیرد.")

        if conn.status != "pending":
            raise ValidationError({"detail": "این درخواست قبلاً تعیین تکلیف شده است."})

        conn.status = decision
        conn.save(update_fields=["status", "updated_at"])
        return conn
