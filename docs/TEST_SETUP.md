# راهنمای نصب و تست سریع (یک کلیک)

این سند مخصوص **تست لوکال** سامانه تدارکات است — بدون تنظیم دستی share، seed کاربران، یا import اکسل.

| مورد | مقدار |
|------|--------|
| **اسکریپت ویندوز** | `test_run.bat` |
| **اسکریپت اصلی** | `scripts/test_setup.py` |
| **کاربران تست** | `share_users.test.seed.json` |
| **آدرس پیش‌فرض** | http://127.0.0.1:8000 |

> **تفاوت با نصب واقعی:** `test_run.bat` برای آزمایش است. برای استقرار روی چند PC یا share شبکه از [README](../README.md) (گام‌های ۳ تا ۸) و [راهنمای استقرار](DEPLOYMENT.md) استفاده کنید.

---

## فهرست

1. [این راهنما برای چه کسی است؟](#۱-این-راهنما-برای-چه-کسی-است)
2. [پیش‌نیازها](#۲-پیش‌نیازها)
3. [دریافت پروژه](#۳-دریافت-پروژه)
4. [آماده‌سازی فایل اکسل](#۴-آماده‌سازی-فایل-اکسل)
5. [ساختار پوشه در حالت تست](#۵-ساختار-پوشه-در-حالت-تست)
6. [اجرای تست — ویندوز (یک کلیک)](#۶-اجرای-تست--ویندوز-یک-کلیک)
7. [اجرای تست — لینوکس یا خط فرمان](#۷-اجرای-تست--لینوکس-یا-خط-فرمان)
8. [مراحل داخلی اسکریپت](#۸-مراحل-داخلی-اسکریپت)
9. [کاربران و نقش‌های تست](#۹-کاربران-و-نقش‌های-تست)
10. [ورود به سامانه و تست UI](#۱۰-ورود-به-سامانه-و-تست-ui)
11. [گزینه‌های پیشرفته خط فرمان](#۱۱-گزینه‌های-پیشرفته-خط-فرمان)
12. [خروجی موفق چگونه است؟](#۱۲-خروجی-موفق-چگونه-است)
13. [مشکلات رایج](#۱۳-مشکلات-رایج)
14. [بازگشت به حالت نصب واقعی (Production)](#۱۴-بازگشت-به-حالت-نصب-واقعی-production)
15. [سؤالات متداول](#۱۵-سؤالات-متداول)

---

## ۱. این راهنما برای چه کسی است؟

- کسی که می‌خواهد **سریع** ببیند برنامه روی PC خودش کار می‌کند.
- توسعه‌دهنده یا کارشناس IT که قبل از استقرار شبکه، **یک بار لوکال** تست می‌کند.
- کسی که **نمی‌خواهد** الان `share.config.json`، `init_share.bat` و پوشه `data/` را دستی تنظیم کند.

**این راهنما برای چه کسی نیست؟**

- استقرار چند کاربره روی share شبکه → [DEPLOYMENT.md](DEPLOYMENT.md)
- تنظیم import خودکار روزانه ساعت ۸ → [DEPLOYMENT.md](DEPLOYMENT.md)

---

## ۲. پیش‌نیازها

### ۲.۱ سخت‌افزار و سیستم‌عامل

| مورد | حداقل |
|------|--------|
| سیستم‌عامل | ویندوز ۱۰/۱۱ **یا** لینوکس (Ubuntu و مشابه) |
| RAM | ۴ گیگابایت (پیشنهاد: ۸) |
| فضای دیسک | حدود ۵۰۰ مگابایت برای Python + وابستگی‌ها + DB |
| مرورگر | Chrome، Edge یا Firefox |

### ۲.۲ نرم‌افزار

| مورد | نسخه | چرا لازم است |
|------|------|--------------|
| **Python** | ۳.۹ یا بالاتر (پیشنهاد: ۳.۱۱ یا ۳.۱۲) | اجرای backend و اسکریپت تست |
| **اینترنت** | بار اول | دانلود پکیج‌های Python؛ بارگذاری UI از CDN (فونت، Tailwind) |

### ۲.۳ نصب Python در ویندوز

1. بروید به https://www.python.org/downloads/
2. **Download Python 3.x** را بزنید.
3. فایل نصب را اجرا کنید.
4. در **اولین صفحه** حتماً تیک **Add python.exe to PATH** را بزنید.
5. **Install Now** → صبر کنید تا «Setup was successful» نمایش داده شود.

**تست:**

```cmd
python --version
```

خروجی باید شبیه `Python 3.12.x` باشد. اگر خطای *python is not recognized* دیدید، Python را با تیک PATH دوباره نصب کنید.

### ۲.۴ نصب Python در لینوکس

```bash
python3 --version
```

اگر نصب نبود:

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

### ۲.۵ فایل اکسل

یک فایل اکسل خروجی ERP با درخواست‌های خرید — همان فایلی که در محیط واقعی با نام `input.xlsx` در share قرار می‌گیرد. **حجم معمول:** چند مگابایت تا حدود ۲۰ مگابایت.

---

## ۳. دریافت پروژه

### روش ۱ — دانلود ZIP (ساده‌تر)

1. https://github.com/hmplus28/tadarokat
2. دکمه سبز **Code** → **Download ZIP**
3. فایل ZIP را Extract کنید، مثلاً در:
   ```
   C:\Users\نامشما\Documents\tadarokat
   ```
4. داخل پوشه باید این فایل‌ها را ببینید:
   - `test_run.bat`
   - `install.bat` و `run.bat`
   - پوشه‌های `backend` و `frontend`
   - `scripts/test_setup.py`

### روش ۲ — Git

```bash
git clone git@github.com:hmplus28/tadarokat.git
cd tadarokat
```

---

## ۴. آماده‌سازی فایل اکسل

در حالت تست، **پوشه share همان ریشه پروژه است** — نه `data/`.

### ۴.۱ نام و محل فایل

| قانون | مقدار |
|--------|--------|
| **نام دقیق فایل** | `input.xlsx` |
| **محل** | ریشه پوشه پروژه (کنار `test_run.bat`) |

مثال ویندوز:

```
C:\Users\نامشما\Documents\tadarokat\
├── test_run.bat
├── input.xlsx          ← اینجا
├── backend\
└── frontend\
```

مثال لینوکس:

```
/home/user/tadarokat/
├── test_run.bat
├── input.xlsx          ← اینجا
├── backend/
└── scripts/test_setup.py
```

### ۴.۲ اگر فایل شما نام دیگری دارد

فایل ERP را **Rename** کنید به `input.xlsx` و در ریشه پروژه بگذارید.  
مثال: `اقلام درخواست خرید (1).xlsx` → `input.xlsx`

### ۴.۳ اگر اکسل ندارید

اسکریپت بدون خطا متوقف **نمی‌شود**، اما import رد می‌شود و لیست درخواست‌ها خالی می‌ماند. در ترمینال این هشدار را می‌بینید:

```
[WARN] No Excel file found - skip import (place input.xlsx in project root)
```

برای تست کامل UI و گزارش‌ها، حتماً `input.xlsx` را آماده کنید.

---

## ۵. ساختار پوشه در حالت تست

برخلاف نصب واقعی که داده‌ها در `data/` یا share شبکه است، در تست همه‌چیز در **ریشه پروژه** ساخته می‌شود:

```
tadarokat/                          ← shared_data_dir = "." (همین پوشه)
├── test_run.bat                    ← شروع تست ویندوز
├── input.xlsx                      ← اکسل ورودی (شما می‌گذارید)
├── share.config.json               ← خودکار: shared_data_dir = "."
├── share.config.json.bak           ← بکاپ تنظیم قبلی (اگر بود)
├── share_users.test.seed.json      ← کاربران تست (در git)
├── db_current.db                   ← پایگاه داده (بعد از تست)
├── logs/                           ← لاگ import
│   └── import_YYYYMMDD_HHMMSS.json
├── .venv/                          ← محیط مجازی Python (خودکار)
├── .installed                      ← نشانگر نصب موفق
├── backend/
├── frontend/
└── scripts/
    └── test_setup.py               ← منطق اصلی تست
```

### فایل‌هایی که اسکریپت می‌سازد یا تغییر می‌دهد

| فایل | عملیات |
|------|--------|
| `share.config.json` | بازنویسی با `shared_data_dir: "."` |
| `share.config.json.bak` | اگر تنظیم قبلی متفاوت بود، یک‌بار بکاپ |
| `.venv/` | نصب وابستگی‌های Python |
| `templates/db_current.db` | قالب خالی DB |
| `db_current.db` | DB پر از کاربران + داده اکسل |
| `share_users.seed.json` | موقت — کپی از فایل تست؛ بعد از init حذف می‌شود |
| `logs/` | گزارش هر import |

### فایل‌هایی که `--fresh` پاک می‌کند

فقط این‌ها — **نه** `.venv`، **نه** `backend/`، **نه** `input.xlsx`:

- `db_current.db`
- `db_new.db`
- `db_old.db`
- `lock.flag`
- `share_users.seed.json` (موقت)

---

## ۶. اجرای تست — ویندوز (یک کلیک)

### گام‌به‌گام

| گام | کار شما | انتظار |
|-----|---------|--------|
| **۱** | `input.xlsx` را در ریشه پروژه بگذارید | فایل کنار `test_run.bat` |
| **۲** | در File Explorer پوشه پروژه را باز کنید | مسیر مثلاً `...\tadarokat` |
| **۳** | روی **`test_run.bat`** دوبار کلیک کنید | پنجره CMD سیاه باز می‌شود |
| **۴** | صبر کنید (بار اول: ۲ تا ۱۰ دقیقه) | نصب pip، ساخت DB، import |
| **۵** | پیام `TEST SETUP COMPLETE` را ببینید | بدون `[ERROR]` |
| **۶** | مرورگر خودکار باز می‌شود | `http://127.0.0.1:8000/` |
| **۷** | پنجره CMD باز می‌ماند — سرور در حال اجراست | **نبندید** — با Ctrl+C یا بستن پنجره متوقف می‌شود |

### چه کارهایی `test_run.bat` انجام می‌دهد؟

```
test_run.bat
    │
    ├─► پیدا کردن Python (py -3 یا python)
    │
    ├─► scripts\test_setup.py --fresh --no-server
    │       نصب + DB + کاربران + import + تأیید login
    │
    ├─► باز کردن مرورگر → http://127.0.0.1:8000/
    │
    └─► run.bat → اجرای دائم سرور
```

### اگر Python پیدا نشد

```
[ERROR] Python not found. Install from https://www.python.org/downloads/
        Check "Add python.exe to PATH" during setup.
```

→ [بخش ۲.۳](#۲۳-نصب-python-در-ویندوز) را انجام دهید، سپس دوباره `test_run.bat` را اجرا کنید.

---

## ۷. اجرای تست — لینوکس یا خط فرمان

روی ویندوز هم می‌توانید به‌جای دوبار کلیک، از CMD استفاده کنید.

### ۷.۱ تست کامل + اجرای سرور

```bash
cd /path/to/tadarokat
# input.xlsx باید در همین پوشه باشد
python3 scripts/test_setup.py --fresh --open-browser
```

### ۷.۲ فقط آماده‌سازی (بدون نگه‌داشتن سرور)

```bash
python3 scripts/test_setup.py --fresh --no-server
./run.sh
```

یا در ویندوز CMD:

```cmd
cd C:\Users\نامشما\Documents\tadarokat
python scripts\test_setup.py --fresh --no-server
run.bat
```

### ۷.۳ اجرای مجدد بدون پاک کردن DB

```bash
python3 scripts/test_setup.py
```

بدون `--fresh`: اگر `db_current.db` و کاربران موجود باشند، seed دوباره انجام نمی‌شود.

---

## ۸. مراحل داخلی اسکریپت

`scripts/test_setup.py` این مراحل را **به ترتیب** انجام می‌دهد:

| # | مرحله | توضیح |
|---|--------|--------|
| 1 | **تنظیم share تست** | `share.config.json` با `shared_data_dir: "."` |
| 2 | **بکاپ config** | اگر تنظیم قبلی متفاوت بود → `share.config.json.bak` |
| 3 | **نصب** | `install.bat` / `install.sh` — یا رد شدن اگر `.installed` موجود است |
| 4 | **قالب DB** | `scripts/build_db_template.py` |
| 5 | **Reset (--fresh)** | حذف `db_*.db` و `lock.flag` |
| 6 | **Seed کاربران** | کپی `share_users.test.seed.json` → `share_users.seed.json` |
| 7 | **init_share** | ساخت `db_current.db` + import کاربران؛ حذف seed موقت |
| 8 | **اکسل** | بررسی `input.xlsx` در ریشه |
| 9 | **Import** | خواندن اکسل و پر کردن DB |
| 10 | **Verify** | راه‌اندازی موقت سرور + تست login چهار کاربر |
| 11 | **Server** | اجرای سرور (مگر `--no-server`) |

---

## ۹. کاربران و نقش‌های تست

این حساب‌ها از `share_users.test.seed.json` ساخته می‌شوند. **فقط برای تست** — در production استفاده نکنید.

| نام کاربری | رمز عبور | نقش | توضیح |
|------------|----------|------|--------|
| `admin` | `admin123` | مدیر سیستم | دسترسی کامل |
| `manager` | `manager123` | مدیر تدارکات | مدیریت و گزارش |
| `mostafa` | `mostafa123` | کارشناس خرید | کارشناس: مصطفی رضوانی |
| `fabri` | `fabri123` | کارشناس خرید | کارشناس: فریبا صالح آبادی |
| `behnaz` | `behnaz123` | کارشناس خرید | کارشناس: بهناز عظیمی |
| `anbar` | `anbar123` | انبار | انبار مصرفی |

اسکریپت verify به‌طور خودکار login این چهار کاربر را تست می‌کند: `admin`، `manager`، `mostafa`، `anbar`.

---

## ۱۰. ورود به سامانه و تست UI

### ۱۰.۱ باز کردن برنامه

آدرس: **http://127.0.0.1:8000/**

اگر صفحه باز نشد:
- پنجره CMD/`run.bat` باید باز و بدون خطا باشد.
- آدرس را دستی در مرورگر بزنید.
- پورت دیگری در `share.config.json` نیست؛ پیش‌فرض **8000** است.

### ۱۰.۲ ورود

1. نام کاربری: مثلاً `admin`
2. رمز: `admin123`
3. **ورود**

### ۱۰.۳ چک‌لیست تست سریع

| # | تست | کاربر پیشنهادی |
|---|------|----------------|
| 1 | داشبورد و آمار بارگذاری شود | `admin` |
| 2 | لیست درخواست‌های خرید پر باشد (بعد از import) | `admin` یا `manager` |
| 3 | کارشناس فقط درخواست‌های خودش را ببیند | `mostafa` |
| 4 | فیلتر و جستجو کار کند | `manager` |
| 5 | خروج و ورود مجدد | هر کاربر |

### ۱۰.۴ تست سلامت API (اختیاری)

```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

در حالت تست موفق:
- `shared_data_dir` باید مسیر ریشه پروژه باشد (نه `data/`)
- `database_exists: true`
- `users_count` بزرگ‌تر از ۰
- `purchase_count` بزرگ‌تر از ۰ (اگر import شده)

---

## ۱۱. گزینه‌های پیشرفته خط فرمان

```text
python scripts/test_setup.py [گزینه‌ها]
```

| گزینه | معنی |
|--------|------|
| `--fresh` | پاک کردن DB و ساخت مجدد کاربران از seed تست |
| `--no-import` | رد شدن از import اکسل |
| `--no-server` | فقط setup؛ سرور را خودتان با `run.bat` / `run.sh` اجرا کنید |
| `--no-verify` | رد شدن از تست خودکار login |
| `--open-browser` | باز کردن مرورگر (ویندوز) بعد از setup |

**مثال‌ها:**

```bash
# reset کامل + import + بدون verify
python3 scripts/test_setup.py --fresh --no-verify

# فقط نصب و DB، بدون اکسل
python3 scripts/test_setup.py --fresh --no-import

# همان کاری که test_run.bat قبل از run.bat انجام می‌دهد
python3 scripts/test_setup.py --fresh --no-server
```

---

## ۱۲. خروجی موفق چگونه است؟

نمونه خروجی ترمینال (بخش‌های مهم):

```
==========================================
  Tadarokat - TEST SETUP
==========================================

[OK] Test share: project root (.)
[OK] Install already done (skipped)
-> DB template
[OK] .../templates/db_current.db
-> Fresh reset (DB + seed staging)
[OK] Data folder reset
[OK] Staged test users seed -> .../share_users.seed.json
[OK] Database: .../db_current.db
[OK] Users in DB: 6
[OK] Excel ready: .../input.xlsx
[OK] Excel imported into DB (rows=1905)
[OK] Server health check
-> Verifying test logins...
    [OK] login admin
    [OK] login manager
    [OK] login mostafa
    [OK] login anbar
[OK] All 4 test logins verified

==========================================
  TEST SETUP COMPLETE
==========================================
  URL:   http://127.0.0.1:8000
```

**نشانه‌های موفقیت:**

- هیچ خط `[ERROR]` نیست
- `Users in DB: 6`
- `Excel imported` با تعداد ردیف بزرگ‌تر از ۰
- `All 4 test logins verified`
- فایل `db_current.db` در ریشه پروژه ساخته شده

---

## ۱۳. مشکلات رایج

| مشکل | علت محتمل | راه‌حل |
|------|-----------|--------|
| `Python not found` | PATH تنظیم نشده | Python را با تیک **Add to PATH** نصب کنید |
| پنجره `test_run.bat` سریع بسته می‌شود | خطا قبل از `pause` | CMD را باز کنید، `cd` به پوشه پروژه، `test_run.bat` را دستی اجرا کنید |
| `[WARN] No Excel file found` | `input.xlsx` نیست یا کوچک است | فایل را با نام دقیق `input.xlsx` در **ریشه** بگذارید |
| `Login check failed` | پورت 8000 اشغال است | برنامه دیگر روی 8000 را ببندید؛ یا پورت را در config عوض کنید |
| `Server did not start within 90s` | فایروال / آنتی‌ویروس / پورت | `run.bat` را جدا تست کنید؛ لاگ CMD را بخوانید |
| لیست درخواست‌ها خالی | import نشده یا اکسل خالی | `--fresh` دوباره؛ اکسل را بررسی کنید |
| UI بدون استایل | اینترنت قطع (CDN) | اتصال اینترنت؛ Ctrl+F5 |
| کارشناس داده نمی‌بیند | نام کارشناس در ERP با seed فرق دارد | با `admin` همه را ببینید؛ در production نام `expert` را دقیق تنظیم کنید |
| `Virtual env missing` | نصب ناقص | `install.bat` یا `python scripts/install_windows.py` |
| health می‌گوید `data/` نه روت | سرور قدیمی هنوز روشن است | CMD قبلی را ببندید؛ `test_run.bat` را دوباره اجرا کنید |

### پورت 8000 اشغال است (ویندوز)

```cmd
netstat -ano | findstr :8000
taskkill /PID شماره_PID /F
```

### پورت 8000 اشغال است (لینوکس)

```bash
ss -tlnp | grep 8000
kill شماره_PID
```

---

## ۱۴. بازگشت به حالت نصب واقعی (Production)

بعد از تست، برای استقرار واقعی:

### ۱۴.۱ بازگرداندن تنظیم share

اگر `share.config.json.bak` ساخته شده:

1. فایل فعلی `share.config.json` را حذف یا rename کنید.
2. `share.config.json.bak` را به `share.config.json` rename کنید.
3. یا دستی `shared_data_dir` را به `./data` یا مسیر share شبکه تغییر دهید:

```json
{
  "shared_data_dir": "./data",
  "local_data_dir": "",
  "port": 8000,
  "mode": "full",
  "host": "127.0.0.1"
}
```

### ۱۴.۲ انتقال داده تست (اختیاری)

اگر می‌خواهید DB تست را نگه دارید:

```text
db_current.db  →  data/db_current.db
input.xlsx     →  data/input.xlsx
logs/          →  data/logs/
```

### ۱۴.۳ مراحل production

1. `install.bat` (اگر هنوز نصب نکرده‌اید)
2. `share.config.json` → مسیر `data/` یا share شبکه
3. `share_users.seed.json` با **رمز واقعی** در share
4. `init_share.bat`
5. `input.xlsx` در پوشه share
6. `run.bat`

جزئیات: [README](../README.md) و [DEPLOYMENT.md](DEPLOYMENT.md)

---

## ۱۵. سؤالات متداول

**هر بار `test_run.bat` دیتابیس را پاک می‌کند؟**  
بله. همیشه `--fresh` اجرا می‌شود. داده‌های قبلی تست در `db_current.db` از بین می‌رود.

**آیا `test_run.bat` جای `install.bat` را می‌گیرد؟**  
خیر. تست خودش نصب را هم انجام می‌دهد، اما برای محیط واقعی و چند PC باید [README](../README.md) را دنبال کنید.

**چرا share در تست ریشه پروژه است؟**  
برای ساده‌سازی: یک پوشه، یک `input.xlsx`، بدون `init_share` دستی.

**آیا `input.xlsx` در git است؟**  
خیر — در `.gitignore` است. هر کاربر فایل خودش را می‌گذارد.

**آیا می‌توانم seed تست را ویرایش کنم؟**  
بله — `share_users.test.seed.json` را ویرایش کنید و `--fresh` اجرا کنید.

**تفاوت `test_run.bat` و `scripts/test_setup.py --fresh`؟**  
`test_run.bat` همان setup با `--fresh --no-server` است، سپس مرورگر و `run.bat`.

---

## مسیر بعدی

```
TEST_SETUP.md (همین سند — تست لوکال)
    ↓
README.md (نصب کامل production)
    ↓
DEPLOYMENT.md (شبکه، چند PC، import روزانه)
    ↓
ARCHITECTURE.md (جزئیات فنی DB و API)
```

**مشکل یا پیشنهاد:** https://github.com/hmplus28/tadarokat/issues