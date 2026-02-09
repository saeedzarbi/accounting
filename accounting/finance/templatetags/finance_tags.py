"""
فیلترهای قالب برای ماژول مالی — مثلاً نمایش تاریخ شمسی.
"""

from datetime import date as date_type
from datetime import datetime as datetime_type

from django import template
from django.utils import timezone

register = template.Library()


def _to_jdate(value, as_datetime=False):
    """تبدیل date یا datetime به jdatetime. اگر as_datetime=True و value datetime باشد، jdatetime.datetime برمی‌گرداند."""
    if value is None:
        return None
    try:
        from jdatetime import date as jdate
        from jdatetime import datetime as jdatetime_type
    except ImportError:
        return None
    if isinstance(value, datetime_type):
        if timezone.is_naive(value):
            dt = value
        else:
            dt = timezone.localtime(value)
        if as_datetime:
            return jdatetime_type.fromgregorian(
                year=dt.year,
                month=dt.month,
                day=dt.day,
                hour=dt.hour,
                minute=dt.minute,
                second=dt.second,
                microsecond=dt.microsecond,
            )
        return jdate.fromgregorian(year=dt.year, month=dt.month, day=dt.day)
    if isinstance(value, date_type):
        return jdate.fromgregorian(year=value.year, month=value.month, day=value.day)
    if isinstance(value, str) and value.strip():
        # رشته‌های عددی شمسی مثل 1403/05/15 یا ۱۴۰۳/۰۵/۱۵
        parts = (
            value.replace("۰", "0")
            .replace("۱", "1")
            .replace("۲", "2")
            .replace("۳", "3")
            .replace("۴", "4")
            .replace("۵", "5")
            .replace("۶", "6")
            .replace("۷", "7")
            .replace("۸", "8")
            .replace("۹", "9")
            .replace("/", "-")
            .split("-")
        )
        if len(parts) >= 3:
            try:
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                if 1200 <= y <= 1500:  # احتمالاً شمسی
                    return jdate(y, m, d)
                if 1900 <= y <= 2100:  # میلادی
                    return jdate.fromgregorian(year=y, month=m, day=d)
            except (ValueError, TypeError):
                pass
    return None


@register.filter
def shamsi_date(value, arg=None):
    """
    نمایش تاریخ به شمسی.
    استفاده: {{ some_date|shamsi_date }} یا {{ some_date|shamsi_date:"%Y/%m/%d" }}
    برای تاریخ و ساعت: {{ dt|shamsi_date:"%Y/%m/%d %H:%M" }}
    اگر مقدار خالی باشد "—" برمی‌گرداند.
    """
    fmt = arg or "%Y/%m/%d"
    as_datetime = "%H" in fmt or "%M" in fmt or "%S" in fmt
    jd = _to_jdate(value, as_datetime=as_datetime)
    if jd is None:
        return "—"
    try:
        return jd.strftime(fmt)
    except (TypeError, ValueError):
        if as_datetime and hasattr(jd, "hour"):
            return "%04d/%02d/%02d %02d:%02d" % (
                jd.year,
                jd.month,
                jd.day,
                jd.hour,
                jd.minute,
            )
        return "%04d/%02d/%02d" % (jd.year, jd.month, jd.day)
