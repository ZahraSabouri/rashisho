# apps/access/domain.py
from enum import Enum

class AdminSection(str, Enum):
    USERS = "users"
    PROJECTS = "projects"
    EXAMS = "exams"
    FEATURE_FLAGS = "feature_flags"

class TeamRole(str, Enum):
    LEADER = "C"   # در داده‌های فعلی برای سرگروه از "C" استفاده می‌شود. :contentReference[oaicite:2]{index=2}
    MEMBER = "M"
    FREE = "F"
