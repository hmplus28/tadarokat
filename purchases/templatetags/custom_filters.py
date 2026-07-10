from django import template
import json
from purchases.models import Purchase, is_valid_value, is_empty_value

register = template.Library()


@register.filter(name='status_fa')
def status_fa(value):
    """تبدیل کد وضعیت انگلیسی به برچسب فارسی"""
    return Purchase.get_status_label(value)


@register.filter(name='workflow_display')
def workflow_display(value):
    """نمایش مقدار واقعی یا — برای فیلدهای خالی/در انتظار اکسل"""
    if is_empty_value(value):
        return '—'
    return value


@register.filter(name='has_workflow_value')
def has_workflow_value(value):
    """آیا فیلد مقدار واقعی دارد (نه متن placeholder اکسل)؟"""
    return is_valid_value(value)


@register.filter(name='payment_timeline_state')
def payment_timeline_state(purchase):
    """وضعیت نمایشی مرحله پرداخت در گردشکار: pending / current / completed"""
    from purchases.models import is_real_date, is_tankhah

    has_ref = is_valid_value(getattr(purchase, 'payment_request_number', None))
    if not has_ref:
        try:
            amount = float(getattr(purchase, 'payment_request_amount', 0) or 0)
            has_ref = amount > 0
        except (TypeError, ValueError):
            has_ref = False

    if not has_ref:
        return 'pending'

    status = getattr(purchase, 'current_status', '')
    if status == 'paid' or is_real_date(getattr(purchase, 'payment_completion_date', None)):
        return 'completed'
    if is_tankhah(getattr(purchase, 'payment_request_number', None)):
        return 'completed'
    if status == 'waiting_payment':
        return 'current'
    return 'pending'


@register.filter(name='payment_is_completed')
def payment_is_completed(purchase):
    """آیا پرداخت واقعاً انجام شده است؟"""
    from purchases.models import is_real_date, is_tankhah

    if getattr(purchase, 'current_status', '') == 'paid':
        return True
    if is_real_date(getattr(purchase, 'payment_completion_date', None)):
        return True
    if is_tankhah(getattr(purchase, 'payment_request_number', None)):
        return True
    return False


@register.filter(name='fa')
def to_persian_digits(value):
    """تبدیل اعداد لاتین به فارسی"""
    if value is None:
        return value
    s = str(value)
    # جایگزینی اعداد لاتین با فارسی
    latin_to_persian = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return s.translate(latin_to_persian)


@register.filter(name='fa_comma')
def to_persian_with_comma(value):
    """تبدیل اعداد به فارسی با جداکننده هزارگان"""
    if value is None:
        return '۰'
    try:
        num = float(value)
        # جدا کردن بخش صحیح و اعشار
        if num == int(num):
            int_part = f"{int(num):,}".replace(',', '٬')
            return int_part.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
        else:
            formatted = f"{num:,.2f}".replace(',', '٬')
            return formatted.translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))
    except (ValueError, TypeError):
        return str(value).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))


@register.filter(name='list')
def to_list(value):
    try:
        return list(value)
    except (TypeError, ValueError):
        return []


@register.filter(name='tojson')
def to_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return '[]'


@register.filter(name='percentage')
def percentage(value, total):
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
    
    
@register.filter(name='list')
def to_list(value):
    """تبدیل dict_keys/dict_values به list برای استفاده در JavaScript"""
    try:
        return list(value)
    except (TypeError, ValueError):
        return []


@register.filter(name='tojson')
def to_json(value):
    """تبدیل مقدار به JSON برای استفاده در JavaScript"""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return '[]'


@register.filter(name='get_item')
def get_item(obj, key):
    """دریافت آیتم از دیکشنری یا فیلد فرم Django با نام"""
    if obj is None or not key:
        return ''
    if isinstance(obj, dict):
        return obj.get(key, '')
    try:
        return obj[key]
    except (TypeError, KeyError, AttributeError):
        return ''


@register.filter(name='mul')
def mul(value, arg):
    """ضرب دو عدد"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter(name='percentage')
def percentage(value, total):
    """محاسبه درصد"""
    try:
        if float(total) == 0:
            return 0
        return round((float(value) / float(total)) * 100, 1)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter(name='fa_compact')
def to_persian_compact(value):
    """
    نمایش خلاصه اعداد بزرگ به فارسی
    1234 → ۱٬۲۳۴
    1234567 → ۱.۲۳ میلیون
    1271711387236 → ۱.۲۷ هزار میلیارد
    """
    if value is None:
        return '۰'
    try:
        num = float(value)
    except (ValueError, TypeError):
        return to_persian_digits(value)
    
    latin_to_persian = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    
    abs_num = abs(num)
    sign = '-' if num < 0 else ''
    
    if abs_num < 1000:
        result = f"{int(abs_num):,}".replace(',', '٬')
    elif abs_num < 1_000_000:
        result = f"{abs_num/1_000:.1f} هزار"
    elif abs_num < 1_000_000_000:
        result = f"{abs_num/1_000_000:.2f} میلیون"
    elif abs_num < 1_000_000_000_000:
        result = f"{abs_num/1_000_000_000:.2f} میلیارد"
    else:
        # هزار میلیارد (Trillion)
        result = f"{abs_num/1_000_000_000_000:.2f} هزار میلیارد"
    
    return (sign + result).translate(latin_to_persian)


@register.filter(name='dict_get')
def dict_get(mapping, key):
    """دسترسی به مقدار دیکشنری در قالب — {{ mydict|dict_get:'key' }}"""
    if mapping is None:
        return ''
    try:
        return mapping.get(key, 0)
    except AttributeError:
        return ''