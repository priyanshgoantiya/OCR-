# app_excel.py
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
import json

st.set_page_config(page_title="Excel → Gemini (multi-prompt OCR)", layout="wide")
st.title("📊 Excel → Gemini — multi-prompt extractor")

uploaded = st.file_uploader("Upload Excel", type=["xlsx"])
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
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-exp-1206"
    ],
    index=0,
    help="Best models: gemini-2.0-flash-exp, gemini-2.5-flash"
)

if not uploaded:
    st.info("Upload an Excel file.")
    st.stop()

if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

# ✅ Read only the 3rd sheet
try:
    xls = pd.ExcelFile(uploaded)
    sheet_name = xls.sheet_names[2]  # 3rd sheet (0-indexed)
    df = pd.read_excel(xls, sheet_name=sheet_name)
except Exception as e:
    st.error(f"❌ Failed to read 3rd sheet: {e}")
    st.stop()

# Convert the sheet into text for Gemini
text_data = df.to_string(index=False)

# Initialize Gemini
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Your same medication extraction prompt
hospital_course_prompt = """
TASK:
You are a licensed medical practitioner and clinical reviewer. From a medical document (digital, scanned, or handwritten), extract the Hospital Course / Clinical Summary paragraph and the two doctor names. Produce a single **plain text** sentence that follows the exact template below, changing only the two doctor names:

Template (exact output format required):
Patient was admitted with above mentioned complaints and history. All relevant laboratory investigations done (Reports attached to the file). General condition and vitals of the patient closely monitored. Daily consulted by Dr. <SURGEON_OR_DAILY_DOCTOR_NAME>. Fitness for surgery given by Dr. <CONSULTANT_PHYSICIAN_NAME> (Consultant Physician). All preoperative assessment done, patient taken up for surgery.

RULES — what to extract and how:
1. Locate the Hospital Course / Clinical Summary section using tolerant heading matches such as:
   - "Hospital Course", "HospitalCourse", "Clinical Summary", "Clinical Course", "Course in Hospital", "Hospital Course / Clinical Summary"
   Capture the paragraph(s) belonging to that section and use the template above (do NOT change its text except for the two doctor names).

2. Surgeon / Daily consulted doctor (insert as <SURGEON_OR_DAILY_DOCTOR_NAME>):
 - Labels: "Admitting Doctor", "Admitting Dr", "Admitting Doctor :"
 - Capture name exactly. If registration number appears on same line/in parentheses, omit it from this field.
 - If multiple candidate names appear, choose the name closest to the hospital-course or operative header. If still ambiguous or illegible, use "Dr. NOT_FOUND".

3. Consultant Physician (insert as <CONSULTANT_PHYSICIAN_NAME>):
   - Search labels: "Consultant Physician:", "Consultant:", "Consultant Dr", "Consultant Physician"
   - Output exactly as "Dr. <Full Name>" inside the template, then append " (Consultant Physician)" as shown.
   - If multiple candidates or illegible, use "Dr. NOT_FOUND".

4. Handwriting & OCR:
   - Attempt verbatim transcription where readable. If handwriting or OCR is low-confidence for a name, prefer "Dr. NOT_FOUND" rather than guessing.
   - Strip registration numbers, material codes, or trailing parenthetical codes from extracted names.

5. Strict output rule:
   - Return **only one line** of plain text matching the Template exactly (with the two doctor names filled in).
   - Do NOT output JSON, page numbers, notes, confidence, or any additional text or commentary.
   - Example valid output (only this single-line sentence is allowed):
     Patient was admitted with above mentioned complaints and history. All relevant laboratory investigations done (Reports attached to the file). General condition and vitals of the patient closely monitored. Daily consulted by Dr. Sahil Kiran Pethe. Fitness for surgery given by Dr. Vineet Rao (Consultant Physician). All preoperative assessment done, patient taken up for surgery.

If a required doctor name is not found/confidently readable, insert "Dr. NOT_FOUND" in that position (still return the single-line sentence).
END TASK.
"""


# Define prompt dictionary
prompts = {
    "hospital_course_prompt": hospital_course_prompt
}

combined_output = {}

with st.spinner("Processing Excel data..."):
    for section_name, prompt_text in prompts.items():
        try:
            # ✅ Send as plain text instead of file
            response = client.models.generate_content(
                model=f"models/{model_option}",
                contents=[prompt_text, text_data]
            )
            text = (response.text or "").strip() if response else ""
            if not text:
                st.warning(f"No response for {section_name}")
                combined_output[section_name] = "NOT_FOUND"
                continue

            try:
                parsed = json.loads(text)
                st.json(parsed)
                combined_output[section_name] = parsed
            except json.JSONDecodeError:
                st.warning(f"{section_name} output is not valid JSON")
                st.code(text)
                combined_output[section_name] = {"raw_text": text}

        except Exception as e:
            st.error(f"Error during extraction: {e}")
            combined_output[section_name] = {"error": str(e)}

st.success(f"✅ Extraction completed using {model_option}!")
st.json(combined_output)

st.download_button(
    "💾 Download All Results (Combined JSON)",
    data=json.dumps(combined_output, indent=2),
    file_name="combined_extracted_data.json",
    mime="application/json"
)


