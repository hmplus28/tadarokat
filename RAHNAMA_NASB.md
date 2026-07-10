# راهنمای نصب و اجرای تدارکات

## شروع سریع (یک کلیک)

1. **Docker Desktop** را نصب و **روشن** کنید (آیکن نهنگ سبز).
2. فایل **`start.bat`** را دوبار کلیک کنید.
3. صبر کنید تا پیام `Starting development server` بیاید.
4. مرورگر: **http://localhost:8000**
5. ورود: `admin` / `admin1234`

> پنجره `start.bat` دیگر خودبه‌خود بسته نمی‌شود — در پایان `pause` می‌زند تا خطا را ببینید.

اگر `start.bat` فوراً بسته شد، احتمالاً Docker نصب نیست یا روشن نیست. دوباره اجرا کنید و پیام قرمز را بخوانید.

---

## فایل‌های اکسل (فقط دو تا)

در **ریشه پروژه** فقط این دو فایل داده دارید:

| فایل | نقش |
|------|-----|
| **`input.xlsx`** | ورودی — داده خام / همگام‌سازی از اکسل |
| **`panel.xlsx`** | خروجی — اکسل غنی‌شده با وضعیت پنل (بعد از sync یا آپلود) |

- فایل‌های اضافی مثل `input_abc12345.xlsx` دیگر ساخته **نمی‌شوند**.
- اگر `input.xlsx` در Excel باز باشد، به‌روزرسانی خطا می‌دهد — **قبل از sync ببندید**.
- فایل `~$input.xlsx` قفل موقت Excel است؛ با بستن Excel پاک می‌شود.

### اولین بار با Docker

اگر `panel.xlsx` ندارید، یک کپی از `input.xlsx` بسازید:

```powershell
copy input.xlsx panel.xlsx
```

Docker این دو فایل را از پوشه پروژه به داخل کانتینر وصل می‌کند.

---

## نصب Docker (اگر ندارید)

### ۱. WSL2

PowerShell **Administrator**:

```powershell
wsl --install
```

ری‌استارت → بعد:

```powershell
wsl --set-default-version 2
wsl --update
```

### ۲. Docker Desktop

1. https://www.docker.com/products/docker-desktop/
2. نصب با گزینه **Use WSL 2**
3. اجرای Docker Desktop تا **Docker Desktop is running**

### ۳. تست

```powershell
docker --version
docker compose version
docker info
```

---

## اجرای دستی (بدون start.bat)

```powershell
cd C:\Users\AVA\Documents\tadarokat\tadarokat-django
docker compose up --build
```

توقف: `Ctrl + C`

---

## دستورات روزمره

| کار | دستور |
|-----|--------|
| شروع در پس‌زمینه | `docker compose up -d --build` |
| توقف | `docker compose down` |
| لاگ | `docker compose logs -f web` |
| migrate | `docker compose exec web python manage.py migrate` |

---

## عیب‌یابی

### Docker نصب نیست / روشن نیست
- Docker Desktop را باز کنید و ۱–۲ دقیقه صبر کنید.
- PowerShell را ببندید و دوباره `start.bat` بزنید.

### پورت ۸۰۰۰ اشغال است
برنامه دیگری روی ۸۰۰۰ است؛ آن را ببندید یا در `docker-compose.yml` پورت را عوض کنید.

### کانتینر بالا نمی‌آید
```powershell
docker compose logs web
```

### خطای WinError 32 در آپلود
`input.xlsx` یا `panel.xlsx` در Excel باز است — ببندید و دوباره آپلود کنید.

### پاک‌سازی کامل (حذف دیتابیس)
```powershell
docker compose down -v
docker compose up --build
```

---

## راهنمای کامل‌تر

جزئیات بیشتر (شبکه، Redis، انتقال دیتابیس): **`docs/DOCKER_WINDOWS.md`**

---

## ساختار مهم

```
tadarokat-django/
├── start.bat           ← یک کلیک برای اجرا
├── RAHNAMA_NASB.md     ← همین فایل
├── input.xlsx          ← ورودی
├── panel.xlsx          ← خروجی / ذخیره
├── docker-compose.yml
└── docs/
    └── DOCKER_WINDOWS.md
```