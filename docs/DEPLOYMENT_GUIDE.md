# دليل النشر والتشغيل — BASIRA AI

هذا الدليل يغطي: تشغيل التطبيق من المصدر، بناء الملف التنفيذي، تشغيل الخدمة المحلية الاختيارية، وما تم بناؤه فعلياً مقابل ما هو سكربتات غير مُتحقق منها.

## 1. متطلبات النظام

| البند | الحد الأدنى الفعلي (مُختبر) | موصى به |
|---|---|---|
| نظام التشغيل | Linux x86_64 (مُختبر على Debian 13) | Windows 10/11، Linux، macOS |
| Python | 3.10+ (مُختبر على 3.12) | 3.12 |
| RAM | 4 GB (مُختبر على 5.9 GB بلا GPU) | 8 GB |
| المعالج | 4 أنوية | 6+ أنوية أو GPU اختياري |
| القرص | ~2 GB (كود + نماذج 87MB + أرشيفات) | 4 GB |
| كاميرا | اختيارية (V4L2 على لينكس / DirectShow على ويندوز) | 720p |
| ميكروفون | اختياري (PortAudio) | — |
| مكتبات نظام (لينكس) | `libgl1`, `libegl1`, `libxcb1`, `libportaudio2` | + `libxkbcommon-x11-0` |

## 2. التشغيل من المصدر (Linux)

```bash
# 1) الحصول على الكود
git clone <repo-url> && cd BASIRA-AI

# 2) بيئة افتراضية وتثبيت
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) مكتبات النظام على Debian/Ubuntu (تحتاج صلاحيات sudo)
sudo apt install -y libgl1 libegl1 libxcb1 libportaudio2 libxkbcommon-x11-0

# 4) تنزيل النماذج (87MB، مع تحقق sha256)
python scripts/download_models.py

# 5) تشغيل التطبيق
python run_desktop.py
```

## 3. بناء الملف التنفيذي

### Linux (مُتحقق منه فعلياً ✅)

```bash
pip install pyinstaller
pyinstaller deployment/basira.spec --noconfirm
# الناتج: dist/BASIRA-AI  (ملف تنفيذي واحد، ~504 MB في بنائنا)
./dist/BASIRA-AI
```

نتيجة البناء الفعلية في بيئة التطوير: نجح بـ exit 0، والملف التنفيذي بدأ وسجّل `desktop app started (version 0.1.0)` وأغلق بنظافة.

ملاحظات مهمة عن الناتج:
- **النماذج غير مضمّنة** في الملف التنفيذي عمداً (يقلّل الحجم ويتيح تحديث النماذج مستقلاً). عند أول تشغيل ضع النماذج في `~/.basira/models/` عبر `scripts/download_models.py`.
- المواصفة تضمّن تلقائياً `libGL/libEGL` إن وجدت في النظام (بحث في LD_LIBRARY_PATH ومجلدات النظام)، وإلا فعليك تثبيت `libgl1`.
- الحجم الكبير (504MB) سببه torch المُجلب مع easyocr. تحسين مستقبلي: استبدال EasyOCR بمحرّك OCR على ONNX خالص لخفض الحجم إلى ما دون 200MB.

### Windows (سكربت جاهز، غير مُتحقق عليه ❌)

```bat
build_windows.bat
```

السكربت ينفّذ نفس الخطوات (venv + pip + pyinstaller + spec). لم يُنفَّذ في بيئة التطوير (لينكس) — لا تُعتبر حزمة ويندوز جاهزة قبل تنفيذه واختباره على ويندوز فعلياً.

## 4. التثبيت كتطبيق سطح مكتب (Linux)

لا يوجد Installer (DEB/RPM/AppImage) في هذه المرحلة — هذا **قيد موثّق بصدق**. الطريقة المدعومة حالياً:

```bash
# انسخ الملف التنفيذي والنماذج:
mkdir -p ~/.basira/models
cp dist/BASIRA-AI ~/bin/basira-ai
python scripts/download_models.py --target ~/.basira/models
# أنشئ اختصار سطح مكتب يدوياً إن رغبت (Exec=~/bin/basira-ai)
```

الملفات تُكتب في `~/.basira/` (قاعدة البيانات، السجلات، الإعدادات، مجموعات بيانات الإشارات). يمكن تغيير الموقع بمتغير البيئة `BASIRA_HOME`.

## 5. الخدمة المحلية الاختيارية (Backend)

```bash
# تشغيل الخدمة على 127.0.0.1 فقط (لا تُكشف للشبكة)
python run_server.py --show-token   # يطبع رمز Bearer عند أول تشغيل
```

- كل النقاط (عدا `/health`) تتطلب `Authorization: Bearer <token>`.
- WebSocket: `ws://127.0.0.1:8765/ws?token=<token>`، يُغلق برمز 4401 عند فشل المصادقة.
- الوثائق الكاملة: `docs/API_DOCUMENTATION.md`.

## 6. سكربتات مساعدة

| السكربت | الوظيفة |
|---|---|
| `scripts/download_models.py` | تنزيل كل النماذج مع تحقق sha256 وتصدير YOLO إلى ONNX |
| `scripts/export_yolo_onnx.py` | تصدير/إعادة تصدير YOLOv8n إلى ONNX |
| `scripts/enroll_sign.py` | تسجيل إشارة جديدة (يتطلب `--consent-id` إلزامياً) |
| `scripts/make_icon.py` | توليد أيقونات التطبيق (PNG/ICO) |
| `run_desktop.py` | نقطة تشغيل واجهة سطح المكتب |
| `run_server.py` | نقطة تشغيل الخدمة المحلية |

## 7. السجلات ومعالجة الأعطال

- السجلات: `~/.basira/logs/basira.log` (تدوير تلقائي) + مخرجات console.
- الأعطال غير المتوقعة تُلتقط في `sys.excepthook` وتُسجَّل قبل الإغلاق الآمن.
- إغلاق التطبيق يمر عبر `closeEvent` → إيقاف مؤشرات الواجهة → `DeviceManager.shutdown()` → إغلاق قاعدة البيانات.

## 8. قائمة تحقق ما بعد التثبيت

1. شغّل التطبيق — يجب أن تظهر نافذة البداية ثم لوحة التحكم.
2. صفحة "النماذج": تحقق أن YOLO/OCR/Whisper/Piper/MediaPipe تظهر بحالة ready (أو unavailable مع سبب).
3. لوحة التحكم: شرائح حالة الكاميرا والميكروفون تعكس الواقع.
4. إن كانت كل النماذج unavailable: أعد تشغيل `scripts/download_models.py` وتحقق من `~/.basira/models/`.
