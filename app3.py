# app.py
import streamlit as st
from google import genai
from google.genai import types
import json
import os

st.set_page_config(page_title="Excel → Gemini (Treatment Given extractor)", layout="wide")
st.title("📄 Excel → Gemini — Treatment Given extractor")

uploaded = st.file_uploader("Upload Excel (.xlsx/.xls)", type=["xlsx", "xls"])
api_key = st.text_input("Paste Gemini API key", type="password")

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
    index=0
)

if not uploaded:
    st.info("Upload an Excel file (.xlsx or .xls).")
    st.stop()

if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

file_bytes = uploaded.read()

# infer mime type for Excel
filename = uploaded.name or "file.xlsx"
ext = os.path.splitext(filename)[1].lower()
if ext == ".xlsx":
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
elif ext == ".xls":
    mime = "application/vnd.ms-excel"
else:
    # fallback
    mime = "application/octet-stream"

# initialize client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Keep your same prompt (adjusted to mention Excel / sheet name)
medication_extraction_prompt = """
TASK:
You are a licensed medical practitioner and clinical pharmacist reviewing hospital treatment records from an Excel workbook. Extract ONLY pharmaceutical medications from the sheet named exactly "Treatment Given" (the 3rd sheet in the workbook). Exclude all medical consumables, supplies, and non-medication items.

# CONTEXT & MINDSET:
- Approach this as a trained pharmacist conducting medication reconciliation.
- Focus on therapeutic agents with pharmacological action.
- Maintain precision and accuracy in medication identification.

# EXTRACTION RULES:
(Use the same INCLUDE / EXCLUDE rules as provided previously.)
- INCLUDE medications (tablets, injections, syrups, respules, inhalers, IV meds, ointments with API, therapeutic supplements like albumin).
- EXCLUDE consumables & supplies (implants, sutures, plain IV fluids without added drug, instruments, dressings, plain water for injection, etc).

# IMPORTANT:
- Look for the column named "DRUG / IMPLANT NAME" in the "Treatment Given" sheet.
- Extract medication names exactly as they appear.
- Remove duplicates (list each medication once).
- Preserve brand and generic names in parentheses when present.
- Do NOT extract material codes or non-pharma items.

# OUTPUT FORMAT:
Return ONLY this JSON structure (valid JSON):
{
  "medications_extracted": [
    "MEDICATION NAME 1",
    "MEDICATION NAME 2"
  ],
  "consumables_excluded": [
    "CONSUMABLE ITEM 1",
    "CONSUMABLE ITEM 2"
  ],
  "total_medications_count": <number>,
  "total_consumables_excluded_count": <number>
}

Extract medications now from the provided Excel workbook's "Treatment Given" sheet.
"""

# single request: send Excel file + prompt
try:
    file_part = types.Part(
        inline_data=types.Blob(
            mime_type=mime,
            data=file_bytes
        )
    )

    response = client.models.generate_content(
        model=f"models/{model_option}",
        contents=[file_part, medication_extraction_prompt]
    )

    text = (response.text or "").strip() if response else ""
    if not text:
        st.error("No response from Gemini.")
        st.stop()

    # try parse JSON
    try:
        parsed = json.loads(text)
        st.success("Extraction completed.")
        st.json(parsed)
        st.download_button(
            "💾 Download extraction (JSON)",
            data=json.dumps(parsed, indent=2),
            file_name="treatment_extraction.json",
            mime="application/json"
        )
    except json.JSONDecodeError:
        st.error("Gemini output is not valid JSON. Showing raw output below.")
        st.code(text)
        st.download_button(
            "💾 Download raw output (txt)",
            data=text,
            file_name="treatment_extraction_raw.txt",
            mime="text/plain"
        )

except Exception as e:
    st.error(f"Error during extraction: {e}")

