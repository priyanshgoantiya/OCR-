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
medication_extraction_prompt = """TASK:
You are a licensed medical practitioner and clinical pharmacist conducting medication reconciliation for a patient's hospital stay. Your task is to extract ONLY pharmaceutical medications with pharmacological actions from the Excel sheet named exactly "Treatment Given" (the 3rd sheet in the workbook). Strictly exclude all medical consumables, supplies, implants, and non-medication items.

# CONTEXT & MINDSET:
- Think like a pharmacist reviewing a Medication Administration Record (MAR).
- Focus on identifying substances with active pharmaceutical ingredients (APIs) that are prescribed, dosed, and monitored.
- Your priority is patient safety — ensure accurate and clinically valid medication identification.

# DEFINITIONS:

## PHARMACEUTICAL MEDICATIONS (INCLUDE):
✓ Tablets, Capsules, Pills (TAB, CAP)
✓ Injections with therapeutic agents (antibiotics, analgesics, antivirals, etc.)
✓ Syrups, Suspensions, and Solutions (SYR)
✓ Topical preparations with active ingredients (OINT, CREAM, LOTION, GEL)
✓ IV Medications (with active drug, not plain fluids)
✓ Therapeutic Supplements (vitamins, minerals, albumin, protein formulations)
✓ Respiratory Medications (inhalers, respules, nebulizers)
✓ Biologicals, Vaccines, and Immunomodulators

## CONSUMABLES & SUPPLIES (EXCLUDE):
✗ Medical devices and implants (stents, catheters, sutures, DJ stents)
✗ IV fluids without active drug (NS, DNS, RL, D5%, D10%, plain water for injection)
✗ Surgical instruments, dressings, gauze, gloves
✗ Needles, syringes, tubing, IV sets
✗ Diagnostic and contrast agents
✗ Personal hygiene items (soap, toothpaste, toothbrushes, non-medicated mouthwash)
✗ Nutritional supplements without therapeutic intent
✗ Medical equipment and disposables

# EXTRACTION RULES:

**INCLUDE Criteria:**
- Substances with known pharmacological or therapeutic actions
- Items requiring prescription or medical order
- Products with clear dosage forms (TAB, CAP, INJ, SYR, OINT, etc.)
- Brand/generic names indicating drug content
- Therapeutic supplements used for specific deficiencies

**EXCLUDE Criteria:**
- Medical devices or implants
- Plain IV fluids or irrigation solutions
- Surgical supplies or diagnostic items
- Personal care and hygiene products
- General nutritional or protein support without therapeutic indication

**PROCESSING GUIDELINES:**
- Extract data from the column named "DRUG / IMPLANT NAME"
- Remove duplicates (list each medication once)
- Keep brand and generic names intact (with strengths and dosage forms)
- Ignore material codes or unrelated columns
- Apply clinical judgment in ambiguous cases

# SPECIAL HANDLING (AMBIGUOUS CASES):
- INCLUDE: Medicated lotions, antiseptic solutions (e.g., Betadine Gargle, CXT Mouthwash)
- EXCLUDE: Plain moisturizers, general mouthwash without API
- INCLUDE: Nutritional or vitamin supplements with therapeutic indication
- EXCLUDE: Non-prescription dietary supplements
- INCLUDE: Therapeutic injections (e.g., KIPINEX FORTE 1.5 INJ)
- EXCLUDE: Plain IV fluids (e.g., NS 100ML, RL INJ 500ML)

# REFERENCE FROM SAMPLE DATA:
✓ INCLUDE: VIDAMYTIL S 360MG TAB, VALGANCICLOVIR, WYSOLONE, COTRIMOXAZOLE, OPTINEURON INJ
✗ EXCLUDE: D J STENT (implant), NS 100ML (plain saline)

# OUTPUT FORMAT:
Return ONLY this valid JSON structure:
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
  "total_consumables_excluded_count": <number>,
  "clinical_notes": "Brief rationale for any ambiguous decisions"
}

# FINAL INSTRUCTION:
Process the complete “Treatment Given” sheet from the provided Excel workbook. Apply strict pharmaceutical criteria and return only the JSON output. 
Exclude all consumables, devices, and non-drug items such as needles, soaps, toothbrushes, or implants."""

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


