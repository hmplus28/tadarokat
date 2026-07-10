"""سرویس خروجی اکسل پویا"""
import pandas as pd
from io import BytesIO
from datetime import datetime
from purchases.models import Purchase
from inquiries.models import Inquiry
from orders.models import Order


class ExportService:
    @staticmethod
    def export_purchases(queryset) -> tuple:
        """خروجی اکسل از درخواست‌های خرید"""
        data = queryset.values(
            'purchase_number', 'line_number', 'product_title', 'product_code',
            'quantity', 'unit', 'product_category', 'deadline_deviated', 'base_number', 'request_date',
            'expert_name', 'requester', 'purchase_date',
            'required_date', 'status', 'current_status',
            'inquiry_number', 'order_number', 'delivery_number',
            'supplier', 'order_total', 'invoice_total',
        )
        df = pd.DataFrame(list(data))

        if not df.empty:
            if 'current_status' in df.columns:
                df['current_status'] = df['current_status'].map(
                    Purchase.CURRENT_STATUS_LABELS
                ).fillna(df['current_status'])
            if 'deadline_deviated' in df.columns:
                df['deadline_deviated'] = df['deadline_deviated'].map(
                    {True: 'بله', False: 'خیر'}
                ).fillna('خیر')

        col_map = {
            'purchase_number': 'شماره خرید',
            'line_number': 'شماره خط',
            'product_title': 'عنوان کالا',
            'product_code': 'کد کالا',
            'quantity': 'مقدار',
            'unit': 'واحد',
            'product_category': 'گروه بندی کالایی',
            'deadline_deviated': 'انحراف مهلت',
            'base_number': 'شماره درخواست کالا از انبار',
            'request_date': 'تاریخ ثبت کالا از انبار',
            'expert_name': 'کارشناس',
            'requester': 'درخواست کننده',
            'purchase_date': 'تاریخ درخواست',
            'required_date': 'تاریخ نیاز',
            'status': 'وضعیت درخواست',
            'current_status': 'وضعیت فعلی',
            'inquiry_number': 'شماره استعلام',
            'order_number': 'شماره دستور',
            'delivery_number': 'شماره تحویل',
            'supplier': 'تامین کننده',
            'order_total': 'جمع سفارش',
            'invoice_total': 'جمع فاکتور',
        }
        df = df.rename(columns=col_map)

        buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"purchases_{timestamp}.xlsx"

        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='درخواست‌های خرید')
            worksheet = writer.sheets['درخواست‌های خرید']
            for i, col in enumerate(df.columns, 1):
                max_length = max(df[col].astype(str).apply(len).max(), len(str(col))) + 2
                col_letter = chr(64 + i) if i <= 26 else 'A' + chr(64 + i - 26)
                worksheet.column_dimensions[col_letter].width = min(max_length, 45)

        buffer.seek(0)
        return buffer.getvalue(), filename

    @staticmethod
    def export_orders(queryset) -> tuple:
        """خروجی اکسل از کوئری‌ست دستورات"""
        data = queryset.values(
            'order_number', 'product_title', 'product_code',
            'contractor', 'quantity', 'unit', 'unit_price', 'total_price',
            'stage', 'order_date', 'expert_name', 'warehouse',
            'order_request_number', 'order_request_date',
            'payment_number', 'payment_date',
            'delivery_number', 'delivery_date',
        )
        df = pd.DataFrame(list(data))
        
        col_map = {
            'order_number': 'شماره دستور',
            'product_title': 'عنوان کالا',
            'product_code': 'کد کالا',
            'contractor': 'پیمانکار',
            'quantity': 'تعداد',
            'unit': 'واحد',
            'unit_price': 'فی واحد',
            'total_price': 'جمع کل',
            'stage': 'مرحله فعلی',
            'order_date': 'تاریخ صدور',
            'expert_name': 'کارشناس',
            'warehouse': 'انبار',
            'order_request_number': 'شماره سفارش',
            'order_request_date': 'تاریخ سفارش',
            'payment_number': 'شماره پرداخت',
            'payment_date': 'تاریخ پرداخت',
            'delivery_number': 'شماره تحویل',
            'delivery_date': 'تاریخ تحویل',
        }
        df = df.rename(columns=col_map)
        
        # ترجمه stage به فارسی
        stage_map = {
            'order_issued': 'صدور دستور',
            'order_placed': 'ثبت سفارش',
            'payment': 'پرداخت',
            'delivered': 'تحویل شده',
        }
        if 'مرحله فعلی' in df.columns:
            df['مرحله فعلی'] = df['مرحله فعلی'].map(stage_map).fillna(df['مرحله فعلی'])
        
        buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"orders_{timestamp}.xlsx"
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='دستورات خرید')
            
            # تنظیم ستون‌ها
            worksheet = writer.sheets['دستورات خرید']
            for i, col in enumerate(df.columns, 1):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                ) + 2
                worksheet.column_dimensions[chr(64 + i) if i <= 26 else 'A' + chr(64 + i - 26)].width = min(max_length, 40)
        
        buffer.seek(0)
        return buffer.getvalue(), filename

    @staticmethod
    def _calc_preinvoice_total(inv: dict) -> float:
        subtotal = sum(
            float(line.get('quantity', 0) or 0) * float(line.get('unit_price', 0) or 0)
            for line in inv.get('lines', [])
        )
        tax = subtotal * (float(inv.get('tax_rate', 0) or 0) / 100)
        return subtotal + tax - float(inv.get('discount', 0) or 0)

    @staticmethod
    def export_wizard_preinvoices(purchase_data: dict, header: dict, pre_invoices: list) -> tuple:
        """خروجی اکسل مقایسه و پیش‌فاکتورها (Wizard صدور استعلام)"""
        purchase_number = purchase_data.get('purchase_number', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"preinvoices_{purchase_number}_{timestamp}.xlsx"

        info_rows = [
            {'فیلد': 'شماره خرید', 'مقدار': purchase_number},
            {'فیلد': 'عنوان کالا', 'مقدار': purchase_data.get('product_title', '')},
            {'فیلد': 'کد کالا', 'مقدار': purchase_data.get('product_code', '')},
            {'فیلد': 'مقدار', 'مقدار': f"{purchase_data.get('quantity', '')} {purchase_data.get('unit', '')}"},
            {'فیلد': 'شماره استعلام', 'مقدار': header.get('inquiry_number', '')},
            {'فیلد': 'تاریخ استعلام', 'مقدار': header.get('inquiry_date', '')},
            {'فیلد': 'مهلت پاسخ', 'مقدار': header.get('deadline', '')},
            {'فیلد': 'نوع خرید', 'مقدار': header.get('purchase_type', '')},
            {'فیلد': 'فوریت', 'مقدار': header.get('urgency_code', '')},
            {'فیلد': 'واحد تامین', 'مقدار': header.get('supply_unit', '')},
            {'فیلد': 'انبار مقصد', 'مقدار': header.get('warehouse', '')},
            {'فیلد': 'گروه بندی کالایی', 'مقدار': header.get('product_category', '')},
            {'فیلد': 'شماره درخواست کالا از انبار', 'مقدار': header.get('warehouse_request_number', '')},
            {'فیلد': 'تاریخ ثبت کالا از انبار', 'مقدار': header.get('warehouse_request_date', '')},
            {'فیلد': 'درخواست دهنده', 'مقدار': header.get('requester', '')},
        ]
        df_info = pd.DataFrame(info_rows)

        all_products = set()
        for inv in pre_invoices:
            for line in inv.get('lines', []):
                title = line.get('product_title', '').strip()
                if title:
                    all_products.add(title)

        comparison_rows = []
        for product in sorted(all_products):
            row = {'عنوان کالا': product}
            for i, inv in enumerate(pre_invoices):
                contractor = inv.get('contractor') or f'پیمانکار {i + 1}'
                line = next(
                    (l for l in inv.get('lines', []) if l.get('product_title') == product),
                    None,
                )
                if line:
                    qty = line.get('quantity', 0)
                    unit = line.get('unit', '')
                    price = line.get('unit_price', 0)
                    total = float(qty or 0) * float(price or 0)
                    row[contractor] = f'{qty} {unit} | فی: {price:,} | جمع: {total:,}'
                else:
                    row[contractor] = '—'
            comparison_rows.append(row)

        total_row = {'عنوان کالا': 'جمع کل (با مالیات)'}
        totals = [ExportService._calc_preinvoice_total(inv) for inv in pre_invoices]
        min_total = min(totals) if totals else 0
        for i, inv in enumerate(pre_invoices):
            contractor = inv.get('contractor') or f'پیمانکار {i + 1}'
            total = totals[i]
            suffix = ' ✓ کمترین' if total == min_total else ''
            total_row[contractor] = f'{total:,.0f} ریال{suffix}'
        comparison_rows.append(total_row)
        df_compare = pd.DataFrame(comparison_rows)

        detail_rows = []
        for i, inv in enumerate(pre_invoices):
            contractor = inv.get('contractor') or f'پیمانکار {i + 1}'
            tax_rate = float(inv.get('tax_rate', 0) or 0)
            invoice_type = 'فاکتور رسمی' if tax_rate > 0 else 'فاکتور کد ملی'
            for line in inv.get('lines', []):
                qty = float(line.get('quantity', 0) or 0)
                price = float(line.get('unit_price', 0) or 0)
                detail_rows.append({
                    'پیمانکار': contractor,
                    'شماره پیش‌فاکتور': inv.get('invoice_number', ''),
                    'نوع فاکتور': invoice_type,
                    'تاریخ پیش‌فاکتور': inv.get('invoice_date', ''),
                    'شهر': inv.get('city', ''),
                    'انتخاب شده': 'بله' if inv.get('is_selected') else 'خیر',
                    'ردیف': line.get('row_number', ''),
                    'عنوان کالا': line.get('product_title', ''),
                    'کد کالا': line.get('product_code', ''),
                    'تعداد': line.get('quantity', ''),
                    'واحد': line.get('unit', ''),
                    'فی واحد (ریال)': line.get('unit_price', ''),
                    'جمع قلم (ریال)': qty * price,
                })
            discount = float(inv.get('discount', 0) or 0)
            if discount > 0:
                detail_rows.append({
                    'پیمانکار': contractor,
                    'شماره پیش‌فاکتور': '',
                    'نوع فاکتور': invoice_type,
                    'تاریخ پیش‌فاکتور': '',
                    'شهر': '',
                    'انتخاب شده': 'بله' if inv.get('is_selected') else 'خیر',
                    'ردیف': '',
                    'عنوان کالا': 'تخفیف (کسور)',
                    'کد کالا': '',
                    'تعداد': '',
                    'واحد': '',
                    'فی واحد (ریال)': '',
                    'جمع قلم (ریال)': -discount,
                })
            detail_rows.append({
                'پیمانکار': contractor,
                'شماره پیش‌فاکتور': '',
                'نوع فاکتور': invoice_type,
                'تاریخ پیش‌فاکتور': '',
                'شهر': '',
                'انتخاب شده': 'بله' if inv.get('is_selected') else 'خیر',
                'ردیف': '',
                'عنوان کالا': 'جمع کل پیش‌فاکتور',
                'کد کالا': '',
                'تعداد': '',
                'واحد': '',
                'فی واحد (ریال)': '',
                'جمع قلم (ریال)': ExportService._calc_preinvoice_total(inv),
            })
        df_details = pd.DataFrame(detail_rows)

        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_info.to_excel(writer, index=False, sheet_name='اطلاعات')
            df_compare.to_excel(writer, index=False, sheet_name='مقایسه')
            df_details.to_excel(writer, index=False, sheet_name='پیش‌فاکتورها')

            for sheet_name, df in [
                ('اطلاعات', df_info),
                ('مقایسه', df_compare),
                ('پیش‌فاکتورها', df_details),
            ]:
                worksheet = writer.sheets[sheet_name]
                for i, col in enumerate(df.columns, 1):
                    max_length = max(df[col].astype(str).apply(len).max(), len(str(col))) + 2
                    col_letter = chr(64 + i) if i <= 26 else 'A' + chr(64 + i - 26)
                    worksheet.column_dimensions[col_letter].width = min(max_length, 45)

        buffer.seek(0)
        return buffer.getvalue(), filename