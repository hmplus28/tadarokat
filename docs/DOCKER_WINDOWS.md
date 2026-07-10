# راهنمای نصب و اجرای تدارکات با Docker روی ویندوز

## شروع فوری (یک دستور)

**پیش‌نیاز:** فقط Docker Desktop نصب و روشن باشد.

```powershell
cd C:\tadarokat\tadarokat-django
docker compose up --build
```

یا روی **`start.bat`** دوبار کلیک کنید.

> راهنمای کوتاه در ریشه پروژه: **`RAHNAMA_NASB.md`**

مرورگر: **http://localhost:8000**  
ورود پیش‌فرض (اولین بار خودکار ساخته می‌شود):

| نام کاربری | رمز |
|------------|-----|
| `admin` | `admin1234` |

نیازی به `.env`، `migrate` یا `createsuperuser` دستی نیست.

---

این راهنما از **صفر** است: حتی اگر Docker نصب ندارید، مرحله‌به‌مرحله پیش می‌رویم.

---

## فهرست

1. [پیش‌نیازها](#۱-پیش‌نیازها)
2. [نصب Docker Desktop روی ویندوز](#۲-نصب-docker-desktop-روی-ویندوز)
3. [آماده‌سازی پروژه](#۳-آماده‌سازی-پروژه)
4. [اجرای اولیه](#۴-اجرای-اولیه)
5. [ساخت کاربر ادمین](#۵-ساخت-کاربر-ادمین)
6. [دستورات روزمره](#۶-دستورات-روزمره)
7. [انتقال دیتابیس موجود](#۷-انتقال-دیتابیس-موجود)
8. [Redis اختیاری](#۸-redis-اختیاری)
9. [عیب‌یابی](#۹-عیب‌یابی)

---

## ۱. پیش‌نیازها

| مورد | توضیح |
|------|--------|
| ویندوز ۱۰/۱۱ (۶۴ بیت) | نسخه Pro یا Home هر دو پشتیبانی می‌شوند |
| Virtualization | در BIOS فعال باشد (Intel VT-x / AMD-V) |
| RAM | حداقل ۴ گیگ (۸ گیگ پیشنهاد می‌شود) |
| فضای دیسک | حداقل ۵ گیگ آزاد |

### بررسی Virtualization

1. `Ctrl + Shift + Esc` → Task Manager
2. تب **Performance** → **CPU**
3. پایین صفحه: **Virtualization: Enabled**

اگر Disabled است، باید از BIOS فعال شود.

---

## ۲. نصب Docker Desktop روی ویندوز

### مرحله ۱ — نصب WSL2 (زیرساخت لینوکس ویندوز)

PowerShell را **به‌عنوان Administrator** باز کنید و بزنید:

```powershell
wsl --install
```

سیستم را **ری‌استارت** کنید.

بعد از بالا آمدن ویندوز:

```powershell
wsl --set-default-version 2
wsl --update
```

بررسی:

```powershell
wsl --status
```

باید `Default Version: 2` را ببینید.

### مرحله ۲ — دانلود Docker Desktop

1. بروید به: https://www.docker.com/products/docker-desktop/
2. **Download for Windows** را بزنید
3. فایل `Docker Desktop Installer.exe` را اجرا کنید
4. گزینه **Use WSL 2 instead of Hyper-V** را تیک بزنید
5. نصب را تمام کنید و سیستم را ری‌استارت کنید

### مرحله ۳ — اجرای Docker Desktop

1. از منوی Start برنامه **Docker Desktop** را باز کنید
2. صبر کنید تا پایین صفحه نوشته شود: **Docker Desktop is running**
3. آیکن نهنگ در System Tray سبز شود

### مرحله ۴ — تست نصب

PowerShell یا CMD:

```powershell
docker --version
docker compose version
```

خروجی نمونه:

```
Docker version 27.x.x
Docker Compose version v2.x.x
```

اگر خطا داد، Docker Desktop را باز کنید و چند دقیقه صبر کنید.

---

## ۳. آماده‌سازی پروژه

پوشه `tadarokat-django` را کپی کنید. **فایل `.env` لازم نیست.**

---

## ۴. اجرای اولیه

```powershell
cd C:\tadarokat\tadarokat-django
docker compose up --build
```

یا `start.bat`

اولین بار ۵–۱۵ دقیقه طول می‌کشد. وقتی دیدید:

`Starting development server at http://0.0.0.0:8000/`

→ **http://localhost:8000** — ورود: `admin` / `admin1234`

برای توقف: `Ctrl + C`

---

## ۵. ساخت کاربر ادمین (اختیاری)

ادمین اولیه خودکار ساخته می‌شود. برای ساخت دستی:

```powershell
docker compose exec web python manage.py createsuperuser
```

---

## ۶. دستورات روزمره

| کار | دستور |
|-----|--------|
| شروع | `docker compose up -d` |
| توقف | `docker compose down` |
| ری‌استارت | `docker compose restart web` |
| مشاهده لاگ | `docker compose logs -f web` |
| ورود به شل داخل کانتینر | `docker compose exec web sh` |
| اجرای migrate | `docker compose exec web python manage.py migrate` |
| جمع‌آوری static | `docker compose exec web python manage.py collectstatic --noinput` |
| به‌روزرسانی بعد از تغییر کد | `docker compose up -d --build` |

---

## ۷. انتقال دیتابیس موجود

اگر قبلاً روی همین سیستم (بدون Docker) کار می‌کردید و `db.sqlite3` دارید:

### روش ۱ — قبل از اولین اجرا

```powershell
mkdir data
copy db.sqlite3 data\db.sqlite3
docker compose up -d --build
```

> دیتابیس داخل volume با نام `tadarokat_data` ذخیره می‌شود. فایل `./data/db.sqlite3` فقط برای کپی اولیه است.

### روش ۲ — بعد از اجرا

```powershell
docker compose up -d
docker cp db.sqlite3 tadarokat-web:/app/data/db.sqlite3
docker compose restart web
```

### فایل‌های اکسل (فقط دو تا در ریشه)

| فایل | نقش |
|------|-----|
| `input.xlsx` | ورودی / همگام‌سازی |
| `panel.xlsx` | خروجی غنی‌شده با داده پنل |

برای Docker هر دو فایل از پوشه پروژه به کانتینر mount می‌شوند. اگر `panel.xlsx` ندارید: `copy input.xlsx panel.xlsx`

---

## ۸. Redis اختیاری

پیش‌فرض بدون Redis کار می‌کند (cache در حافظه). برای فعال‌سازی Redis:

در `.env` اضافه کنید:

```env
REDIS_URL=redis://redis:6379/0
```

سپس:

```powershell
docker compose --profile redis up -d --build
```

---

## ۹. عیب‌یابی

### `Docker نصب نیست` یا `command not found`

- Docker Desktop را باز کنید و صبر کنید تا Ready شود
- PowerShell را ببندید و دوباره باز کنید

### `WSL 2 installation is incomplete`

```powershell
wsl --install
wsl --update
```

ری‌استارت و دوباره Docker Desktop را باز کنید.

### پورت ۸۰۰۰ اشغال است

در `.env` عوض کنید:

```env
APP_PORT=8080
```

سپس: `http://localhost:8080`

### کانتینر بالا نمی‌آید

```powershell
docker compose logs web
```

خطاهای migrate یا import را بررسی کنید.

### صفحه بدون CSS (استایل ندارد)

```powershell
docker compose exec web python manage.py collectstatic --noinput
docker compose restart web
```

### خطای WinError 32 در آپلود اکسل

فایل `input.xlsx` را در Excel روی **میزبان ویندوز** نبندید؛ داخل Docker فایل جداگانه نگهداری می‌شود.

### پاک‌سازی کامل و شروع از نو

```powershell
docker compose down -v
docker compose up -d --build
```

> **هشدار:** `-v` همه داده‌ها (دیتابیس، media) را پاک می‌کند.

### پشتیبان‌گیری دیتابیس

```powershell
docker compose exec web python -c "import shutil; shutil.copy('/app/data/db.sqlite3', '/app/data/db_backup.sqlite3')"
docker cp tadarokat-web:/app/data/db.sqlite3 .\backup_db.sqlite3
```

---

## ساختار Docker پروژه

```
tadarokat-django/
├── Dockerfile              # تصویر اپلیکیشن
├── docker-compose.yml      # سرویس‌ها و volumeها
├── .env.example            # نمونه تنظیمات
├── start.bat               # یک کلیک — همه‌چیز خودکار
├── scripts/
│   └── docker-entrypoint.sh  # migrate + collectstatic + runserver
├── config/
│   └── settings_docker.py    # تنظیمات مخصوص Docker
└── docs/
    └── DOCKER_WINDOWS.md     # همین فایل
```

### Volumeها

| Volume | محتوا |
|--------|--------|
| `tadarokat_data` | دیتابیس SQLite |
| `tadarokat_media` | فایل‌های آپلود (اکسل و ...) |
| `tadarokat_static` | CSS/JS جمع‌شده |

---

## دسترسی از شبکه داخلی

اگر از کامپیوتر دیگر در شبکه محلی وصل می‌شوید:

1. IP سرور را پیدا کنید: `ipconfig` → مثلاً `192.168.1.50`
2. در `.env`:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://192.168.1.50:8000
```

3. `docker compose restart web`
4. در مرورگر: `http://192.168.1.50:8000`

فایروال ویندوز ممکن است نیاز به باز کردن پورت ۸۰۰۰ داشته باشد.

---

## پشتیبانی

مشکل دارید؟ این خروجی‌ها را ذخیره کنید:

```powershell
docker compose ps
docker compose logs web --tail 100
docker --version
```