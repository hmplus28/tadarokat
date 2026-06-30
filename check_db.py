
import sqlite3

conn = sqlite3.connect('db/db_current.db')
cur = conn.cursor()

# پیدا کردن نام جداول
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
tables = [r[0] for r in cur.fetchall()]
print("جداول دیتابیس:", tables)

# حدس زدن نام جدول اصلی
main_table = tables[0] if tables else None
for t in ['purchases', 'orders', 'items', 'tadarokat', 'data']:
    if t in tables:
        main_table = t
        break

print(f"\nبررسی جدول اصلی: {main_table}")
cur.execute(f"PRAGMA table_info({main_table});")
cols = [r[1] for r in cur.fetchall()]
print("نام ستون‌ها:", cols)

cur.execute(f"SELECT * FROM {main_table};")
all_rows = cur.fetchall()
print(f"تعداد کل ردیف‌ها: {len(all_rows)}")

# پیدا کردن ردیف مورد نظر (کد 600120768)
found = False
for row in all_rows:
    if 600120768 in row or '600120768' in row:
        print("\n✅ داده‌های ذخیره شده در دیتابیس برای کد 600120768:")
        for c, v in zip(cols, row):
            # نمایش بهتر مقادیر خالی
            val = v if v is not None and str(v).strip() != "" else "[خالی]"
            print(f"  {c}: {val}")
        found = True
        break

if not found:
    print("\n❌ کد 600120768 پیدا نشد. نمایش ۲ ردیف اول برای بررسی ساختار:")
    for row in all_rows[:2]:
        print("\nردیف:")
        for c, v in zip(cols, row):
            val = v if v is not None and str(v).strip() != "" else "[خالی]"
            print(f"  {c}: {val}")

conn.close()