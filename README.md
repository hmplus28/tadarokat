# سامانه تدارکات

برنامهٔ تحت وب برای مدیریت درخواست‌های خرید، استعلام، دستور خرید و گزارش‌گیری.

**ریپو:** https://github.com/hmplus28/tadarokat

---

## فهرست مستندات

| سند | برای چه کسی | محتوا |
|-----|-------------|--------|
| **همین README** | همه — مخصوصاً تازه‌وارد | دریافت، نصب، اجرا، تست ساده |
| [راهنمای استقرار](docs/DEPLOYMENT.md) | IT / admin | شبکه، share، import اکسل، ویندوز |
| [معماری داده](docs/ARCHITECTURE.md) | توسعه‌دهنده / IT | DB، import، همزمانی، API سیستم |

**فایل‌های نمونه تنظیمات**

| فایل | توضیح |
|------|--------|
| [share.config.example.json](share.config.example.json) | مسیر پوشه share و پورت سرور |
| [share_users.seed.example.json](share_users.seed.example.json) | کاربران اولیه (قبل از `init_share`) |

**اسکریپت‌های پرکاربرد** → جزئیات در [DEPLOYMENT](docs/DEPLOYMENT.md#خلاصه)

| اسکریپت | کار |
|---------|-----|
| `install.bat` / [install.sh](install.sh) | نصب یک‌بار |
| `run.bat` / [run.sh](run.sh) | اجرای روزانه |
| [scripts/init_share.bat](scripts/init_share.bat) / [init_share.sh](scripts/init_share.sh) | راه‌اندازی اول share |
| [scripts/e2e_api_test.sh](scripts/e2e_api_test.sh) | تست خودکار API |

---

## چه چیزهایی لازم دارید؟

| مورد | توضیح |
|------|--------|
| **Python 3.9+** | [python.org](https://www.python.org/downloads/) — در ویندوز **Add Python to PATH** |
| **مرورگر** | Chrome، Edge یا Firefox |
| **اینترنت** | برای UI (CDN فونت و Tailwind) |

استقرار تیمی روی شبکه → [راهنمای استقرار](docs/DEPLOYMENT.md)

---

## مرحله ۱ — دریافت پروژه

### روش ساده (بدون Git)

1. https://github.com/hmplus28/tadarokat  
2. **Code** → **Download ZIP**  
3. Extract کنید (مثلاً `Documents\tadarokat`)  
4. باید `install.bat`، `run.bat` و پوشه `backend` را ببینید.

### با Git

```bash
git clone git@github.com:hmplus28/tadarokat.git
cd tadarokat
```

---

## مرحله ۲ — نصب (یک بار)

### ویندوز

1. پوشه پروژه را باز کنید.  
2. **`install.bat`** را اجرا کنید.  
3. تا «نصب کامل شد» صبر کنید.

برای تست لوکال، `share.config.json` خودکار ساخته می‌شود.  
برای شبکه: [DEPLOYMENT — تنظیم share](docs/DEPLOYMENT.md#it--یک-بار)

### لینوکس

```bash
chmod +x install.sh run.sh
./install.sh
```

---

## مرحله ۳ — اجرا

| سیستم | دستور |
|--------|--------|
| ویندوز | `run.bat` (پنجره را نبندید) |
| لینوکس | `./run.sh` |

مرورگر: **http://127.0.0.1:8000**

---

## مرحله ۴ — تست با مرورگر

### ورود

بعد از [راه‌اندازی share](docs/DEPLOYMENT.md#it--یک-بار) و seed کاربران:

| کاربر | رمز | نقش |
|-------|-----|-----|
| `admin` | `admin123` | مدیر سیستم |
| `manager` | `manager123` | مدیر تدارکات |
| `mostafa` | `mostafa123` | کارشناس |

ورود نشد؟ → `scripts\init_share.bat` و [share_users.seed.example.json](share_users.seed.example.json)

### چک‌لیست

- [ ] داشبورد باز می‌شود  
- [ ] **درخواست‌های خرید** لیست دارد  
- [ ] **🔄 آخرین داده** کار می‌کند  
- [ ] با `admin` → **پنل سیستم** ([جزئیات دکمه‌ها](docs/DEPLOYMENT.md#دکمه‌های-پنل))

---

## مرحله ۵ — تست API (اختیاری)

با سرور روشن:

```bash
# لینوکس / Git Bash
./scripts/e2e_api_test.sh
# یا
python3 scripts/e2e_api_test.py
```

باید خطوط `[OK]` ببینید.

---

## ساختار پروژه

```
tadarokat/
├── README.md                  ← شروع از اینجا
├── docs/
│   ├── DEPLOYMENT.md          ← استقرار شبکه
│   └── ARCHITECTURE.md        ← معماری DB و import
├── install.bat / install.sh
├── run.bat / run.sh
├── share.config.example.json
├── share_users.seed.example.json
├── backend/                   ← FastAPI
├── frontend/                  ← UI
└── scripts/                   ← init_share، import، تست
```

چرا `db_current.db` و نه مستقیم اکسل؟ → [معماری داده](docs/ARCHITECTURE.md)

---

## مشکلات رایج

| مشکل | راه‌حل |
|------|--------|
| صفحه باز نمی‌شود | `run.bat` + `http://127.0.0.1:8000` |
| `python` پیدا نشد | نصب Python + PATH |
| ورود نمی‌شود | [init_share](docs/DEPLOYMENT.md#it--یک-بار) + seed |
| داده قدیمی | **🔄 آخرین داده** یا [import اکسل](docs/DEPLOYMENT.md#دکمه‌های-پنل) |
| UI خراب | اینترنت + Ctrl+F5 |
| import / share | [عیب‌یابی استقرار](docs/DEPLOYMENT.md#عیب‌یابی) |

---

## مسیر یادگیری پیشنهادی

```
README (نصب و تست لوکال)
    ↓
DEPLOYMENT (شبکه و تیم)
    ↓
ARCHITECTURE (جزئیات فنی DB و API)
```

---

## پشتیبانی

Issue: https://github.com/hmplus28/tadarokat/issues