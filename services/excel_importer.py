import gc
import io
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from services.excel_import_progress import ExcelImportProgress

User = get_user_model()


class ExcelImportError(Exception):
    """خطای واردسازی اکسل — برای rollback اتمیک."""

    def __init__(self, message: str, errors: Optional[list] = None):
        super().__init__(message)
        self.errors = errors or []


class ExcelImporter:
    IMPORT_BATCH_SIZE = 250
    STATUS_BATCH_SIZE = 500

    """
    سرویس import و sync هوشمند داده‌ها از اکسل
    
    استراتژی: UPSERT
    - رکوردهای جدید اضافه می‌شوند
    - رکوردهای موجود به‌روز می‌شوند (با حفظ فیلدهای workflow)
    - تحویل‌ها به صورت خودکار در جدول Deliveries sync می‌شوند
    - استعلام‌های اکسل به جدول Inquiry sync می‌شوند
    - وضعیت current_status برای همه رکوردها مجدداً محاسبه می‌شود
    """

    @classmethod
    def sync_inquiries_from_purchases(cls) -> Dict:
        """
        ایجاد رکورد Inquiry برای خریدهایی که شماره استعلام در اکسل دارند
        ولی هنوز در جدول استعلام‌ها ثبت نشده‌اند.
        """
        from purchases.models import Purchase
        from inquiries.models import Inquiry
        from django.db import IntegrityError

        stats = {
            'inquiries_created': 0,
            'inquiries_skipped': 0,
            'inquiries_errors': [],
        }

        purchases_with_inquiry = (
            Purchase.objects
            .exclude(inquiry_number='')
            .exclude(inquiry_number__isnull=True)
            .order_by('purchase_number', 'line_number', 'id')
        )

        inquiry_primary = {}
        for purchase in purchases_with_inquiry:
            inquiry_number = cls.clean_value(purchase.inquiry_number)
            if not inquiry_number:
                continue
            if inquiry_number not in inquiry_primary:
                inquiry_primary[inquiry_number] = purchase

        for inquiry_number, purchase in inquiry_primary.items():
            if Inquiry.objects.filter(inquiry_number=inquiry_number).exists():
                stats['inquiries_skipped'] += 1
                continue

            try:
                Inquiry.objects.create(
                    inquiry_number=inquiry_number,
                    purchase=purchase,
                    inquiry_date=(
                        purchase.inquiry_received_date
                        or purchase.purchase_date
                        or purchase.request_date
                        or ''
                    ),
                    deadline=purchase.inquiry_deadline or purchase.inquiry_deadline_2 or '',
                    purchase_type=purchase.purchase_type or '',
                    supply_unit=purchase.supply_unit or '',
                    product_category=purchase.product_category or '',
                    warehouse_request_number=purchase.base_number or '',
                    warehouse_request_date=purchase.request_date or '',
                    requester=purchase.requester or '',
                    expert_name=purchase.expert_name or '',
                    issuer='همگام‌سازی اکسل',
                    status=Inquiry.Status.ISSUED,
                    created_by=None,
                )
                stats['inquiries_created'] += 1
            except IntegrityError:
                stats['inquiries_skipped'] += 1
            except Exception as e:
                stats['inquiries_errors'].append(
                    f"Inquiry {inquiry_number} (Purchase {purchase.purchase_number}): {e}"
                )

        return stats

    @classmethod
    def _order_stage_from_purchase(cls, purchase) -> str:
        """تعیین مرحله دستور خرید بر اساس فیلدهای پرونده خرید"""
        from purchases.models import is_valid_value, is_real_date, is_tankhah
        from orders.models import Order

        if is_valid_value(purchase.delivery_number) or is_real_date(purchase.delivery_date):
            return Order.Stage.DELIVERED

        if is_real_date(purchase.payment_completion_date):
            return Order.Stage.PAYMENT
        if is_tankhah(purchase.payment_request_number) or is_tankhah(purchase.payment_registration_date):
            return Order.Stage.PAYMENT

        if is_valid_value(purchase.order_request_number):
            return Order.Stage.ORDER_PLACED

        return Order.Stage.ORDER_ISSUED

    @staticmethod
    def _order_status_from_stage(stage: str) -> str:
        from orders.models import Order
        return {
            Order.Stage.DELIVERED: 'تحویل شده',
            Order.Stage.PAYMENT: 'پرداخت شده',
            Order.Stage.ORDER_PLACED: 'سفارش داده شده',
            Order.Stage.ORDER_ISSUED: 'جاری',
        }.get(stage, 'جاری')

    @classmethod
    def sync_orders_from_purchases(cls) -> Dict:
        """
        ایجاد رکورد Order برای خریدهایی که شماره دستور در اکسل دارند
        ولی هنوز در جدول دستورات ثبت نشده‌اند.
        """
        from purchases.models import Purchase, is_valid_value
        from orders.models import Order
        from inquiries.models import Inquiry
        from django.db import IntegrityError

        stats = {
            'orders_created': 0,
            'orders_skipped': 0,
            'orders_errors': [],
        }

        purchases_with_order = (
            Purchase.objects
            .exclude(order_number='')
            .exclude(order_number__isnull=True)
            .order_by('purchase_number', 'line_number', 'id')
        )

        order_primary = {}
        for purchase in purchases_with_order:
            order_number = cls.clean_value(purchase.order_number)
            if not order_number or not is_valid_value(order_number):
                continue
            if order_number not in order_primary:
                order_primary[order_number] = purchase

        for order_number, purchase in order_primary.items():
            if Order.objects.filter(order_number=order_number).exists():
                stats['orders_skipped'] += 1
                continue

            inquiry = None
            inquiry_number = cls.clean_value(purchase.inquiry_number)
            if inquiry_number and is_valid_value(inquiry_number):
                inquiry = Inquiry.objects.filter(inquiry_number=inquiry_number).first()

            qty = cls.clean_decimal(purchase.quantity)
            unit_price = cls.clean_decimal(purchase.preinvoice_price or purchase.invoice_price)
            total_price = cls.clean_decimal(purchase.order_total)
            if total_price == 0 and qty and unit_price:
                total_price = qty * unit_price

            stage = cls._order_stage_from_purchase(purchase)

            def _safe_str(val):
                cleaned = cls.clean_value(val)
                return cleaned if cleaned and is_valid_value(cleaned) else ''

            try:
                Order.objects.create(
                    order_number=order_number,
                    inquiry=inquiry,
                    purchase=purchase,
                    product_title=purchase.product_title or '',
                    product_code=purchase.product_code or '',
                    quantity=qty,
                    unit=purchase.unit or '',
                    unit_price=unit_price,
                    total_price=total_price,
                    contractor=_safe_str(purchase.supplier),
                    warehouse=purchase.supply_unit or '',
                    expert_name=purchase.expert_name or '',
                    stage=stage,
                    status=cls._order_status_from_stage(stage),
                    order_date=_safe_str(purchase.order_date) or _safe_str(purchase.purchase_date) or '',
                    order_request_date=_safe_str(purchase.order_request_date),
                    order_request_number=_safe_str(purchase.order_request_number),
                    payment_date=_safe_str(purchase.payment_completion_date) or _safe_str(purchase.payment_registration_date),
                    payment_number=_safe_str(purchase.payment_request_number),
                    delivery_date=_safe_str(purchase.delivery_date),
                    delivery_number=_safe_str(purchase.delivery_number),
                    description='همگام‌سازی اکسل',
                    issued_by='همگام‌سازی اکسل',
                    created_by=None,
                )
                stats['orders_created'] += 1
            except IntegrityError:
                stats['orders_skipped'] += 1
            except Exception as e:
                stats['orders_errors'].append(
                    f"Order {order_number} (Purchase {purchase.purchase_number}): {e}"
                )

        return stats
    
    # نگاشت ستون‌های اکسل به فیلدهای مدل
    COLUMN_MAP = {
        'شماره درخواست خرید': 'purchase_number',
        'شماره درخواست کالا': 'base_number',
        'تاریخ درخواست کالا': 'request_date',
        'تاریخ درخواست': 'purchase_date',
        'واحد تامین': 'supply_unit',
        'گروه بندی کالایی': 'product_category',
        'گروه‌بندی کالایی': 'product_category',
        'درخواست کننده': 'requester',
        'کد قلم خریدنی': 'product_code',
        'نام قلم خریدنی': 'product_title',
        'واحد سنجش': 'unit',
        'مقدار درخواست': 'quantity',
        'نام کارشناس خرید': 'expert_name',
        'توضیحات درخواست خرید': 'description',
        'وضعیت درخواست خرید': 'status',
        'تاریخ نیاز درخواست خرید': 'required_date',
        'مهلت استعلام': 'inquiry_deadline',
        'مهلت استعلام 2': 'inquiry_deadline_2',
        'شماره استعلام': 'inquiry_number',
        'تاریخ دریافت درخواست': 'inquiry_received_date',
        'روند خرید': 'purchase_type',
        'شماره پیش فاکتور': 'preinvoice_number',
        'فی پیش فاکتور': 'preinvoice_price',
        'جمع پیش فاکتور بدون ارزش افزوده': 'preinvoice_total',
        'شماره دستور خرید': 'order_number',
        'تاریخ دستور خرید': 'order_date',
        'شماره سفارش': 'order_request_number',
        'وضعیت سفارش': 'order_request_status',
        'تاریخ سفارش': 'order_request_date',
        'جمع کل سفارش': 'order_total',
        'مبلغ پیش پرداخت': 'advance_payment',
        'کسور': 'deductions',
        'مقدار تحویل': 'delivered_quantity',
        'شماره تحویل': 'delivery_number',
        'تاریخ تحویل': 'delivery_date',
        'تامین کننده': 'supplier',
        'فی فاکتور': 'invoice_price',
        'شماره فاکتور': 'invoice_number',
        'جمع کل فاکتور': 'invoice_total',
        'مبلغ درخواست پرداخت': 'payment_request_amount',
        'شماره درخواست پرداخت': 'payment_request_number',
        'تاریخ ثبت واریزی': 'payment_registration_date',
        'تاریخ انجام واریزی': 'payment_completion_date',
        'انحراف مهلت': '_deadline_deviated_label',
        'انحراف مهلت سفارش': '_order_deadline_deviated_label',
    }

    ALWAYS_EXPORT_TEXT_FIELDS = frozenset({'product_category'})

    EXTRA_EXPORT_COLUMNS = {
        'product_category': 'گروه بندی کالایی',
        '_deadline_deviated_label': 'انحراف مهلت',
        '_order_deadline_deviated_label': 'انحراف مهلت سفارش',
        '_payment_lead_deviated_label': 'انحراف لید تایم پرداخت',
        '_current_status_label': 'وضعیت فعلی پنل',
    }
    
    # فیلدهای عددی (Decimal)
    DECIMAL_FIELDS = {
        'quantity', 'preinvoice_price', 'preinvoice_total',
        'order_total', 'advance_payment', 'deductions',
        'delivered_quantity', 'invoice_price', 'invoice_total',
        'payment_request_amount'
    }
    
    # فیلدهای workflow که باید با احتیاط sync شوند
    WORKFLOW_FIELDS = {
        'inquiry_number', 'order_number', 'order_date', 
        'delivery_number', 'delivery_date'
    }
    
    @staticmethod
    def clean_value(val) -> Optional[str]:
        """پاکسازی مقادیر متنی از Excel"""
        if val is None:
            return None
        if pd.isna(val):
            return None
        s = str(val).strip()
        if not s or s.lower() in ('nan', 'none', 'null', '#n/a', '#n/a!', '#ref!', '#value!', '#div/0!', '-'):
            return None
        # حذف .0 از اعداد float
        if s.endswith('.0') and s[:-2].replace('-', '').replace('.', '').isdigit():
            s = s[:-2]
        return s
    
    @staticmethod
    def clean_decimal(val) -> Decimal:
        """تبدیل مقادیر به Decimal با پشتیبانی از اعداد فارسی"""
        if val is None or pd.isna(val):
            return Decimal('0')
        try:
            s = str(val).strip().replace(',', '').replace(' ', '')
            if not s or s.lower() in ('nan', 'none', 'null', '-', '#n/a', '#n/a!'):
                return Decimal('0')
            # تبدیل اعداد فارسی به انگلیسی
            persian_digits = '۰۱۲۳۴۵۶۷۸۹'
            english_digits = '0123456789'
            for p, e in zip(persian_digits, english_digits):
                s = s.replace(p, e)
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return Decimal('0')
    
    @classmethod
    def normalize_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """نرمال‌سازی نام ستون‌ها"""
        df = df.copy()
        df.columns = [
            ' '.join(str(c).replace('\n', ' ').replace('\r', ' ').split()).strip() 
            for c in df.columns
        ]
        return df
    
    COLUMN_ALIASES = {
        'شماره درخواست کالا از انبار': 'base_number',
        'تاریخ ثبت کالا از انبار': 'request_date',
    }

    IMPORT_REQUIRED_FIELDS = {'purchase_number'}

    @classmethod
    def get_import_columns(cls) -> list[tuple[str, str]]:
        """
        ستون‌های ورودی اکسل — یک عنوان کاننیکال برای هر فیلد مدل.
        منبع واحد برای قالب دانلودی و import.
        """
        seen: set[str] = set()
        columns: list[tuple[str, str]] = []
        for excel_col, model_field in cls.COLUMN_MAP.items():
            if model_field.startswith('_'):
                continue
            if model_field in seen:
                continue
            seen.add(model_field)
            columns.append((excel_col, model_field))
        return columns

    @classmethod
    def get_export_columns(cls) -> list[tuple[str, str]]:
        """
        ستون‌های خروجی اکسل — همان ورودی به‌علاوه فیلدهای محاسبه‌شده پنل.
        منبع واحد برای export پس از آپلود و خروجی کامل دیتابیس.
        """
        columns = list(cls.get_import_columns())
        import_fields = {field for _, field in columns}
        for field, header in cls.EXTRA_EXPORT_COLUMNS.items():
            if field not in import_fields:
                columns.append((header, field))
        return columns

    @classmethod
    def get_import_aliases_for_field(cls, model_field: str) -> list[str]:
        aliases = [
            col for col, field in cls.COLUMN_ALIASES.items()
            if field == model_field
        ]
        alt_headers = [
            col for col, field in cls.COLUMN_MAP.items()
            if field == model_field
        ][1:]
        return aliases + alt_headers

    @classmethod
    def map_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        """نگاشت ستون‌های اکسل به فیلدهای مدل"""
        df = df.copy()
        for alias_col, target_field in cls.COLUMN_ALIASES.items():
            if alias_col in df.columns:
                if target_field not in df.columns:
                    df[target_field] = df[alias_col]
                else:
                    df[target_field] = df[target_field].where(
                        df[target_field].notna() & (df[target_field].astype(str).str.strip() != ''),
                        df[alias_col],
                    )

        rename_map = {}
        for excel_col, model_field in cls.COLUMN_MAP.items():
            if excel_col in df.columns:
                rename_map[excel_col] = model_field
        return df.rename(columns=rename_map)
    
    @classmethod
    def _raise_if_fail_on_errors(cls, stats: Dict, phase_label: str) -> None:
        if not stats.get('_fail_on_errors'):
            return
        if stats['errors']:
            raise ExcelImportError(
                f'خطا در {phase_label} — هیچ تغییری ذخیره نشد',
                errors=stats['errors'],
            )

    @classmethod
    def import_from_excel(
        cls,
        file_path: str,
        user: Optional[User] = None,
        full_sync: bool = False,
        fail_on_errors: bool = False,
        export_path: Optional[str] = None,
        progress: Optional['ExcelImportProgress'] = None,
    ) -> Dict:
        """
        import/sync هوشمند داده‌ها از اکسل

        Args:
            file_path: مسیر فایل اکسل ورودی (فقط خواندنی)
            user: کاربری که sync را انجام می‌دهد
            full_sync: اگر True باشد، همه فیلدها بازنویسی می‌شوند (خطرناک!)
            fail_on_errors: اگر True باشد، هر خطا باعث rollback کامل می‌شود
            export_path: مسیر جدا برای اکسل خروجی (جلوگیری از قفل فایل در ویندوز)
            progress: ردیاب پیشرفت اختیاری برای UI
        """
        from purchases.models import Purchase

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        export_target = Path(export_path) if export_path else file_path

        def _progress(phase: str, message: str = '', sub_percent: float = 0.0) -> None:
            if progress:
                progress.set_phase(phase, message, sub_percent)

        from services.excel_file_utils import read_file_bytes

        print(f"[INFO] Reading Excel: {file_path}")
        _progress('reading', 'در حال خواندن فایل اکسل...')
        file_bytes = read_file_bytes(file_path)
        df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=0, engine='openpyxl')

        df = cls.normalize_columns(df)
        df = cls.map_columns(df)

        from services.product_category_service import ProductCategoryService
        categories_created = 0
        _progress('categories', 'ثبت گروه‌های کالایی...')
        if 'product_category' in df.columns:
            category_names = [
                cls.clean_value(value)
                for value in df['product_category'].dropna()
                if cls.clean_value(value)
            ]
            categories_created = ProductCategoryService.ensure_categories(category_names)
        
        if 'purchase_number' not in df.columns:
            raise ValueError("ستون 'شماره درخواست خرید' در اکسل یافت نشد")
        
        print(f"[INFO] Total rows in Excel: {len(df)}")
        print(f"[INFO] Sync mode: {'FULL (dangerous)' if full_sync else 'SMART (preserve workflow)'}")
        if categories_created:
            print(f"[INFO] Product categories created: {categories_created}")
        
        stats = {
            'total_rows': len(df),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'workflow_preserved': 0,
            'categories_created': categories_created,
            'errors': [],
            'seen_keys': set(),
            '_fail_on_errors': fail_on_errors,
        }

        line_counters = {}
        row_items = list(df.iterrows())
        total_rows = max(len(row_items), 1)

        _progress('importing', f'شروع واردسازی {len(row_items)} ردیف...')

        # ============================================
        # PHASES 1–5: همه تغییرات DB در یک تراکنش اتمیک
        # ============================================
        with transaction.atomic():
            for batch_start in range(0, len(row_items), cls.IMPORT_BATCH_SIZE):
                batch = row_items[batch_start:batch_start + cls.IMPORT_BATCH_SIZE]
                for idx, row in batch:
                    try:
                        purchase_number = cls.clean_value(row.get('purchase_number'))
                        if not purchase_number:
                            stats['skipped'] += 1
                            continue

                        if purchase_number not in line_counters:
                            line_counters[purchase_number] = 0
                        line_counters[purchase_number] += 1
                        line_number = line_counters[purchase_number]

                        unique_key = f"{purchase_number}_{line_number}"
                        stats['seen_keys'].add(unique_key)

                        data = {}
                        for excel_col, model_field in cls.COLUMN_MAP.items():
                            if model_field in row.index:
                                val = row[model_field]
                                if model_field in cls.DECIMAL_FIELDS:
                                    data[model_field] = cls.clean_decimal(val)
                                else:
                                    cleaned = cls.clean_value(val)
                                    data[model_field] = cleaned if cleaned is not None else ""

                        from services.monetary_service import MonetaryService
                        MonetaryService.normalize_purchase_data(data)

                        existing = Purchase.objects.filter(
                            purchase_number=purchase_number,
                            line_number=line_number
                        ).first()

                        if existing:
                            if not full_sync:
                                from purchases.models import is_valid_value
                                for wf_field in cls.WORKFLOW_FIELDS:
                                    current_val = getattr(existing, wf_field, '')
                                    if current_val and str(current_val).strip() and is_valid_value(current_val):
                                        data.pop(wf_field, None)
                                        stats['workflow_preserved'] += 1

                            for key, value in data.items():
                                setattr(existing, key, value)
                            if user:
                                existing.imported_by = user
                            existing.save()
                            stats['updated'] += 1
                        else:
                            data['purchase_number'] = purchase_number
                            data['line_number'] = line_number
                            if user:
                                data['imported_by'] = user
                            Purchase.objects.create(**data)
                            stats['created'] += 1

                        processed = stats['created'] + stats['updated'] + stats['skipped']
                        if processed % 50 == 0 or processed == total_rows:
                            _progress(
                                'importing',
                                f'ردیف {processed} از {total_rows}',
                                processed / total_rows,
                            )

                        if (stats['created'] + stats['updated']) % 1000 == 0:
                            print(f"[INFO] Processed {stats['created'] + stats['updated']} rows...")

                    except Exception as e:
                        err_msg = f"Row {idx} (Purchase {row.get('purchase_number', '?')}): {str(e)}"
                        if fail_on_errors:
                            raise ExcelImportError(err_msg, errors=[err_msg]) from e
                        stats['errors'].append(err_msg)
                        stats['skipped'] += 1

            cls._raise_if_fail_on_errors(stats, 'واردسازی ردیف‌ها')

            _progress('syncing_inquiries', 'همگام‌سازی استعلام‌ها...')
            print("[INFO] Syncing inquiries from purchases...")
            inquiry_stats = cls.sync_inquiries_from_purchases()
            stats['inquiries_created'] = inquiry_stats['inquiries_created']
            stats['inquiries_skipped'] = inquiry_stats['inquiries_skipped']
            stats['errors'].extend(inquiry_stats['inquiries_errors'])
            cls._raise_if_fail_on_errors(stats, 'همگام‌سازی استعلام‌ها')
            print(
                f"[INFO] Inquiries synced: {inquiry_stats['inquiries_created']} created, "
                f"{inquiry_stats['inquiries_skipped']} skipped"
            )

            _progress('syncing_orders', 'همگام‌سازی دستورات خرید...')
            print("[INFO] Syncing orders from purchases...")
            order_stats = cls.sync_orders_from_purchases()
            stats['orders_created'] = order_stats['orders_created']
            stats['orders_skipped'] = order_stats['orders_skipped']
            stats['errors'].extend(order_stats['orders_errors'])
            cls._raise_if_fail_on_errors(stats, 'همگام‌سازی دستورات')
            print(
                f"[INFO] Orders synced: {order_stats['orders_created']} created, "
                f"{order_stats['orders_skipped']} skipped"
            )

            _progress('syncing_deliveries', 'همگام‌سازی تحویل‌ها...')
            print("[INFO] Syncing deliveries from purchases...")
            from deliveries.models import Delivery
            from orders.models import Order
            from django.db import IntegrityError

            purchases_with_delivery = Purchase.objects.exclude(
                delivery_number=''
            ).exclude(
                delivery_number__isnull=True
            )

            deliveries_created = 0
            deliveries_skipped = 0

            for purchase in purchases_with_delivery:
                delivery_number = (purchase.delivery_number or '').strip()
                if not delivery_number:
                    deliveries_skipped += 1
                    continue

                if Delivery.objects.filter(delivery_number=delivery_number).exists():
                    deliveries_skipped += 1
                    continue

                order = None
                if purchase.order_number:
                    order = Order.objects.filter(order_number=purchase.order_number).first()

                try:
                    Delivery.objects.create(
                        delivery_number=delivery_number,
                        order=order,
                        purchase=purchase,
                        product_title=purchase.product_title or '',
                        quantity=purchase.delivered_quantity or purchase.quantity or 0,
                        unit=purchase.unit or '',
                        warehouse=purchase.supply_unit or '',
                        receiver='',
                        delivery_date=purchase.delivery_date or '',
                        supplier=purchase.supplier or '',
                        description='',
                    )
                    deliveries_created += 1
                except IntegrityError:
                    deliveries_skipped += 1
                    stats['errors'].append(
                        f"Delivery {delivery_number} (Purchase {purchase.purchase_number}): duplicate"
                    )

            print(f"[INFO] Deliveries synced: {deliveries_created} created, {deliveries_skipped} skipped")
            stats['deliveries_created'] = deliveries_created
            stats['deliveries_skipped'] = deliveries_skipped
            cls._raise_if_fail_on_errors(stats, 'همگام‌سازی تحویل‌ها')

            _progress('recalculating_status', 'محاسبه مجدد وضعیت‌ها...')
            print("[INFO] Recalculating current_status for all purchases...")
            status_updated = 0
            status_unchanged = 0

            purchase_ids = list(Purchase.objects.values_list('pk', flat=True))
            status_total = max(len(purchase_ids), 1)
            for batch_start in range(0, len(purchase_ids), cls.STATUS_BATCH_SIZE):
                batch_ids = purchase_ids[batch_start:batch_start + cls.STATUS_BATCH_SIZE]
                for purchase in Purchase.objects.filter(pk__in=batch_ids):
                    old_status = purchase.current_status
                    new_status = purchase.calculate_current_status()

                    if old_status != new_status:
                        Purchase.objects.filter(pk=purchase.pk).update(current_status=new_status)
                        status_updated += 1
                    else:
                        status_unchanged += 1
                done = min(batch_start + cls.STATUS_BATCH_SIZE, len(purchase_ids))
                _progress('recalculating_status', f'وضعیت {done} از {len(purchase_ids)}', done / status_total)

            print(f"[INFO] Status recalculated: {status_updated} updated, {status_unchanged} unchanged")
            stats['status_updated'] = status_updated
            stats['status_unchanged'] = status_unchanged

            _progress('refreshing_deadlines', 'به‌روزرسانی انحراف مهلت...')
            from services.deadline_service import DeadlineService
            from services.order_deadline_service import OrderDeadlineService
            from services.payment_lead_service import PaymentLeadService
            dl_stats = DeadlineService.refresh_all_categories_and_deadlines()
            order_dl_updated = OrderDeadlineService.recalculate_all()
            payment_lead_updated = PaymentLeadService.recalculate_all()
            dl_stats['order_deadline_updated'] = order_dl_updated
            dl_stats['payment_lead_updated'] = payment_lead_updated
            stats['deadline_refresh'] = dl_stats
            stats['deadline_deviated_updated'] = dl_stats.get('deadline_updated', 0)
            stats['order_deadline_deviated_updated'] = order_dl_updated
            stats['payment_lead_deviated_updated'] = payment_lead_updated
            synced_categories = ProductCategoryService.sync_from_purchases()
            stats['categories_synced'] = synced_categories
            print(
                f"[INFO] Deadline refresh: inquiries={dl_stats.get('from_inquiries', 0)}, "
                f"prefix={dl_stats.get('from_code_prefix', 0)}, "
                f"request_deviations={dl_stats.get('deadline_updated', 0)}, "
                f"order_deviations={order_dl_updated}, "
                f"payment_lead_deviations={payment_lead_updated}"
            )

        stats.pop('_fail_on_errors', None)
        stats['seen_keys_count'] = len(stats.pop('seen_keys'))

        print(f"[OK] Sync completed:")
        print(f"  - Created: {stats['created']}")
        print(f"  - Updated: {stats['updated']}")
        print(f"  - Workflow fields preserved: {stats['workflow_preserved']}")
        print(f"  - Skipped: {stats['skipped']}")
        print(f"  - Errors: {len(stats['errors'])}")
        print(f"  - Deliveries Created: {stats.get('deliveries_created', 0)}")
        print(f"  - Deliveries Skipped: {stats.get('deliveries_skipped', 0)}")
        print(f"  - Status Updated: {stats.get('status_updated', 0)}")

        if stats['errors']:
            print(f"\n[WARN] First 10 errors:")
            for err in stats['errors'][:10]:
                print(f"  ⚠️ {err}")

        if export_target != file_path:
            try:
                file_path.unlink(missing_ok=True)
            except OSError:
                pass

        _progress('exporting', 'تولید اکسل غنی‌شده...')
        gc.collect()
        try:
            export_stats = cls.export_to_excel(
                str(export_target),
                source_bytes=file_bytes,
            )
        except OSError as exc:
            if 'WinError 32' in str(exc) or getattr(exc, 'winerror', None) == 32:
                raise OSError(
                    f'ذخیره اکسل خروجی ناموفق بود (فایل قفل است): {exc}'
                ) from exc
            raise
        stats['excel_export'] = export_stats
        print(
            f"[INFO] Excel export: {export_stats.get('rows_updated', 0)} updated, "
            f"{export_stats.get('rows_appended', 0)} appended"
        )

        return stats

    @classmethod
    def _normalize_header(cls, value) -> str:
        return ' '.join(str(value or '').replace('\n', ' ').replace('\r', ' ').split()).strip()

    @classmethod
    def _field_export_value(cls, purchase, field: str):
        from purchases.models import is_valid_value

        if field == '_deadline_deviated_label':
            return 'بله' if purchase.deadline_deviated else 'خیر'
        if field == '_order_deadline_deviated_label':
            return 'بله' if purchase.order_deadline_deviated else 'خیر'
        if field == '_payment_lead_deviated_label':
            return 'بله' if purchase.payment_lead_deviated else 'خیر'
        if field == '_current_status_label':
            return purchase.current_status_fa
        if field in cls.ALWAYS_EXPORT_TEXT_FIELDS:
            return cls.clean_value(getattr(purchase, field, None))

        val = getattr(purchase, field, None)
        if field in cls.DECIMAL_FIELDS:
            if val is None or val == 0:
                return None
            return float(val)
        if val is None:
            return None
        cleaned = cls.clean_value(val)
        if cleaned is None:
            return None
        if field in cls.WORKFLOW_FIELDS:
            return cleaned
        if not is_valid_value(cleaned):
            return None
        return cleaned

    @classmethod
    def export_to_excel(
        cls,
        file_path: str,
        source_path: Optional[str] = None,
        source_bytes: Optional[bytes] = None,
    ) -> Dict:
        """نوشتن داده‌های پنل (جدید و به‌روز) به فایل اکسل"""
        from purchases.models import Purchase
        from services.excel_file_utils import (
            load_workbook_from_bytes,
            read_file_bytes,
            safe_save_workbook,
        )

        file_path = Path(file_path)

        if source_bytes is not None:
            wb = load_workbook_from_bytes(source_bytes)
        elif source_path:
            wb = load_workbook_from_bytes(read_file_bytes(source_path))
        elif file_path.exists():
            wb = load_workbook_from_bytes(read_file_bytes(file_path))
        else:
            raise FileNotFoundError(f"File not found: {file_path}")
        ws = wb.active

        col_map = {}
        for col_idx, cell in enumerate(ws[1], start=1):
            hdr = cls._normalize_header(cell.value)
            if hdr in cls.COLUMN_MAP:
                field = cls.COLUMN_MAP[hdr]
                col_map.setdefault(field, col_idx)

        for field, header in cls.EXTRA_EXPORT_COLUMNS.items():
            if field not in col_map:
                new_col = ws.max_column + 1
                ws.cell(row=1, column=new_col, value=header)
                col_map[field] = new_col

        purchase_col = col_map.get('purchase_number')
        if not purchase_col:
            raise ValueError("ستون 'شماره درخواست خرید' در اکسل یافت نشد")

        purchase_by_key = {}
        for purchase in Purchase.objects.all().order_by('purchase_number', 'line_number', 'id'):
            key = f"{purchase.purchase_number}_{purchase.line_number}"
            purchase_by_key[key] = purchase

        stats = {'rows_updated': 0, 'rows_appended': 0, 'errors': []}
        line_counters = {}
        seen_keys = set()

        export_fields = set(col_map.keys()) - {'purchase_number'}

        for row_idx in range(2, ws.max_row + 1):
            try:
                purchase_number = cls.clean_value(ws.cell(row=row_idx, column=purchase_col).value)
                if not purchase_number:
                    continue

                line_counters.setdefault(purchase_number, 0)
                line_counters[purchase_number] += 1
                key = f"{purchase_number}_{line_counters[purchase_number]}"
                seen_keys.add(key)

                purchase = purchase_by_key.get(key)
                if not purchase:
                    continue

                for field in export_fields:
                    col_idx = col_map.get(field)
                    if not col_idx:
                        continue
                    val = cls._field_export_value(purchase, field)
                    if field in cls.ALWAYS_EXPORT_TEXT_FIELDS or (val is not None and val != ''):
                        ws.cell(row=row_idx, column=col_idx, value=val or '')

                stats['rows_updated'] += 1
            except Exception as e:
                stats['errors'].append(f"Row {row_idx}: {e}")

        for key, purchase in purchase_by_key.items():
            if key in seen_keys:
                continue
            row_idx = ws.max_row + 1
            try:
                for field, col_idx in col_map.items():
                    if field == 'purchase_number':
                        ws.cell(row=row_idx, column=col_idx, value=purchase.purchase_number)
                        continue
                    val = cls._field_export_value(purchase, field)
                    if field in cls.ALWAYS_EXPORT_TEXT_FIELDS or (val is not None and val != ''):
                        ws.cell(row=row_idx, column=col_idx, value=val or '')
                stats['rows_appended'] += 1
            except Exception as e:
                stats['errors'].append(f"Append {key}: {e}")

        written_path = safe_save_workbook(wb, file_path)
        stats['output_path'] = str(written_path)

        return stats