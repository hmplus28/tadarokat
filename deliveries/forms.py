from django import forms
from django.utils.translation import gettext_lazy as _


class CreateDeliveryForm(forms.Form):
    """فرم ثبت تحویل کالا"""
    
    delivery_number = forms.CharField(
        max_length=50, required=True, label=_('شماره تحویل / مجوز ورود'),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'placeholder': 'مثلاً: DL-7001 یا شماره مجوز'})
    )
    delivery_date = forms.CharField(
        max_length=20, required=True, label=_('تاریخ تحویل'),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'placeholder': '1405/04/15'})
    )
    receiver = forms.CharField(
        max_length=100, required=False, label=_('تحویل گیرنده'),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'placeholder': 'نام شخص یا واحد دریافت کننده'})
    )
    description = forms.CharField(
        required=False, label=_('توضیحات انباردار'),
        widget=forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none', 'rows': 3, 'placeholder': 'وضعیت ظاهری کالا، مغایرت‌ها و...'})
    )