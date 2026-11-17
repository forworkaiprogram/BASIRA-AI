# SYSTEM ARCHITECTURE — BASIRA AI Desktop

## Decision: PySide6 / Qt (Option B)

| المعيار | Flutter Desktop | **PySide6/Qt** | Tauri | Electron |
|---|---|---|---|---|
| تكامل Python المباشر | عبر FFI/خدمة منفصلة | **داخلي بالكامل** | خدمة جانبية | خدمة جانبية |
| الكاميرا/الميكروفون | plugins متفاوتة | **OpenCV/sounddevice مباشرة** | WebView APIs | WebView APIs |
| استهلاك الذاكرة | متوسط | **منخفض-متوسط** | منخفض | مرتفع |
| دعم RTL/العربية | جيد | **ممتاز (Qt LayoutDirection)** | جيد | جيد |
| قارئات الشاشة | جيد | **QAccessible (Orca/NVDA)** | جيد | جيد |
| ملفات التثبيت | جيد | **PyInstaller/NSIS** | جيد | جيد |

السبب الحاسم: كل محركات AI مكتوبة بـ Python؛ واجهة Qt داخل نفس العملية تزيل
طبقة IPC كاملة، وتدعم RTL وقارئات الشاشة أصلاً.

## الطبقات

```
Desktop Presentation Layer (basira/desktop)     ← PySide6, 9 صفحات
        ↓ QThread workers (basira/worker)
Application Controller (basira/desktop/main_window)
        ↓
Unified Intelligence Layer (basira/intelligence)
   ├── ContextManager   سياق المحادثة المشترك
   ├── MultimodalFusion دمج النتائج + كشف التعارضات
   ├── ModeRouter       توجيه الطلب للوضع والمحركات
   ├── BASIRACore       نقطة الدخول الموحدة (UI وBackend معاً)
   └── AccessibilityManager (profiles في DB)
        ↓
Engines (basira/engines) — مستقلة عن الواجهة، lazy-loading
   ├── vision/   ObjectDetector (YOLOv8n ONNX), OcrEngine (EasyOCR),
   │             SpatialAnalyzer, SceneDescriptor (وصف/VQA قائم على الأدلة)
   ├── sign/     HandTracker (MediaPipe), static gestures (هندسية),
   │             SequenceRecognizer (DTW), dataset tools
   ├── audio/    SpeechRecognizer (faster-whisper), SoundEventDetector,
   │             AlertManager (cooldown/dedup)
   ├── language/ TextToSpeech (Piper ONNX عربي)
   └── connect/  سيناريوهات المحادثة الثلاثة
        ↓
Local AI Runtime
   ├── Model Registry (جدول model_registry + scripts/download_models.py)
   ├── SQLite (basira/db) — WAL, thread-local connections
   └── Offline Sync (basira/sync) — queue/retry/conflict
        ↓
Optional Cloud Services (معطلة افتراضياً)
```

## قواعد معمارية

1. **المحركات لا تعرف شيئاً عن Qt.** أي واجهة مستقبلاً (Android/Web) تعيد
   استخدامها كما هي.
2. **Lazy loading:** لا يُحمَّل نموذج إلا عند أول استخدام؛ بدء التطبيق < ثوانٍ.
3. **Degradation صريح:** كل محرك يعلن حالته (ready/unavailable/error) والواجهة
   تعرضها بدلاً من الانهيار.
4. **الاستدلال خلف QThread** — الواجهة لا تتجمد أبداً.
5. **الخدمة المحلية اختيارية:** الاتصال الداخلي المباشر هو الافتراضي؛ FastAPI
   فقط لعملاء خارجيين (loopback + توكن).

## تدفق طلب نموذجي

```
"أين الهاتف؟" → ModeRouter(vision/find) → CameraManager.latest_frame()
→ ObjectDetector.detect → SpatialAnalyzer → SceneDescriptor.answer_question
→ CoreResponse(text, confidence) → ContextManager → TTS → السماعة
```
