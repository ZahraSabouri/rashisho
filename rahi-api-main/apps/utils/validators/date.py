from django.core.validators import RegexValidator


class DateValidation(RegexValidator):
    regex = r"\d{4}-\d{2}-\d{2}"
    message = "باشد YYYY-MM-DD فرمت تاریخ به صورت"
