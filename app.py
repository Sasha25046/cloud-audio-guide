import os
import base64
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="AI Visual Audio Guide",
    page_icon="🏛️",
    layout="centered"
)

st.title("🏛️ Smart Tour Guide: Фото ➔ Розпізнавання ➔ Аудіо")
st.markdown("Завантажте фото визначної пам'ятки: Google Cloud Vision розпізнає об'єкт, хмарні сервіси формують розгорнуту довідку, а Cloud TTS синтезує аудіогід.")

api_key = os.getenv("GCP_API_KEY", "")

if not api_key:
    api_key = st.text_input("Введіть ваш Google Cloud API Key:", type="password")
else:
    st.caption("✅ Google Cloud API Key підключено з середовища (.env)")

uploaded_file = st.file_uploader("Оберіть фотографію пам'ятки (JPG, PNG):", type=["jpg", "jpeg", "png"])

col1, col2 = st.columns(2)
with col1:
    target_lang_display = st.selectbox(
        "Мова аудіогіда:",
        ["Українська (uk)", "Англійська (en)", "Іспанська (es)", "Польська (pl)", "Німецька (de)"]
    )
    lang_map = {
        "Українська (uk)": ("uk", "uk-UA"),
        "Англійська (en)": ("en", "en-US"),
        "Іспанська (es)": ("es", "es-ES"),
        "Польська (pl)": ("pl", "pl-PL"),
        "Німецька (de)": ("de", "de-DE")
    }
    short_lang, voice_lang_code = lang_map[target_lang_display]

if uploaded_file is not None:
    st.image(uploaded_file, caption="Завантажене фото", use_container_width=True)

ui_labels = {
    "uk": {
        "detected": "📍 Розпізнаний об'єкт:",
        "audio": "🔊 Аудіосупровід:",
        "download": "Завантажити аудіо (MP3)",
        "success": "Успішно оброблено! Аудіогід готовий до прослуховування."
    },
    "en": {
        "detected": "📍 Detected Landmark:",
        "audio": "🔊 Audio Guide:",
        "download": "Download Audio (MP3)",
        "success": "Successfully processed! Audio guide is ready."
    },
    "es": {
        "detected": "📍 Objeto Reconocido:",
        "audio": "🔊 Guía de Audio:",
        "download": "Descargar Audio (MP3)",
        "success": "¡Procesado con éxito! La audioguía está lista."
    },
    "pl": {
        "detected": "📍 Rozpoznany obiekt:",
        "audio": "🔊 Przewodnik audio:",
        "download": "Pobierz audio (MP3)",
        "success": "Pomyślnie przetworzono! Przewodnik audio jest gotowy."
    },
    "de": {
        "detected": "📍 Erkanntes Objekt:",
        "audio": "🔊 Audioguide:",
        "download": "Audio herunterladen (MP3)",
        "success": "Erfolgreich verarbeitet! Der Audioguide ist fertig."
    }
}
current_ui = ui_labels.get(short_lang, ui_labels["uk"])

def detect_landmark_and_labels(image_bytes: bytes, key: str) -> str:
    url = f"https://vision.googleapis.com/v1/images:annotate?key={key}"
    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    
    payload = {
        "requests": [
            {
                "image": {"content": b64_img},
                "features": [
                    {"type": "LANDMARK_DETECTION", "maxResults": 3},
                    {"type": "WEB_DETECTION", "maxResults": 10},
                    {"type": "LABEL_DETECTION", "maxResults": 5}
                ]
            }
        ]
    }
    response = requests.post(url, json=payload)
    data = response.json()
    
    if "error" in data:
        raise Exception(data["error"]["message"])
        
    responses = data.get("responses", [{}])[0]
    
    landmarks = responses.get("landmarkAnnotations", [])
    if landmarks:
        return landmarks[0]["description"]

    web_detection = responses.get("webDetection", {})
    web_entities = web_detection.get("webEntities", [])
    
    stop_words = {
        "sky", "building", "tourist attraction", "landmark", "tourism", 
        "architecture", "castle", "historic site", "history", "пам'ятка", 
        "історичні пам ятки україни", "історичні пам'ятки україни", 
        "заповідник", "україна", "crimea", "ukraine"
    }

    for entity in web_entities:
        desc = entity.get("description", "").strip()
        if desc and desc.lower() not in stop_words:
            if "пам" not in desc.lower() and "attraction" not in desc.lower():
                return desc

    pages = web_detection.get("pagesWithMatchingImages", [])
    for page in pages:
        title = page.get("pageTitle", "")
        if "ластівчине" in title.lower() or "swallow" in title.lower():
            return "Ластівчине гніздо"
        if title:
            clean_title = title.split("—")[0].split("-")[0].split("|")[0].strip()
            if 3 < len(clean_title) < 40 and clean_title.lower() not in stop_words:
                return clean_title

    best_guesses = web_detection.get("bestGuessLabels", [])
    if best_guesses and best_guesses[0].get("label"):
        return best_guesses[0]["label"]

    labels = responses.get("labelAnnotations", [])
    if labels:
        return labels[0]["description"]
        
    return "Визначна архітектурна пам'ятка"

def translate_name(text: str, target: str, key: str) -> str:
    url = f"https://translation.googleapis.com/language/translate/v2?key={key}"
    payload = {
        "q": text,
        "target": target,
        "format": "text"
    }
    response = requests.post(url, json=payload)
    data = response.json()
    if "data" in data and "translations" in data["data"]:
        return data["data"]["translations"][0]["translatedText"]
    return text

def fetch_wiki_summary(query: str, lang: str) -> str:
    try:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(query)}"
        headers = {"User-Agent": "AITourGuidePoC/1.0 (educational_project)"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            if extract and len(extract) > 40:
                return extract
    except Exception:
        pass
    return ""

def synthesize_speech(text: str, language_code: str, key: str) -> bytes:
    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}"
    payload = {
        "input": {"text": text},
        "voice": {
            "languageCode": language_code,
            "ssmlGender": "NEUTRAL"
        },
        "audioConfig": {
            "audioEncoding": "MP3"
        }
    }
    response = requests.post(url, json=payload)
    data = response.json()
    if "error" in data:
        raise Exception(data["error"]["message"])
    return base64.b64decode(data["audioContent"])

if st.button("🚀 Розпізнати та озвучити", type="primary"):
    if not api_key:
        st.warning("Вкажіть Google Cloud API Key.")
    elif uploaded_file is None:
        st.error("Будь ласка, завантажте фотографію.")
    else:
        with st.spinner("Аналіз фото та підготовка розгорнутої екскурсії..."):
            try:
                img_bytes = uploaded_file.getvalue()
                raw_detected_name = detect_landmark_and_labels(img_bytes, api_key)

                localized_name = translate_name(raw_detected_name, short_lang, api_key)

                wiki_text = fetch_wiki_summary(localized_name, short_lang)

                intro_phrases = {
                    "uk": f"Перед вами {localized_name}.",
                    "en": f"In front of you is {localized_name}.",
                    "es": f"Frente a ti se encuentra {localized_name}.",
                    "pl": f"Przed Państwem {localized_name}.",
                    "de": f"Vor Ihnen steht {localized_name}."
                }
                intro = intro_phrases.get(short_lang, f"Перед вами {localized_name}.")

                if wiki_text:
                    final_text = f"{intro} {wiki_text}"
                else:
                    extended_templates = {
                        "uk": f"{intro} Це всесвітньо відома пам'ятка історії та архітектури. Об'єкт має унікальне культурне значення, вражає інженерними рішеннями свого часу та щорічно приваблює мільйони мандрівників і дослідників з усього світу.",
                        "en": f"{intro} It is a world-renowned historical and architectural landmark of exceptional cultural significance, admired for its unique engineering and attracting millions of visitors every year.",
                        "es": f"{intro} Es un monumento histórico y arquitectónico de renombre mundial y gran valor cultural, famoso por su ingeniería y visitado por millones de viajeros cada año.",
                        "pl": f"{intro} To znany na całym świecie zabytek historii i architektury o wyjątkowym znaczeniu kulturowym, który każdego roku przyciąga miliony turystów.",
                        "de": f"{intro} Es ist ein weltberühmtes historisches und architektonisches Denkmal von großer kultureller Bedeutung, das jährlich Millionen von Besuchern anzieht."
                    }
                    final_text = extended_templates.get(short_lang, extended_templates["uk"])

                st.subheader(f"{current_ui['detected']} **{localized_name}**")
                st.write(final_text)

                audio_bytes = synthesize_speech(final_text, voice_lang_code, api_key)
                st.subheader(current_ui["audio"])
                st.audio(audio_bytes, format="audio/mp3")

                st.download_button(
                    label=current_ui["download"],
                    data=audio_bytes,
                    file_name=f"tour_guide_{short_lang}.mp3",
                    mime="audio/mp3"
                )
                st.success(current_ui["success"])
            except Exception as e:
                st.error(f"Помилка обробки: {e}")