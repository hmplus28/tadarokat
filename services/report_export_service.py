"""خروجی اکسل گزارش‌های پنل"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd


class ReportExportService:
    @staticmethod
    def _write_workbook(filename_prefix: str, sheets: Dict[str, List[Dict[str, Any]]]) -> tuple:
        buffer = BytesIO()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f"{filename_prefix}_{timestamp}.xlsx"

        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            for sheet_name, rows in sheets.items():
                df = pd.DataFrame(rows or [{}])
                safe_name = sheet_name[:31]
                df.to_excel(writer, index=False, sheet_name=safe_name)
                worksheet = writer.sheets[safe_name]
                for i, col in enumerate(df.columns, 1):
                    try:
                        max_len = max(df[col].astype(str).apply(len).max(), len(str(col))) + 2
                    except ValueError:
                        max_len = len(str(col)) + 2
                    col_letter = chr(64 + i) if i <= 26 else 'A' + chr(64 + i - 26)
                    worksheet.column_dimensions[col_letter].width = min(int(max_len), 50)

        buffer.seek(0)
        return buffer.getvalue(), filename

    @classmethod
    def export_purchase_report(cls, context: Dict[str, Any]) -> tuple:
        total_value = context.get('total_value') or {}

        summary = [
            {'شاخص': 'کل درخواست‌ها', 'مقدار': context.get('total_purchases', 0)},
            {'شاخص': 'ارزش سفارشات', 'مقدار': total_value.get('order_total') or 0},
            {'شاخص': 'ارزش فاکتورها', 'مقدار': total_value.get('invoice_total') or 0},
            {'شاخص': 'نرخ تکمیل (٪)', 'مقدار': context.get('completion_rate', 0)},
            {'شاخص': 'به‌موقع مهلت درخواست', 'مقدار': context.get('deadline_on_time_count', 0)},
            {'شاخص': 'انحراف مهلت درخواست', 'مقدار': context.get('deadline_deviated_count', 0)},
        ]
        order_dl = context.get('order_deadline_summary') or {}
        summary.extend([
            {'شاخص': 'سفارش به‌موقع (O←AB)', 'مقدار': order_dl.get('on_time', 0)},
            {'شاخص': 'انحراف مهلت سفارش', 'مقدار': order_dl.get('deviated', 0)},
            {'شاخص': 'نرخ انحراف سفارش (٪)', 'مقدار': order_dl.get('rate', 0)},
            {'شاخص': 'استعلام‌ها در پنل', 'مقدار': context.get('inquiry_count', 0)},
            {'شاخص': 'دستورات در پنل', 'مقدار': context.get('order_count', 0)},
            {'شاخص': 'تحویل‌ها در پنل', 'مقدار': context.get('delivery_count', 0)},
        ])

        status_rows = [
            {'وضعیت': name, 'تعداد': count}
            for name, count in (context.get('status_stats') or {}).items()
        ]
        monthly_rows = [
            {'ماه': (row.get('month') or '').rstrip('/'), 'تعداد': row.get('count', 0)}
            for row in (context.get('monthly_stats') or [])
        ]
        type_rows = [
            {'نوع خرید': row.get('purchase_type', ''), 'تعداد': row.get('count', 0)}
            for row in (context.get('type_stats') or [])
        ]
        category_rows = [
            {'گروه کالایی': row.get('product_category', ''), 'تعداد': row.get('count', 0)}
            for row in (context.get('category_stats') or [])
        ]
        stage_rows = [
            {
                'مرحله': stage.label,
                'میانگین (روز)': stage.avg_days,
                'میانه (روز)': stage.median_days,
                'تعداد نمونه': stage.sample_count,
            }
            for stage in (context.get('stage_averages') or [])
        ]

        return cls._write_workbook('report_purchase', {
            'خلاصه': summary,
            'وضعیت‌ها': status_rows,
            'ماهانه': monthly_rows,
            'نوع خرید': type_rows,
            'گروه کالایی': category_rows,
            'میانگین مراحل': stage_rows,
        })

    @classmethod
    def export_expert_performance(
        cls,
        experts_stats: List[Dict[str, Any]],
        overall: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        overall = overall or {}
        summary = [
            {'شاخص': 'بررسی‌شده (O←AB)', 'مقدار': overall.get('evaluated', 0)},
            {'شاخص': 'به‌موقع', 'مقدار': overall.get('on_time', 0)},
            {'شاخص': 'انحراف', 'مقدار': overall.get('deviated', 0)},
            {'شاخص': 'نرخ انحراف (٪)', 'مقدار': overall.get('rate', 0)},
        ]
        rows = []
        for ex in experts_stats:
            rows.append({
                'کارشناس': ex.get('name', ex.get('expert_name', '')),
                'کل پرونده': ex.get('total', ex.get('total_purchases', 0)),
                'بررسی‌شده': ex.get('evaluated', 0),
                'به‌موقع (O←AB)': ex.get('on_time', ex.get('order_deadline_on_time', 0)),
                'انحراف (O←AB)': ex.get('deviated', ex.get('order_deadline_deviated', 0)),
                'نرخ انحراف (٪)': ex.get('rate', ex.get('order_deadline_rate', 0)),
            })
        return cls._write_workbook('report_experts', {
            'خلاصه': summary,
            'عملکرد کارشناسان': rows,
        })

    @classmethod
    def export_deadline_deviation(cls, data: Dict[str, Any]) -> tuple:
        filter_label = data.get('filter_label', 'همه دوره‌ها')
        overall = data.get('overall') or {}
        order_overall = data.get('order_overall') or {}

        request_summary = [
            {'شاخص': 'فیلتر تاریخ درخواست', 'مقدار': filter_label},
            {'شاخص': 'کل پرونده‌ها', 'مقدار': overall.get('total', 0)},
            {'شاخص': 'بررسی‌شده', 'مقدار': overall.get('evaluated', 0)},
            {'شاخص': 'به‌موقع', 'مقدار': overall.get('on_time', 0)},
            {'شاخص': 'انحراف', 'مقدار': overall.get('deviated', 0)},
            {'شاخص': 'نرخ انحراف (٪)', 'مقدار': overall.get('rate', 0)},
        ]
        order_summary = [
            {'شاخص': 'بررسی‌شده', 'مقدار': order_overall.get('evaluated', 0)},
            {'شاخص': 'به‌موقع', 'مقدار': order_overall.get('on_time', 0)},
            {'شاخص': 'انحراف', 'مقدار': order_overall.get('deviated', 0)},
            {'شاخص': 'نرخ انحراف (٪)', 'مقدار': order_overall.get('rate', 0)},
        ]

        category_rows = [
            {
                'گروه کالایی': row.get('name', ''),
                'قانون مهلت': row.get('rule', ''),
                'کل': row.get('total', 0),
                'بررسی‌شده': row.get('evaluated', 0),
                'به‌موقع': row.get('on_time', 0),
                'انحراف': row.get('deviated', 0),
                'نرخ انحراف (٪)': row.get('rate', 0),
            }
            for row in (data.get('category_stats') or [])
        ]
        warehouse_rows = [
            {
                'انبار مقصد': row.get('name', ''),
                'کل': row.get('total', 0),
                'به‌موقع': row.get('on_time', 0),
                'انحراف': row.get('deviated', 0),
                'نرخ انحراف (٪)': row.get('rate', 0),
            }
            for row in (data.get('warehouse_stats') or [])
        ]
        request_deviated_rows = [
            {
                'شماره خرید': row.get('purchase_number', ''),
                'گروه کالایی': row.get('product_category', ''),
                'تاریخ درخواست': row.get('purchase_date', ''),
                'انبار': row.get('warehouse', ''),
                'مهلت مجاز': row.get('deadline_info', ''),
            }
            for row in (data.get('recent_deviated') or [])
        ]
        order_expert_rows = [
            {
                'کارشناس': row.get('name', ''),
                'کل پرونده': row.get('total', 0),
                'بررسی‌شده': row.get('evaluated', 0),
                'به‌موقع': row.get('on_time', 0),
                'انحراف': row.get('deviated', 0),
                'نرخ انحراف (٪)': row.get('rate', 0),
            }
            for row in (data.get('order_expert_stats') or [])
            if row.get('evaluated', 0) > 0
        ]
        order_category_rows = [
            {
                'گروه کالایی': row.get('name', ''),
                'بررسی‌شده': row.get('evaluated', 0),
                'به‌موقع': row.get('on_time', 0),
                'انحراف': row.get('deviated', 0),
                'نرخ انحراف (٪)': row.get('rate', 0),
            }
            for row in (data.get('order_category_stats') or [])
            if row.get('evaluated', 0) > 0
        ]
        order_case_rows = []
        for expert in (data.get('order_cases_by_expert') or []):
            for case in expert.get('cases', []):
                order_case_rows.append({
                    'کارشناس': expert.get('name', ''),
                    'شماره خرید': case.get('purchase_number', ''),
                    'عنوان کالا': case.get('product_title', ''),
                    'مهلت (O)': case.get('deadline', ''),
                    'تاریخ سفارش (AB)': case.get('order_date', ''),
                    'وضعیت': case.get('status', ''),
                    'تأخیر (روز)': case.get('delay_days', 0),
                })

        return cls._write_workbook('report_deadline', {
            'خلاصه درخواست': request_summary,
            'گروه کالایی درخواست': category_rows,
            'انبار درخواست': warehouse_rows,
            'انحراف درخواست': request_deviated_rows,
            'خلاصه سفارش': order_summary,
            'سفارش کارشناس': order_expert_rows,
            'سفارش گروه کالایی': order_category_rows,
            'جزئیات سفارش کارشناس': order_case_rows,
        })

    @classmethod
    def export_category_amounts(cls, summary: Dict[str, Any], filter_label: str) -> tuple:
        overview = [
            {'شاخص': 'فیلتر دوره', 'مقدار': filter_label},
            {'شاخص': 'جمع کل سفارشات (ریال)', 'مقدار': summary.get('grand_total', 0)},
            {'شاخص': 'کل پرونده‌ها', 'مقدار': summary.get('total_purchases', 0)},
            {'شاخص': 'دارای مبلغ سفارش', 'مقدار': summary.get('with_amount', 0)},
            {'شاخص': 'بدون گروه کالایی', 'مقدار': summary.get('without_category', 0)},
        ]
        category_rows = [
            {
                'گروه کالایی': row.get('name', ''),
                'جمع مبلغ سفارش (ریال)': row.get('amount', 0),
                'سهم (٪)': row.get('share', 0),
                'تعداد پرونده': row.get('purchase_count', 0),
                'دارای مبلغ': row.get('with_amount', 0),
            }
            for row in (summary.get('categories') or [])
        ]
        return cls._write_workbook('report_category_amounts', {
            'خلاصه': overview,
            'گروه کالایی': category_rows,
        })

    @classmethod
    def export_product_amounts(cls, summary: Dict[str, Any], filter_label: str) -> tuple:
        overview = [
            {'شاخص': 'فیلتر دوره', 'مقدار': filter_label},
            {'شاخص': 'جمع کل (ریال)', 'مقدار': summary.get('grand_total', 0)},
            {'شاخص': 'تعداد کالا', 'مقدار': summary.get('product_count', 0)},
            {'شاخص': 'ردیف دارای مبلغ', 'مقدار': summary.get('with_amount', 0)},
            {'شاخص': 'جمع از فاکتور (AJ)', 'مقدار': summary.get('invoice_based_total', 0)},
            {'شاخص': 'جمع از سفارش (AA)', 'مقدار': summary.get('order_based_total', 0)},
        ]
        product_rows = [
            {
                'کد قلم': row.get('product_code', ''),
                'نام کالا': row.get('product_title', ''),
                'جمع مبلغ (ریال)': row.get('amount', 0),
                'سهم (٪)': row.get('share', 0),
                'از فاکتور': row.get('invoice_amount', 0),
                'از سفارش': row.get('order_amount', 0),
                'تعداد ردیف': row.get('line_count', 0),
                'ردیف فاکتور': row.get('invoice_lines', 0),
                'ردیف سفارش': row.get('order_lines', 0),
            }
            for row in (summary.get('products') or [])
        ]
        return cls._write_workbook('report_product_amounts', {
            'خلاصه': overview,
            'کالاها': product_rows,
        })

    @classmethod
    def export_payment_lead(cls, data: Dict[str, Any]) -> tuple:
        overall = data.get('overall') or {}
        summary = [
            {'شاخص': 'فیلتر', 'مقدار': data.get('filter_label', '')},
            {'شاخص': 'بررسی‌شده', 'مقدار': overall.get('evaluated', 0)},
            {'شاخص': 'در مهلت', 'مقدار': overall.get('on_time', 0)},
            {'شاخص': 'انحراف', 'مقدار': overall.get('deviated', 0)},
            {'شاخص': 'نرخ انحراف (٪)', 'مقدار': overall.get('rate', 0)},
            {'شاخص': 'میانگین روز', 'مقدار': overall.get('avg_days')},
            {'شاخص': 'میانه روز', 'مقدار': overall.get('median_days')},
        ]
        bucket_labels = {key: label for key, label, _ in (data.get('day_buckets') or [])}
        category_rows = []
        for row in (data.get('category_stats') or []):
            buckets = row.get('buckets') or {}
            category_rows.append({
                'گروه کالایی': row.get('name', ''),
                'لید تایم مجاز (روز)': row.get('lead_days', 7),
                'بررسی‌شده': row.get('evaluated', 0),
                'در مهلت': row.get('on_time', 0),
                'انحراف': row.get('deviated', 0),
                'نرخ انحراف (٪)': row.get('rate', 0),
                'میانگین روز': row.get('avg_days'),
                'میانه روز': row.get('median_days'),
                'بیشترین روز': row.get('max_days'),
                bucket_labels.get('on_time', 'تا مهلت'): buckets.get('on_time', 0),
                bucket_labels.get('8_14', '۸-۱۴'): buckets.get('8_14', 0),
                bucket_labels.get('15_21', '۱۵-۲۱'): buckets.get('15_21', 0),
                bucket_labels.get('22_plus', '۲۲+'): buckets.get('22_plus', 0),
            })
        deviated_rows = [
            {
                'شماره خرید': row.get('purchase_number', ''),
                'گروه کالایی': row.get('product_category', ''),
                'کارشناس': row.get('expert_name', ''),
                'ثبت واریزی (AP)': row.get('registration_date', ''),
                'انجام واریزی (AQ)': row.get('completion_date', ''),
                'روز واقعی': row.get('actual_days', 0),
                'مهلت (روز)': row.get('lead_days', 7),
                'تأخیر (روز)': row.get('over_days', 0),
            }
            for row in (data.get('recent_deviated') or [])
        ]
        return cls._write_workbook('report_payment_lead', {
            'خلاصه': summary,
            'گروه کالایی': category_rows,
            'انحراف‌ها': deviated_rows,
        })

    @classmethod
    def export_financial_loss(cls, data: Dict[str, Any]) -> tuple:
        overall = data.get('overall') or {}
        summary = [
            {'شاخص': 'فیلتر', 'مقدار': data.get('filter_label', '')},
            {'شاخص': 'بررسی‌شده', 'مقدار': overall.get('evaluated', 0)},
            {'شاخص': 'دارای ضرر', 'مقدار': overall.get('with_loss', 0)},
            {'شاخص': 'بدون ضرر', 'مقدار': (overall.get('on_budget', 0) or 0) + (overall.get('under_budget', 0) or 0)},
            {'شاخص': 'نرخ ضرر (٪)', 'مقدار': overall.get('loss_rate', 0)},
            {'شاخص': 'میانگین درصد افزایش', 'مقدار': overall.get('avg_loss_rate', 0)},
        ]
        expert_rows = [
            {
                'کارشناس': row.get('name', ''),
                'بررسی‌شده': row.get('evaluated', 0),
                'دارای ضرر': row.get('with_loss', 0),
                'نرخ ضرر (٪)': row.get('rate', 0),
            }
            for row in (data.get('expert_stats') or [])
            if row.get('with_loss', 0) > 0
        ]
        category_rows = [
            {
                'گروه کالایی': row.get('name', ''),
                'بررسی‌شده': row.get('evaluated', 0),
                'دارای ضرر': row.get('with_loss', 0),
                'نرخ ضرر (٪)': row.get('rate', 0),
            }
            for row in (data.get('category_stats') or [])
            if row.get('with_loss', 0) > 0
        ]
        case_rows = [
            {
                'شماره خرید': row.get('purchase_number', ''),
                'شماره سفارش': row.get('order_request_number', ''),
                'کالا': row.get('product_title', ''),
                'کارشناس': row.get('expert_name', ''),
                'گروه کالایی': row.get('product_category', ''),
                'جمع سفارش (AC)': row.get('order_total', 0),
                'پیش‌پرداخت (AD)': row.get('advance_payment', 0),
                'درخواست پرداخت (AN)': row.get('payment_request_amount', 0),
                'فاکتور (AL)': row.get('invoice_total', 0),
                'اختلاف (AL−AC)': row.get('loss_amount', 0),
                'افزایش (٪)': row.get('loss_rate', 0),
            }
            for row in (data.get('loss_cases') or [])
        ]
        return cls._write_workbook('report_financial_loss', {
            'خلاصه': summary,
            'کارشناسان': expert_rows,
            'گروه کالایی': category_rows,
            'پرونده‌های ضررده': case_rows,
        })

    @classmethod
    def export_data_quality(cls, validation: Dict[str, Any], sample_size: int, seed: int) -> tuple:
        if validation.get('error'):
            return cls._write_workbook('report_data_quality', {
                'خطا': [{'پیام': validation.get('error', '')}],
            })

        summary = [
            {'شاخص': 'ردیف‌های اکسل', 'مقدار': validation.get('total_excel_rows', 0)},
            {'شاخص': 'نمونه بررسی‌شده', 'مقدار': validation.get('sample_size', sample_size)},
            {'شاخص': 'تأیید شده', 'مقدار': validation.get('passed', 0)},
            {'شاخص': 'مشکل‌دار', 'مقدار': validation.get('failed', 0)},
            {'شاخص': 'seed', 'مقدار': seed},
            {'شاخص': 'فایل', 'مقدار': validation.get('file_path', '')},
        ]

        detail_rows = []
        for row in validation.get('rows', []):
            base = {
                'ردیف اکسل': getattr(row, 'excel_row', row.get('excel_row', '')),
                'شماره خرید': getattr(row, 'purchase_number', row.get('purchase_number', '')),
                'شماره خط': getattr(row, 'line_number', row.get('line_number', '')),
                'عنوان کالا': getattr(row, 'product_title', row.get('product_title', '')),
                'یافت در DB': 'بله' if getattr(row, 'found_in_db', row.get('found_in_db')) else 'خیر',
                'وضعیت': 'تأیید' if getattr(row, 'ok', row.get('ok')) else 'مشکل',
            }
            issues = getattr(row, 'issues', row.get('issues', [])) or []
            mismatches = getattr(row, 'mismatches', row.get('mismatches', [])) or []
            if issues or mismatches:
                for i, issue in enumerate(issues + mismatches):
                    detail = base.copy()
                    detail['مورد'] = i + 1
                    detail['شرح'] = str(issue)
                    detail_rows.append(detail)
            else:
                detail_rows.append({**base, 'مورد': 1, 'شرح': '—'})

        return cls._write_workbook('report_data_quality', {
            'خلاصه': summary,
            'جزئیات نمونه': detail_rows,
        })