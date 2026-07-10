from django import forms
from .models import Purchase, is_empty_value


class SuperuserPurchaseEditForm(forms.ModelForm):
    """فرم ویرایش کامل خرید — فقط برای سوپر یوزر"""

    class Meta:
        model = Purchase
        fields = [
            'base_number', 'request_date', 'purchase_date', 'supply_unit', 'requester',
            'product_code', 'product_title', 'unit', 'quantity', 'expert_name', 'description',
            'status', 'required_date', 'inquiry_deadline', 'inquiry_deadline_2',
            'inquiry_number', 'inquiry_received_date', 'purchase_type',
            'preinvoice_number', 'preinvoice_price', 'preinvoice_total',
            'order_number', 'order_date',
            'order_request_number', 'order_request_status', 'order_request_date',
            'order_total', 'advance_payment', 'deductions',
            'delivered_quantity', 'delivery_number', 'delivery_date', 'supplier',
            'invoice_price', 'invoice_number', 'invoice_total',
            'payment_request_amount', 'payment_request_number',
            'payment_registration_date', 'payment_completion_date',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'form-input'
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': css, 'rows': 3})
            elif isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.update({'class': css, 'step': 'any'})
            else:
                field.widget.attrs.update({'class': css})
            if self.instance and name in self.fields:
                val = getattr(self.instance, name, None)
                if val is not None and is_empty_value(val):
                    self.initial[name] = '' if isinstance(field, forms.CharField) else None

    def _normalize_char(self, value):
        if value is None:
            return ''
        value = str(value).strip()
        if is_empty_value(value):
            return ''
        return value

    def clean(self):
        cleaned = super().clean()
        for name, field in self.fields.items():
            if name in cleaned and cleaned[name] is not None and isinstance(field, forms.CharField):
                cleaned[name] = self._normalize_char(cleaned[name])
        return cleaned