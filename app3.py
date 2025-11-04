# app_pdf.py
import streamlit as st
from google import genai
from google.genai import types
from pdf2image import convert_from_bytes
import json
import io

st.set_page_config(page_title="PDF → Gemini Hospital Course Extractor", layout="wide")
st.title("🏥 PDF → Gemini — Hospital Course Extractor")

uploaded = st.file_uploader("Upload PDF File", type=["pdf"])
api_key = st.text_input(
    "Paste Gemini API key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

model_option = st.selectbox(
    "Select Gemini Model",
    [
        "gemini-2.0-flash-exp",
        "gemini-2.5-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash"
    ],
    index=0
)

if not uploaded:
    st.info("Please upload a PDF file.")
    st.stop()

if not api_key.strip():
    st.warning("Please enter your Gemini API key to proceed.")
    st.stop()

# ✅ Configure Gemini client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"❌ Failed to initialize Gemini client: {e}")
    st.stop()

# 🧠 Your clinical extraction prompt
hospital_course_prompt = """
You are a licensed medical practitioner and clinical reviewer. From this medical document (digital, scanned, or handwritten), extract the Hospital Course / Clinical Summary paragraph and the two doctor names. 

Produce a single **plain text** sentence that follows this exact format, changing only the two doctor names:

Patient was admitted with above mentioned complaints and history. All relevant laboratory investigations done (Reports attached to the file). General condition and vitals of the patient closely monitored. Daily consulted by Dr. <SURGEON_OR_DAILY_DOCTOR_NAME>. Fitness for surgery given by Dr. <CONSULTANT_PHYSICIAN_NAME> (Consultant Physician). All preoperative assessment done, patient taken up for surgery.

RULES:
- Identify “Hospital Course” or “Clinical Summary” section.
- Replace only the two doctor names in the sentence above.
- Surgeon/Daily Doctor:
  * Labels: "Admitting Doctor", "Surgeon", "Daily consulted by"
  * Format: Dr. <Full Name>
- Consultant Physician:
  * Labels: "Consultant Physician", "Consultant Dr"
  * Format: Dr. <Full Name> (Consultant Physician)
- If name not found or unreadable → use “Dr. NOT_FOUND”.
- Do NOT output anything else.
- Output this single line as plain text.

Additionally, return the same information in JSON format:
{
  "hospital_course_text": "<above sentence>",
  "surgeon_name": "<name>",
  "consultant_physician_name": "<name>"
}
END TASK.
"""

st.divider()
st.subheader("🧠 Running Hospital Course Extraction...")

# ✅ Convert PDF pages to images
images = convert_from_bytes(uploaded.read())
st.info(f"Extracting from {len(images)} page(s)...")

all_results = []
with st.spinner("Processing with Gemini..."):
    for i, img in enumerate(images):
        st.write(f"📄 Processing Page {i+1}...")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        try:
            response = client.models.generate_content(
                model=f"models/{model_option}",
                contents=[hospital_course_prompt, types.Part.from_bytes(img_bytes.read(), mime_type="image/png")]
            )

            text = (response.text or "").strip()
            st.markdown(f"### 🧾 Page {i+1} Output (Text)")
            st.write(text)

            try:
                parsed_json = json.loads(text)
                st.markdown(f"### 📦 Page {i+1} JSON")
                st.json(parsed_json)
                all_results.append(parsed_json)
            except json.JSONDecodeError:
                # If plain text only, wrap it into JSON
                all_results.append({"hospital_course_text": text})

        except Exception as e:
            st.error(f"Error on page {i+1}: {e}")
            all_results.append({"error": str(e)})

# ✅ Final combined output
combined_json = json.dumps(all_results, indent=2)
st.divider()
st.success(f"✅ Extraction completed successfully using {model_option}!")
st.json(all_results)

# Download JSON
st.download_button(
    "💾 Download Extracted Results (JSON)",
    data=combined_json,
    file_name="hospital_course_extraction.json",
    mime="application/json"
)


