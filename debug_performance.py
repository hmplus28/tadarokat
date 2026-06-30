import sys
import time
sys.path.insert(0, 'backend')

from services import excel_service, local_storage

print("=== تست ۱: زمان اجرای _get_merged_purchases ===")
start = time.time()
df = excel_service._get_merged_purchases()
elapsed = time.time() - start
print(f"زمان: {elapsed:.2f} ثانیه")
print(f"تعداد ردیف‌ها: {len(df)}")

print("\n=== تست ۲: بررسی داده‌های تحویل در اکسل ===")
if "شماره تحویل" in df.columns:
    has_delivery = df["شماره تحویل"].notna() & (df["شماره تحویل"].astype(str).str.strip() != "")
    print(f"تعداد ردیف‌های دارای شماره تحویل: {has_delivery.sum()}")
    if has_delivery.any():
        sample = df[has_delivery].head(3)
        for _, row in sample.iterrows():
            print(f"  - خرید {row.get('شماره')}: تحویل {row.get('شماره تحویل')} در {row.get('تاریخ تحویل')}")

print("\n=== تست ۳: بررسی داده‌های دستور خرید در اکسل ===")
if "شماره دستور خرید" in df.columns:
    has_order = df["شماره دستور خرید"].notna() & (df["شماره دستور خرید"].astype(str).str.strip() != "")
    print(f"تعداد ردیف‌های دارای شماره دستور خرید: {has_order.sum()}")
    if has_order.any():
        sample = df[has_order].head(3)
        for _, row in sample.iterrows():
            print(f"  - خرید {row.get('شماره')}: دستور {row.get('شماره دستور خرید')} در {row.get('تاریخ دستور خرید')}")

print("\n=== تست ۴: زمان اجرای list_deliveries ===")
start = time.time()
deliveries = local_storage.get_deliveries()
elapsed = time.time() - start
print(f"زمان get_deliveries: {elapsed:.2f} ثانیه")
print(f"تعداد تحویل‌ها در local_storage: {len(deliveries)}")

print("\n=== تست ۵: زمان اجرای list_orders ===")
start = time.time()
orders = local_storage.get_orders()
elapsed = time.time() - start
print(f"زمان get_orders: {elapsed:.2f} ثانیه")
print(f"تعداد دستور خریدها در local_storage: {len(orders)}")

print("\n=== تست ۶: بررسی sync_deliveries_from_excel ===")
start = time.time()
count = excel_service.sync_deliveries_from_excel("test")
elapsed = time.time() - start
print(f"زمان sync_deliveries_from_excel: {elapsed:.2f} ثانیه")
print(f"تعداد تحویل‌های sync شده: {count}")