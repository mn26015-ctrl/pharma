# 💊 PharmAI — دليل الإعداد والنشر الكامل

## هيكل المشروع

```
pharmai/
├── app.py                    # نقطة الدخول الرئيسية
├── requirements.txt          # المكتبات المطلوبة
├── render.yaml               # إعداد Render
├── railway.toml              # إعداد Railway
├── Dockerfile                # للـ VPS
├── .streamlit/
│   └── config.toml           # إعداد Streamlit (ثيم + سيرفر)
└── src/
    ├── database.py           # قاعدة البيانات SQLite + كل العمليات
    ├── pdf_processor.py      # استخراج النص وتقسيمه
    ├── ai_generator.py       # Gemini API + Cache
    └── pages/
        ├── upload_page.py    # رفع PDF
        ├── daily_test_page.py # الاختبار اليومي
        ├── review_page.py    # مراجعة الأخطاء
        ├── question_bank_page.py # بنك الأسئلة
        └── dashboard_page.py # لوحة التقدم
```

---

## 1. تشغيل محلي (Local)

### المتطلبات
- Python 3.10+
- Git

### الخطوات

```bash
# 1. انشئ مجلد المشروع
mkdir pharmai && cd pharmai

# 2. أنشئ بيئة افتراضية
python -m venv venv
source venv/bin/activate       # macOS/Linux
# أو: venv\Scripts\activate   # Windows

# 3. ثبّت المكتبات
pip install -r requirements.txt

# 4. أضف مفتاح Gemini API
export GEMINI_API_KEY="your_key_here"
# Windows: set GEMINI_API_KEY=your_key_here

# 5. شغّل التطبيق
streamlit run app.py
```

افتح المتصفح على: **http://localhost:8501**

---

## 2. الحصول على Gemini API Key (مجاني)

1. اذهب إلى: **https://aistudio.google.com/app/apikey**
2. سجّل دخول بـ Google
3. اضغط "Create API Key"
4. انسخ المفتاح
5. الاستخدام المجاني: **1,500 request/day** بدون تكلفة

> ملاحظة: بدون مفتاح يعمل النظام بأسئلة تجريبية demo

---

## 3. النشر على Render (الأسهل)

### الخطوات:
1. ارفع الكود على GitHub
2. اذهب إلى **https://render.com** وسجّل حساب مجاني
3. اضغط "New Web Service"
4. اختر الـ repository
5. في إعدادات البناء:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
6. أضف Environment Variables:
   - `GEMINI_API_KEY` = مفتاحك
7. أضف Persistent Disk (لحفظ قاعدة البيانات):
   - Mount Path: `/var/data`
   - أضف `DB_PATH=/var/data/pharmai.db`
8. اضغط Deploy

**الرابط:** `https://pharmai-xxxx.onrender.com`

---

## 4. النشر على Railway

```bash
# 1. ثبّت Railway CLI
npm install -g @railway/cli

# 2. سجّل دخول
railway login

# 3. أنشئ مشروع جديد
railway new

# 4. أضف المتغيرات
railway variables set GEMINI_API_KEY=your_key

# 5. انشر
railway up
```

أو عبر الموقع: **https://railway.app** → New Project → Deploy from GitHub

---

## 5. النشر على VPS (Ubuntu)

```bash
# على السيرفر
sudo apt update && sudo apt install -y docker.io docker-compose

# ارفع الكود
git clone https://github.com/yourusername/pharmai
cd pharmai

# ابنِ وشغّل
docker build -t pharmai .
docker run -d \
  -p 8501:8501 \
  -v /opt/pharmai-data:/data \
  -e GEMINI_API_KEY=your_key \
  --name pharmai \
  --restart unless-stopped \
  pharmai

# تأكد أنه يعمل
docker ps
```

ثم ضع Nginx Reverse Proxy:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

---

## 6. إضافة إلى الهاتف كـ PWA

بعد النشر، يمكن إضافة الموقع كتطبيق من المتصفح:

**iOS (Safari):**
1. افتح الرابط في Safari
2. اضغط زر المشاركة ↑
3. اختر "إضافة إلى الشاشة الرئيسية"

**Android (Chrome):**
1. افتح الرابط في Chrome
2. اضغط القائمة (⋮)
3. اختر "إضافة إلى الشاشة الرئيسية"

---

## 7. استراتيجية تقليل التكلفة

النظام يطبق 5 طبقات لتوفير التكلفة:

| الطبقة | الوصف |
|--------|-------|
| **Hash Dedup** | نفس الـ PDF لن يُعالج مرتين أبداً |
| **Chunk Cache** | نفس النص → نفس الأسئلة من Cache |
| **DB Cache** | كل نتائج AI محفوظة في SQLite |
| **Reuse First** | الأسئلة الموجودة تُعاد قبل توليد جديد |
| **Flash Model** | Gemini Flash أرخص بـ 10x من Pro |

**التكلفة التقديرية:**
- 100 صفحة PDF → ~300 API call → ~0.03$ (تقريبًا)
- بعد أول تحليل: **0$ للأسئلة ذاتها**

---

## 8. قاعدة البيانات

النظام يستخدم SQLite (ملف واحد `pharmai.db`):

```
pdf_documents  → تتبع الملفات المرفوعة + hash
chunks         → تقسيمات النص (dedup بـ content_hash)
questions      → كل الأسئلة المولدة
answers        → سجل إجابات المستخدم
review_schedule → جدول المراجعة المتباعدة (SM-2)
user_performance → إحصائيات يومية
cache_store    → cache استجابات Gemini
```

---

## 9. خوارزمية المراجعة المتباعدة (SM-2)

```
إجابة صحيحة سهلة → interval × 2.5 (مراجعة بعد فترة أطول)
إجابة صحيحة صعبة → interval × 1.5
إجابة خاطئة       → interval = 1 يوم (راجعها غداً)
```

---

## 10. استكشاف الأخطاء

**خطأ PDF:** جرّب تثبيت `pdfplumber`: `pip install pdfplumber`

**خطأ Gemini 429:** تجاوزت الحد المجاني اليومي — انتظر أو استخدم مفتاحاً آخر

**البيانات لا تُحفظ على Render:** تأكد من إضافة Persistent Disk وضبط `DB_PATH`

**تطبيق بطيء:** طبيعي في الـ Free Plan (cold start 30-60 ثانية)
