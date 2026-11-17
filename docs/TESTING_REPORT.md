# تقرير الاختبارات — BASIRA AI

هذا التقرير يوثّق **نتائج فعلية منفّذة** فقط. كل رقم هنا ناتج عن تشغيل حقيقي في بيئة التطوير:

- Debian 13 (trixie)، Python 3.12.15، CPU 5 أنوية، RAM 5.9GB، **بدون GPU**، بدون شاشة/كاميرا/ميكروفون (اختبارات الواجهة عبر `QT_QPA_PLATFORM=offscreen`).
- أمر التشغيل: `python3 -m pytest tests -v` (عبر ملف `pytest.ini`).

## 1. الملخص التنفيذي

| البند | القيمة الفعلية |
|---|---|
| إجمالي الاختبارات | **82** |
| ناجحة | **82** |
| فاشلة | 0 |
| متخطاة (skipped) | 0 |
| زمن التشغيل الكامل | 21.5 ثانية |
| آخر تشغيل | جلسة إصدار 0.1.0 |

## 2. التوزيع حسب الملف

| الملف | النوع | عدد الاختبارات | النتيجة |
|---|---|---|---|
| `tests/integration/test_desktop_ui.py` | تكامل (واجهة offscreen) | 9 | ✅ 9/9 |
| `tests/integration/test_orchestrator.py` | تكامل (طبقة الذكاء الموحدة) | 4 | ✅ 4/4 |
| `tests/integration/test_real_models.py` | تكامل (نماذج حقيقية) | 7 | ✅ 7/7 |
| `tests/integration/test_server.py` | تكامل (FastAPI) | 7 | ✅ 7/7 |
| `tests/unit/test_audio_logic.py` | وحدة | 7 | ✅ 7/7 |
| `tests/unit/test_database.py` | وحدة | 7 | ✅ 7/7 |
| `tests/unit/test_hardware.py` | وحدة | 9 | ✅ 9/9 |
| `tests/unit/test_intelligence.py` | وحدة | 9 | ✅ 9/9 |
| `tests/unit/test_privacy_sync.py` | وحدة | 7 | ✅ 7/7 |
| `tests/unit/test_sign_logic.py` | وحدة | 16 | ✅ 16/16 |

## 3. اختبارات النماذج الحقيقية (الأهم)

هذه الاختبارات تشغّل نماذج مدربة فعلياً (ليست محاكاة):

| الاختبار | ما يثبته فعلياً |
|---|---|
| `test_yolo_detects_real_image` | YOLOv8n ONNX يكتشف `person` و`bus` في صورة حقيقية (`tests/data/bus.jpg`) مع ثقة > 0.5 |
| `test_vision_engine_full_pipeline` | خط كامل: إطار → كشف + تحليل مكاني + وصف عربي/إنجليزي |
| `test_scene_description_arabic` | وصف عربي صحيح مبني على الكشف الفعلي (لا نص ثابت) |
| `test_ocr_english_rendered_text` | EasyOCR يقرأ نصاً إنجليزياً مرسومَا ("EXIT 2024") من صورة مولّدة |
| `test_hand_tracking_real_image` | MediaPipe يتتبع يد في صورة حقيقية (`thumb_up.jpg`) والمصنّف الهندسي يعيد `thumbs_up` بثقة ~0.85 |
| `test_stt_whisper_on_piper_speech` | اختبار دائري: Piper يولّد كلاماً عربياً → faster-whisper ينسخه ويكتشف اللغة `ar` |
| `test_tts_synthesis_deterministic` | Piper ينتج WAV صالحاً متسقاً (نفس الإدخال → نفس المخرجات) |

## 4. المقاييس المطلوبة في المواصفة — الحالة الصادقة

المواصفة تطلب مقاييس (mAP، WER، F1...). ما تم قياسه فعلياً وما لم يتم:

| المحرك | المقياس المطلوب | الحالة | ما تم فعله بدلاً منه |
|---|---|---|---|
| Object Detection | Precision/Recall/mAP | ❌ لم يُقيّم على مجموعة اختبار معيارية | تحقق وظيفي على صور حقيقية (person/bus) + اختبارات المعالجة اللاحقة (NMS, letterbox, clamp) |
| OCR | CER/WER | ❌ لم يُحسب على مجموعة معيارية | اختبار قراءة نص rendered واحد بنجاح |
| Sign Recognition | Accuracy/F1 | ❌ لا توجد بيانات تدريب | اختبارات وحدة على مصنّف هندسي بيد اصطناعية + صورة حقيقية thumbs_up |
| Sign Translation | WER + تقييم بشري | ❌ المفردات فارغة عمداً (لا بيانات يمنية) | — |
| Speech Recognition | WER | ❌ لم يُحسب WER على مجموعة معيارية | اختبار دائري Piper→Whisper يثبت الاتساق اللغوي (ar) |
| Sound Classification | Accuracy/F1 | ❌ المصنّف ONNX غير مدرّب؛ الوضع الحالي heuristic | اختبارات للبوابة الطاقية وكشف إنذار heuristic |
| Scene Understanding | تقييم بشري | ❌ لم يُجرَ | اختبارات أن الوصف مشتق من الكشف الفعلي |
| Desktop App | Latency/Stability | جزئي | قياسات زمن `_timed` لكل محرك متاحة في سجلات التشغيل؛ التطبيق يبدأ ويغلق بنظافة offscreen |

**السبب:** بيئة التطوير بلا GPU وبلا مجموعات بيانات محمّلة (قيود مساحة/زمن)، والتقييم المعياري يتطلب بيانات خارج النطاق. خطوط التدريب والتقييم موثقة في `docs/DATASETS.md` و`training/` لمن يريد إكمالها.

## 5. خريطة الاختبارات لقائمة "تعريف الاكتمال"

| بند DoD | الاختبارات المغطية |
|---|---|
| نافذة رئيسية / عربية / إنجليزية / RTL | `test_desktop_ui.py` (9 اختبارات offscreen تشمل تبديل اللغة والاتجاه) |
| كاميرا/ميكروفون (غياب آمن) | `test_hardware.py` (9 اختبارات تثبت رفض آمن مع HardwareUnavailableError) |
| إخراج صوتي | `test_tts_synthesis_deterministic` |
| اكتشاف الأشياء / وصف المشهد | `test_real_models.py` (YOLO + وصف) |
| OCR عربي/إنجليزي | `test_ocr_english_rendered_text` + EasyOCR محمّل بنموذجي ar+en |
| الأسئلة البصرية / العثور | `test_intelligence.py` + `test_orchestrator.py` (intent routing: find/read/count) |
| تتبع اليدين / الإشارات / الثقة | `test_hand_tracking_real_image` + `test_sign_logic.py` (16) |
| تحليل التسلسلات (DTW) | `test_sign_logic.py` (dtw_distance, cooldown, templates) |
| إضافة إشارات جديدة | `test_sign_logic.py` (dataset writer + consent إلزامي + split/augment) |
| تحويل الكلام إلى نص | `test_stt_whisper_on_piper_speech` |
| تصنيف الأصوات / التنبيهات | `test_audio_logic.py` (alerts cooldown, heuristic alarm, mel shape) |
| Connect | `test_orchestrator.py` (ConnectEngine مسارات sign→text→TTS وspeech→text) |
| قاعدة البيانات | `test_database.py` (7: migrate, settings, history, sync queue, wipe) |
| Backend + المصادقة | `test_server.py` (7: token, /health, /query, WS 4401) |
| المزامنة | `test_privacy_sync.py` (retry, max attempts, conflict) |
| الخصوصية | `test_privacy_sync.py` (no media default, purge, audit) |

## 6. بناء التطبيق (اختبار بناء حقيقي)

| البند | النتيجة الفعلية |
|---|---|
| PyInstaller (spec واحد لـ Linux/Windows) | ✅ نجح، exit 0 |
| الملف الناتج | `dist/BASIRA-AI` (ملف تنفيذي واحد) |
| الحجم | ~504 MB (يشمل torch عبر easyocr — راجع DEVELOPMENT_STATUS) |
| اختبار تشغيل الملف التنفيذي | ✅ يبدأ ويسجل `desktop app started (version 0.1.0)` ويغلق بنظافة (offscreen، مع libGL متاحاً) |

## 7. ما لم يُختبر (بصورة صريحة)

1. **كاميرا/ميكروفون حقيقيان** — البيئة بلا أجهزة. تم اختبار مسار الغياب الآمن فقط.
2. **مستخدمون حقيقيون** (مكفوفون/صم) — لم يُجرَ تقييم بشري.
3. **Windows/macOS** — لم يُبنَ التطبيق عليهما؛ سكربت `build_windows.bat` موجود لكن غير مُتحقق منه في هذه البيئة.
4. **مصنّف أصوات مدرّب** — الوضع الحالي heuristic (موثّق بوضوح في النتائج `heuristic=True`).
5. **الأداء على أجهزة متعددة** — قياس واحد فقط في بيئة واحدة.

## 8. إعادة إنتاج النتائج

```bash
cd BASIRA-AI
pip install -r requirements.txt
python scripts/download_models.py        # ينزّل النماذج ويتحقق من sha256
python -m pytest tests -v                # يجب أن يظهر: 82 passed
```

ملاحظة: اختبارات النماذج الحقيقية تتخطى نفسها تلقائياً برسالة واضحة إذا غاب النموذج (لا تفشل زوراً).
