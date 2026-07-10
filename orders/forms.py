from django import forms
from django.utils.translation import gettext_lazy as _


class CreateOrderForm(forms.Form):
    """فرم صدور دستور خرید"""
    order_number = forms.CharField(required=False, label=_('شماره دستور'),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'placeholder': 'خودکار'}))
    order_date = forms.CharField(required=False, label=_('تاریخ صدور'),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'placeholder': '1405/04/10'}))
    contractor = forms.CharField(required=True, label=_('تامین کننده / پیمانکار'),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'placeholder': 'نام شرکت یا شخص تامین کننده'}))
    unit_price = forms.DecimalField(required=False, label=_('فی واحد (ریال)'),
        widget=forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none'}))
    description = forms.CharField(required=False, label=_('توضیحات'),
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'rows': 3}))


class AdvanceStageForm(forms.Form):
    """فرم پیشبرد مرحله - فیلدها داینامیک هستند"""
    field1 = forms.CharField(required=False, label='',
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none'}))
    field2 = forms.CharField(required=False, label='',
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none'}))
    note = forms.CharField(required=False, label=_('یادداشت'),
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'rows': 2, 'placeholder': 'توضیحات اختیاری...'}))