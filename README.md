# JARVIS MVP Prototype

Chat bot emas — Core + Memory + Voice + Internet + Android Actions
modullaridan tashkil topgan, kengaytiriladigan struktura.

## Loyiha tuzilishi

```
jarvis_mvp/
├── main.py                  # Kivy UI (chat log + mic tugma + matn input)
├── core/
│   ├── orchestrator.py       # Miya: intent -> routing -> memory
│   ├── llm_client.py         # Claude/GPT adapter (almashtiriladigan)
│   ├── memory.py              # SQLite xotira (conversation + facts)
│   └── search.py               # Internet qidiruv
├── android_layer/
│   ├── actions.py             # open_app, set_alarm, notify
│   └── voice.py                # TTS (ishlaydi) + STT (pastga qarang)
├── buildozer.spec
└── requirements.txt
```

## 1. Avval DESKTOP'da tekshirish (tavsiya etiladi)

APK yasashdan oldin, mantiqni kompyuteringizda tez tekshiring:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sizning_claude_api_kalitingiz"
export JARVIS_LLM_PROVIDER=claude
export SERPER_API_KEY="ixtiyoriy, internet qidiruv uchun"

python main.py
```

Bu holatda Android actions "[DESKTOP MODE]" deb ko'rsatadi (real telefon
bo'lmagani uchun), lekin butun Core/Memory/LLM zanjiri ishlaydi.

## 2. Android APK yasash

**MUHIM CHEKLOV:** Men (Claude) buni shu suhbat ichida siz uchun compile
qila olmayman — buildozer Android SDK/NDK'ni internetdan yuklab olishi
kerak, mening ishlash muhitimda esa tarmoq o'chirilgan. Shuning uchun
buni sizning tomoningizda (yoki quyidagi CI usulida) bajarishingiz kerak.

### Variant A — Linux / WSL'da (eng ishonchli)
```bash
pip install buildozer cython
sudo apt install -y openjdk-17-jdk unzip
buildozer android debug
```
Birinchi marta 20-40 daqiqa vaqt oladi (SDK/NDK yuklanadi). Natija:
`bin/jarvis-0.1-debug.apk`

### Variant B — GitHub Actions (kompyuteringizga hech narsa o'rnatmasdan)
Loyihani GitHub'ga yuklang, so'ng `.github/workflows/build.yml` orqali
`buildozer` action'ini ishlating (masalan `ArtemSBulgakov/buildozer-action`).
CI serverida internet bor, shuning uchun bu eng oson yo'l.

## 3. Ma'lum cheklovlar (keyingi iteratsiya uchun)

- **STT (ovozni matnga)**: hozircha faqat matn input orqali ishlaydi.
  Android native `SpeechRecognizer` async callback (Java thread bridge)
  talab qiladi — bu keyingi bosqichda `android_layer/voice.py` ichida
  `listen_once()` funksiyasini to'ldirish orqali qo'shiladi. Hozircha
  soxta ishlamoqda demay, ochiq qoldirdim.
- **TTS (matnni ovozga)**: ishlaydi, Android native TextToSpeech orqali.
- **Xavfsizlik/permission tizimi**: MVP'da yo'q — Automation/Phone Control
  kabi xavfli actionlar productionga chiqarilishidan oldin albatta
  qo'shilishi kerak (avvalgi arxitektura hujjatida ko'rsatilgan).

## Qo'shildi (2-bosqich): Ovozli, fonda ishlaydigan MVP

- **Wake word + davomiy suhbat**: `android_layer/voice.py` native
  `SpeechRecognizer`ga ulandi (`RecognitionListener` Java-Python
  ko'prigi orqali), `gateway/voice_gateway.py` esa "Jarvis" so'zini
  kutish -> "Yes?" -> buyruqni eshitish -> Orchestrator -> TTS
  aylanasini yuritadi (xuddi `CLIGateway` kabi, faqat ovoz orqali).
- **Foreground Service**: `service/main.py` + `android_layer/service_manager.py`
  + `buildozer.spec`dagi `services = jarvisvoice:service/main.py:foreground`.
  Ilova ochilganda `main.py` avtomatik shu xizmatni ishga tushiradi —
  mikrofon tugmasi YO'Q, qo'lda ishga tushirish YO'Q.
- **Android Controller kengaytirildi**: `android_layer/actions.py`ga
  `dial_number`, `send_sms`, `open_settings`, `set_flashlight`,
  `adjust_volume`, `media_control`, `get_device_contacts`,
  `launch_intent` qo'shildi. Har biri `core/adapters.py`da mos
  `IActionExecutor` orqali ro'yxatdan o'tgan (`call_contact`,
  `send_sms`, `open_settings`, `flashlight`, `volume`,
  `media_control`, `import_contacts`, `remember_contact`).
- **Xotira**: `core/memory.py`ga `contacts` va `command_history`
  jadvallar qo'shildi (kontaktlarni eslab qolish + oxirgi bajarilgan
  buyruqlarni LLM kontekstiga qo'shish).
- **Accessibility Service**: hali ISHLAMAYDI (loyiha ko'lami tashqarisida
  qoldirilgan), lekin `core/interfaces.py`dagi `IUIController` va
  `android_layer/accessibility.py` orqali arxitektura buni qo'llab-quvvatlaydi.

To'liq nima qilingani va keyingi sessiya nimadan boshlashi kerakligi
uchun **`HANDOVER.md`** ga qarang.

## Keyingi qadam

1. Loyihani real Android telefonda (yoki emulator) `buildozer android debug`
   bilan build qiling — bu qism tarmoq talab qiladi, shuning uchun
   Claude buni shu muhitda sinab ko'ra olmaydi.
2. `HANDOVER.md`dagi "Qurilmada tekshirish kerak" ro'yxatini bajaring
   (ayniqsa `_SERVICE_CLASS` nomi va wake-word aniqligi).
3. Keyingi navbatdagi katta modul: Accessibility Service (haqiqiy Java
   klassi kerak) — reja `android_layer/accessibility.py` ichida yozilgan.
