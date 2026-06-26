# راهنمای استقرار — سامانه تدارکات (ویندوز)

> همه سیستم‌ها **ویندوز** هستند. فایل‌های `.sh` فقط برای احتیاط نگه داشته شده‌اند.

---

## خلاصه

| مرحله | فایل | یک بار / هر روز |
|--------|------|-----------------|
| نصب | `install.bat` | یک بار هر PC |
| اجرا | `run.bat` | هر روز |
| راه‌اندازی share | `scripts\init_share.bat` | یک بار IT |
| import اکسل | پنل admin | هر بار که `input.xlsx` عوض شد |
| import خودکار | پنل admin | ساعت ۸ (قابل تغییر) |

---

## IT — یک بار

```cmd
copy share.config.example.json share.config.json
notepad share.config.json
install.bat
```

1. `shared_data_dir` = مسیر share شبکه، مثلاً:
   `\\server\share\tadarokat\data`
2. `share_users.seed.json` را در share بگذارید (از `share_users.seed.example.json`)
3. `scripts\init_share.bat`

---

## هر کاربر — یک بار

```cmd
install.bat
run.bat
```

مرورگر: `http://127.0.0.1:8000`

---

## دکمه‌های پنل

### همه کاربران (هدر صفحه)
**🔄 آخرین داده** — آخرین اطلاعات را از `db_current.db` مشترک می‌گیرد (بدون import اکسل)

### admin / IT (پنل سیستم)

| دکمه | کاربرد |
|------|--------|
| **اکسل را الان به دیتابیس import کن** | بعد از جایگزینی `input.xlsx` در share |
| **ذخیره زمان‌بندی** | ساعت import خودکار (پیش‌فرض ۸:۰۰) |
| **این PC مسئول import خودکار** | فقط یک PC IT — جلوگیری از import تکراری |

---

## یک DB — بدون تداخل

- همه `share.config.json` → **همان** `shared_data_dir`
- `db_current.db` **فقط روی share**
- `init_share` **فقط یک بار** توسط IT
- هر کلاینت فقط **می‌خواند**؛ import فقط از پنل admin

---

## لینوکس (احتیاط)

همان مراحل با `install.sh`، `run.sh`، `scripts/init_share.sh`

---

## عیب‌یابی

| مشکل | راه‌حل |
|------|--------|
| داده قدیمی | دکمه «آخرین داده» |
| اکسل جدید نیامده | admin → «اکسل را الان import کن» |
| import خودکار نزد | PC IT روشن + «این PC مسئول…» |