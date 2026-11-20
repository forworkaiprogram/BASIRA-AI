# BASIRA AI — Universal Multimodal Accessibility Intelligence

منصة ذكاء اصطناعي متعددة الوسائط **لتطبيق سطح المكتب** تساعد المكفوفين والصم وضعاف
البصر والسمع على فهم العالم المحيط والتواصل مع الآخرين. تعمل محلياً على الحاسوب
دون إنترنت قدر الإمكان.

**الحالة الحالية: نسخة أولى عاملة (v0.1.0) — انظر [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) لما تم تنفيذه واختباره فعلياً وما لم يكتمل بعد.**

---

## الأوضاع الأربعة

| الوضع | الوظيفة | الحالة |
|---|---|---|
| **BASIRA VISION** | كشف الأجسام، وصف المشهد صوتياً، OCR عربي/إنجليزي، أسئلة بصرية، تنبيهات عوائق | يعمل (YOLOv8n ONNX + EasyOCR + وصف قائم على النتائج) |
| **BASIRA SIGN** | تتبع اليدين، إيماءات ثابتة، إشارات حركية (DTW)، تسجيل مفردات جديدة بموافقة المستخدم | تتبع اليد + إيماءات ثابتة يعمل؛ مفردات ArSL تحتاج جمع بيانات |
| **BASIRA HEAR** | كلام إلى نص (Whisper)، كشف أصوات بيئية، تنبيهات مرئية مع منع التكرار | يعمل (whisper-base + بوابة طاقة + كاشف إنذار طيفي) |
| **BASIRA CONNECT** | محادثة بين أصم وغير أصم: إشارة→نص→كلام، كلام→نص | يعمل عبر المحركات أعلاه |

## التشغيل السريع (Linux)

```bash
# 1) الاعتماديات
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# لينكس فقط: ملفات النظام
sudo apt install libportaudio2 libgl1 libgles2 libegl1

# 2) النماذج (تنزيل لمرة واحدة، ~250MB)
python scripts/download_models.py

# 3) التشغيل
python scripts/run_desktop.py
```

Windows: نفس الخطوات بدون حزم apt؛ استخدم `deployment/build_windows.bat` لبناء ملف exe.

## البنية

```
basira/
├── desktop/       واجهة PySide6 (RTL عربي / LTR إنجليزي، 3 سمات، تكبير نص)
├── hardware/      كاميرا/ميكروفون/سماعات مع إغلاق آمن ومعالجة انقطاع
├── engines/       vision | sign | audio | language | connect (مستقلة عن الواجهة)
├── intelligence/  Context Manager, Multimodal Fusion, Router, Orchestrator
├── db/            SQLite: 13 جدولاً (users, sessions, history, models, sync…)
├── privacy/       لا حفظ وسائط افتراضياً + حذف شامل مدوّن
├── sync/          طابور مزامنة محلي مع retry وconflict resolution
└── server/        خدمة FastAPI محلية (127.0.0.1 فقط + توكن bearer)
```

المحركات مستقلة عن الواجهة تماماً — قابلة لإعادة الاستخدام في تطبيقات
الهاتف/الويب مستقبلاً دون تغيير (انظر [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)).

## البنية الكاملة في [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md).

## التشغيل في المتصفح (GitHub Codespaces)

المستودع جاهز لـ Codespaces: افتح المستودع → زر **Code** → تبويب **Codespaces** → **Create codespace**. سيُثبّت المتطلبات والنماذج ويشغّل الاختبارات تلقائياً، وتظهر واجهة Qt في تبويب متصفح عبر noVNC (منفذ 6080). **قيود مهمة:** كاميرا وميكروفون جهازك لا يصلان إلى البيئة السحابية، لذا الأوضاع الحية (VISION المباشر / SIGN / HEAR) تعمل فقط على جهازك المحلي — في Codespaces استخدم الخدمة المحلية (`scripts/run_server.py`) لإرسال صور وتحليلها.

## الوثائق

| المستند | المحتوى |
|---|---|
| [SYSTEM_ARCHITECTURE](docs/SYSTEM_ARCHITECTURE.md) | البنية والطبقات ومقارنة تقنيات سطح المكتب |
| [INSTALLATION](docs/INSTALLATION.md) | التثبيت والمتطلبات |
| [USER_GUIDE](docs/USER_GUIDE.md) | دليل الاستخدام لكل وضع |
| [API_DOCUMENTATION](docs/API_DOCUMENTATION.md) | الخدمة المحلية وWebSocket |
| [DATASETS](docs/DATASETS.md) | مجموعات البيانات وخطوط التدريب |
| [MODEL_CARDS](docs/MODEL_CARDS.md) | بطاقات النماذج والتراخيص والقيود |
| [PRIVACY_POLICY](docs/PRIVACY_POLICY.md) | الخصوصية وحماية البيانات |
| [TESTING_REPORT](docs/TESTING_REPORT.md) | نتائج الاختبارات الفعلية (82 اختباراً) |
| [DEPLOYMENT_GUIDE](docs/DEPLOYMENT_GUIDE.md) | البناء والنشر والتشغيل |
| [DEVELOPMENT_STATUS](docs/DEVELOPMENT_STATUS.md) | ما اكتمل وما لم يكتمل (بصدق) |

## الاختبارات

```bash
python -m pytest            # 82 اختباراً (وحدة + تكامل)
```

تشمل اختبارات تكامل تعمل **بنماذج حقيقية**: كشف شخص/حافلة في صورة COCO،
تتبع يد حقيقية وتصنيف thumbs_up، OCR لنص مرسوم، تحويل نص عربي إلى كلام
بـ Piper ثم تفريغه بـ Whisper، وخدمة FastAPI بمصادقة كاملة.

## الأمان والخصوصية

- الخدمة المحلية على `127.0.0.1` فقط، مع توكن يُولَّد تلقائياً.
- لا تُحفظ الصور أو الصوت افتراضياً؛ زر "حذف جميع بياناتي" يمحو كل شيء ويسجل العملية.
- المعالجة محلية 100% افتراضياً؛ السحابة معطلة حتى يفعّلها المستخدم.

## ملاحظة سلامة

بصيرة AI مساعد تقني وليس بديلاً عن العصا البيضاء أو أدوات السلامة المعتمدة.
عدم اكتشاف جسم لا يعني عدم وجوده، ولا تُقدَّم مسافات دقيقة دون مستشعر قياس.
