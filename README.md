# سامانه تدارکات

برنامهٔ تحت وب برای مدیریت درخواست‌های خرید، استعلام، دستور خرید و گزارش‌گیری.

**ریپو:** https://github.com/hmplus28/tadarokat

---

## فهرست مستندات

| سند | مخاطب | محتوا |
|-----|--------|--------|
| **همین README** | همه | راهنمای صفر تا صد نصب |
| [راهنمای استقرار](docs/DEPLOYMENT.md) | IT / admin | شبکه، share چندکاربره، import روزانه |
| [معماری داده](docs/ARCHITECTURE.md) | توسعه‌دهنده | DB، import، همزمانی |

---

# راهنمای نصب — از صفر تا اجرا

این بخش برای کسی است که **Git و Python** را کم‌وبیش نمی‌شناسد. مراحل را **به ترتیب** انجام دهید.

---

## گام ۰ — چه چیزهایی لازم است؟

| مورد | چرا |
|------|-----|
| **ویندوز ۱۰/۱۱** (یا لینوکس) | محیط اجرا |
| **Python 3.9 یا بالاتر** | موتور برنامه (گام ۱) |
| **مرورگر** (Chrome / Edge) | باز کردن سامانه |
| **اینترنت** | بار اول برای ظاهر UI (فونت و Tailwind) |
| **فایل اکسل خرید** (`input.xlsx`) | دادهٔ درخواست‌ها — بعداً در گام ۷ |

---

## گام ۱ — نصب Python (ویندوز)

### ۱.۱ دانلود

1. بروید به: https://www.python.org/downloads/  
2. دکمه **Download Python 3.x** را بزنید.  
3. فایل نصب (مثلاً `python-3.12.x-amd64.exe`) را اجرا کنید.

### ۱.۲ نصب — مهم

در اولین صفحه نصب:

- حتماً تیک **Add python.exe to PATH** را بزنید.  
- روی **Install Now** کلیک کنید.  
- صبر کنید تا **Setup was successful** بیاید.

### ۱.۳ تست نصب

1. کلیدهای `Win + R` را بزنید.  
2. بنویسید `cmd` و Enter.  
3. در پنجره سیاه بنویسید:

```cmd
python --version
```

باید چیزی شبیه `Python 3.12.x` ببینید.

اگر خطای *python is not recognized* آمد → Python را دوباره نصب کنید و تیک PATH را بزنید.

### لینوکس (اختیاری)

```bash
python3 --version
# اگر نبود:
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
```

---

## گام ۲ — دریافت پروژه

### بدون Git (ساده‌تر)

1. https://github.com/hmplus28/tadarokat  
2. دکمه سبز **Code** → **Download ZIP**  
3. ZIP را Extract کنید، مثلاً در:  
   `C:\Users\نامشما\Documents\tadarokat`  
4. داخل پوشه باید این‌ها را ببینید:  
   `install.bat` · `run.bat` · پوشه `backend` · پوشه `frontend`

### با Git

```bash
git clone git@github.com:hmplus28/tadarokat.git
cd tadarokat
```

---

## تست سریع ویندوز (یک کلیک)

برای تست لوکال بدون مراحل دستی:

1. دوبار کلیک **`test_run.bat`**
2. صبر کنید تا نصب + DB + کاربران + import اکسل تمام شود
3. مرورگر باز می‌شود و سرور اجرا می‌شود

| کاربر | رمز |
|-------|-----|
| admin | admin123 |
| manager | manager123 |
| mostafa | mostafa123 |
| anbar | anbar123 |
| fabri | fabri123 |
| behnaz | behnaz123 |

> هر اجرای `test_run.bat` دیتابیس را از نو می‌سازد (`--fresh`). برای نصب واقعی از `install.bat` استفاده کنید.

---

## گام ۳ — نصب برنامه (یک بار روی هر PC)

### ویندوز

1. پوشه `tadarokat` را در File Explorer باز کنید.  
2. روی **`install.bat`** دوبار کلیک کنید.  
3. پنجره سیاه باز می‌ماند — تا **نصب کامل شد** صبر کنید، سپس یک کلید بزنید.

> اگر پنجره سریع بسته شد: Python نصب نیست یا PATH تنظیم نشده — [گام ۱](#گام-۱--نصب-python-ویندوز) را دوباره انجام دهید.  
> یا از CMD اجرا کنید: `cd مسیر\tadarokat` سپس `install.bat` — متن خطا می‌ماند.

**این مرحله چه کار می‌کند؟**

- ساخت محیط مجازی Python (پوشه `.venv`)  
- نصب کتابخانه‌ها از `backend/requirements.txt`  
- ساخت قالب پایگاه داده (`templates/db_current.db`)  
- ساخت `share.config.json` اگر نباشد  

### لینوکس

```bash
cd مسیر/tadarokat
chmod +x install.sh run.sh scripts/init_share.sh
./install.sh
```

---

## گام ۴ — تنظیم پوشه داده (share)

فایل **`share.config.json`** مسیر دادهٔ مشترک را مشخص می‌کند.

### تست روی یک کامپیوتر (لوکال)

معمولاً بعد از `install.bat` همین فایل ساخته شده و کافی است. اگر `shared_data_dir` خالی یا نامشخص است:

1. فایل `share.config.example.json` را باز کنید.  
2. کپی کنید به `share.config.json` (اگر نیست).  
3. برای تست تک‌کاربره:

```json
{
  "shared_data_dir": "./data",
  "local_data_dir": "",
  "port": 8000,
  "mode": "full",
  "host": "127.0.0.1"
}
```

پوشه `data` کنار پروژه ساخته می‌شود و همه فایل‌ها آنجا می‌روند.

### استفاده در شبکه (چند کاربر)

`shared_data_dir` را به مسیر share شبکه بگذارید، مثلاً:

```json
"shared_data_dir": "\\\\server\\share\\tadarokat\\data"
```

جزئیات بیشتر: [راهنمای استقرار — IT](docs/DEPLOYMENT.md#it--یک-بار)

| فیلد | معنی |
|------|------|
| `shared_data_dir` | پوشه مشترک: DB، اکسل، لاگ |
| `port` | پورت سرور (پیش‌فرض ۸۰۰۰) |
| `mode` | `full` = همه قابلیت‌ها روی این PC |

---

## گام ۵ — ساخت کاربران (خیلی مهم)

کاربران در **پایگاه داده روی share** ذخیره می‌شوند، نه داخل کد پروژه.  
اولین بار باید فایل **seed** بسازید و `init_share` را اجرا کنید.

### ۵.۱ نقش‌های سیستم

| نقش (`role`) | کاربرد | فیلدهای اضافه |
|--------------|--------|----------------|
| `admin` | IT — کاربران، import اکسل، پنل سیستم | — |
| `manager` | مدیر تدارکات — بررسی استعلام، گزارش | — |
| `expert` | کارشناس خرید | **`expert`** = نام دقیق در ERP (ستون کارشناس خرید) |
| `warehouse` | مسئول انبار | **`warehouse`** = نام انبار (مثلاً `انبار مصرفی`) |

### ۵.۲ ساخت فایل seed

1. فایل [share_users.seed.example.json](share_users.seed.example.json) را باز کنید.  
2. **Save As** با نام: **`share_users.seed.json`**  
3. برای **هر کاربر** فیلد `password` را عوض کنید.  
   - `CHANGE_ME_STRONG_PASSWORD` **قبول نمی‌شود**  
   - رمزها را در جای امن یادداشت کنید (فایل seed بعداً حذف می‌شود)

**نمونه کارشناس** — نام `expert` باید **دقیقاً** مثل اکسل باشد:

```json
{
  "username": "mostafa",
  "password": "رمز-قوی-شما",
  "name": "مصطفی رضوانی",
  "role": "expert",
  "expert": "مصطفی رضوانی",
  "warehouse": null
}
```

**نمونه انبار:**

```json
{
  "username": "anbar",
  "password": "رمز-قوی-شما",
  "name": "مسئول انبار مصرفی",
  "role": "warehouse",
  "expert": null,
  "warehouse": "انبار مصرفی"
}
```

### ۵.۳ کجا فایل seed را بگذاریم؟

فایل `share_users.seed.json` را در **پوشه share** قرار دهید:

- لوکال: `tadarokat\data\share_users.seed.json`  
- شبکه: `\\server\share\tadarokat\data\share_users.seed.json`

(همان مسیری که در `share.config.json` → `shared_data_dir` است)

### ۵.۴ اجرای init_share (یک بار — معمولاً IT)

این دستور:

- `db_current.db` را روی share می‌سازد  
- کاربران seed را وارد DB می‌کند  
- **فایل seed را حذف می‌کند** (امنیت)

**ویندوز:**

```cmd
cd C:\Users\...\Documents\tadarokat
scripts\init_share.bat
```

**لینوکس:**

```bash
./scripts/init_share.sh
```

خروجی موفق:

```
✓ share آماده شد
  DB: ...\data\db_current.db
  کاربران: 4
  • 4 کاربر از seed وارد شد — فایل seed حذف شد.
```

### ۵.۵ اگر init_share خطا داد

| پیام | کار |
|------|-----|
| `رمز ... هنوز تنظیم نشده` | همه `CHANGE_ME` را در seed عوض کنید |
| `فایل seed یافت نشد` | `share_users.seed.json` را در پوشه `data` بگذارید |
| `کاربری در DB نیست` | seed را دوباره بگذارید و init_share را تکرار کنید |

### ۵.۶ افزودن کاربر بعداً (بدون seed)

بعد از ورود با `admin`:

1. منو → **کاربران**  
2. **افزودن کاربر** — نام کاربری، رمز، نقش  
3. برای `expert`: فیلد expert = نام ERP  
4. برای `warehouse`: نام انبار را پر کنید  

> **توجه:** `init_share` فقط وقتی DB خالی است seed می‌خواند. اگر کاربر دارید، از پنل admin استفاده کنید.

---

## گام ۶ — قرار دادن فایل اکسل خرید

سامانه دادهٔ ERP را از اکسل می‌خواند (نه مستقیم در حین کار).

1. فایل روزانه ERP را با نام **`input.xlsx`** در پوشه share بگذارید:  
   `data\input.xlsx`  
2. یا لینک/کپی با نام `purchases.xlsx` در همان پوشه.

بدون اکسل، برنامه اجرا می‌شود ولی لیست درخواست‌ها خالی است.

---

## گام ۷ — اجرای سامانه

### هر بار که می‌خواهید کار کنید

| سیستم | کار |
|--------|-----|
| ویندوز | دوبار کلیک **`run.bat`** — پنجره را **نبندید** |
| لینوکس | `./run.sh` |

### باز کردن در مرورگر

```
http://127.0.0.1:8000
```

صفحه **ورود به سامانه** باید بیاید.

### خاموش کردن

پنجره `run.bat` را ببندید یا `Ctrl + C` در ترمینال.

---

## گام ۸ — ورود و تست اولیه

### ۸.۱ ورود

با کاربر و رمزی که در seed (گام ۵) تعریف کردید وارد شوید.

برای محیط تستی نمونه (اگر همان رمزهای demo را گذاشته باشید):

| کاربر | رمز نمونه | نقش |
|-------|-----------|-----|
| `admin` | `admin123` | مدیر سیستم |
| `manager` | `manager123` | مدیر |
| `mostafa` | `mostafa123` | کارشناس |
| `anbar` | `anbar123` | انبار |

### ۸.۲ import اکسل به دیتابیس (admin)

1. با `admin` وارد شوید.  
2. منو → **پنل سیستم**.  
3. دکمه **اکسل را الان به دیتابیس import کن**.  
4. بعد از موفقیت، **درخواست‌های خرید** را باز کنید — باید داده ببینید.

### ۸.۳ چک‌لیست تست

- [ ] داشبورد باز می‌شود  
- [ ] درخواست‌های خرید لیست دارد (بعد از import)  
- [ ] دکمه **🔄 آخرین داده** در هدر کار می‌کند  
- [ ] کارشناس فقط درخواست‌های خودش را می‌بیند  
- [ ] مدیر → بررسی استعلام / گزارش‌ها  

### ۸.۴ تست خودکار API (اختیاری)

با روشن بودن `run.bat`:

```bash
# ویندوز — Git Bash یا WSL
bash scripts/e2e_api_test.sh
```

```bash
# لینوکس
./scripts/e2e_api_test.sh
```

باید چند خط `[OK]` ببینید.

---

## خلاصه مراحل (یک نگاه)

```
۱ Python نصب + PATH
۲ دانلود ZIP پروژه
۳ install.bat
۴ share.config.json → مسیر data یا share شبکه
۵ share_users.seed.json → رمز واقعی → data\ → init_share.bat
۶ input.xlsx در data
۷ run.bat → http://127.0.0.1:8000
۸ ورود admin → import اکسل → تست
```

---

## ساختار پوشه‌ها

```
tadarokat/
├── README.md
├── test_run.bat                  ← تست یک‌کلیک ویندوز
├── install.bat / install.sh      ← گام ۳
├── run.bat / run.sh              ← گام ۷
├── share.config.json             ← گام ۴
├── share_users.seed.example.json ← گام ۵ (نمونه)
├── data/                         ← پوشه share لوکال
│   ├── share_users.seed.json     ← قبل از init (موقت)
│   ├── db_current.db             ← بعد از init
│   ├── input.xlsx              ← گام ۶
│   └── logs/
├── docs/
│   ├── DEPLOYMENT.md
│   └── ARCHITECTURE.md
├── backend/
├── frontend/
└── scripts/
    ├── init_share.bat            ← گام ۵
    └── e2e_api_test.sh         ← گام ۸
```

---

## مشکلات رایج

| مشکل | راه‌حل |
|------|--------|
| `python` پیدا نشد | گام ۱ — PATH؛ CMD → `install.bat` |
| `install.bat` سریع بسته می‌شود | Python نیست؛ یا CMD باز کنید و دستی اجرا کنید |
| نصب ناموفق / pip خطا | اینترنت؛ آنتی‌ویروس؛ CMD as Administrator |
| صفحه باز نمی‌شود | `run.bat` روشن باشد |
| ورود نمی‌شود | گام ۵ — init_share + seed |
| لیست خالی است | گام ۶ + گام ۸ import اکسل |
| کارشناس داده نمی‌بیند | `expert` در seed = نام دقیق ERP |
| داده قدیمی | **🔄 آخرین داده** یا import دوباره |
| UI خراب | اینترنت + Ctrl+F5 |
| share شبکه | [DEPLOYMENT](docs/DEPLOYMENT.md) |

---

## مسیر یادگیری

```
README (همین سند — نصب کامل)
    ↓
DEPLOYMENT (چند PC، import خودکار ۸ صبح)
    ↓
ARCHITECTURE (جزئیات DB و API)
```

---

## پشتیبانی

https://github.com/hmplus28/tadarokat/issues