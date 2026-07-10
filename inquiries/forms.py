from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Inquiry


class IssueInquiryForm(forms.Form):
    """فرم صدور استعلام"""
    
    inquiry_number = forms.CharField(
        max_length=50,
        required=False,
        label=_('شماره استعلام'),
        help_text=_('خالی بگذارید تا خودکار تولید شود'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'placeholder': 'خودکار تولید می‌شود'
        })
    )
    
    inquiry_date = forms.CharField(
        max_length=20,
        required=False,
        label=_('تاریخ استعلام'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'placeholder': '1405/04/02'
        })
    )
    
    deadline = forms.CharField(
        max_length=20,
        required=False,
        label=_('مهلت پاسخ استعلام'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'placeholder': '1405/04/20'
        })
    )
    
    PURCHASE_TYPE_CHOICES = [
        ('', '--- انتخاب کنید ---'),
        ('استعلامي', 'استعلامی'),
        ('مناقصه', 'مناقصه'),
        ('خرید مستقیم', 'خرید مستقیم'),
        ('ترک تشریفات', 'ترک تشریفات'),
    ]
    purchase_type = forms.ChoiceField(
        choices=PURCHASE_TYPE_CHOICES,
        required=False,
        label=_('نوع خرید'),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'
        })
    )
    
    URGENCY_CHOICES = [
        ('', '--- عادی ---'),
        ('عادی', 'عادی'),
        ('فوری', 'فوری'),
        ('آنی', 'آنی'),
    ]
    urgency_code = forms.ChoiceField(
        choices=URGENCY_CHOICES,
        required=False,
        label=_('فوریت'),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'
        })
    )
    
    warehouse = forms.CharField(
        max_length=100,
        required=False,
        label=_('انبار مقصد'),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
        }),
    )

    product_category = forms.CharField(
        max_length=100,
        required=False,
        label=_('گروه بندی کالایی'),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
        }),
    )

    warehouse_request_number = forms.CharField(
        max_length=50,
        required=False,
        label=_('شماره درخواست کالا از انبار'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
        }),
    )

    warehouse_request_date = forms.CharField(
        max_length=20,
        required=False,
        label=_('تاریخ ثبت کالا از انبار'),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'placeholder': '1405/04/02',
        }),
    )
    
    reason = forms.CharField(
        required=False,
        label=_('علت خرید'),
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'rows': 3,
            'placeholder': 'علت نیاز به این خرید...'
        })
    )
    
    risk_note = forms.CharField(
        required=False,
        label=_('ریسک عدم خرید'),
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500',
            'rows': 2,
            'placeholder': 'در صورت عدم خرید چه مشکلی پیش می‌آید...'
        })
    )