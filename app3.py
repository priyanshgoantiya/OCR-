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

# Define prompt dictionary
prompts = {
    "medication_extraction": medication_extraction_prompt
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


