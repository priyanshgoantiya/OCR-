# app.py
# app.py
import streamlit as st
from google import genai
from google.genai import types
import json

st.set_page_config(page_title="PDF → Gemini (multi-prompt OCR)", layout="wide")
st.title("📄 PDF → Gemini — multi-prompt extractor")

# Upload & API key
uploaded = st.file_uploader("Upload PDF", type=["pdf"])
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
    help="Best OCR models: gemini-2.0-flash-exp, gemini-2.5-flash"
)

if not uploaded:
    st.info("Upload a PDF to extract text.")
    st.stop()

if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

pdf_bytes = uploaded.read()

# Initialize client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Define all prompts
prompts = {
    "administrative_data": """Extract patient administrative information from the hospital discharge summary. Apply OCR best practices and return data in JSON format.

REQUIRED FIELDS:
1. patient_full_name
2. age_gender
3. mr_no_ip_no
4. admission_date_time
5. discharge_date_time
6. admitting_doctor_name
7. admitting_doctor_registration_number
8. discharge_summary_number

INSTRUCTIONS:
- Extract values EXACTLY as they appear
- Use "NOT_FOUND" for missing fields
- Preserve original date formats
- For age_gender use "age / gender" format
- For mr_no_ip_no combine with " / "
- If heading "Discharge Summary" is detected, do not extract or interpret any code or unrelated text.

OUTPUT FORMAT:
{
  "patient_full_name": "string or NOT_FOUND",
  "age_gender": "string or NOT_FOUND",
  "mr_no_ip_no": "string or NOT_FOUND",
  "admission_date_time": "string or NOT_FOUND",
  "discharge_date_time": "string or NOT_FOUND",
  "admitting_doctor_name": "string or NOT_FOUND",
  "admitting_doctor_registration_number": "string or NOT_FOUND",
  "discharge_summary_number": "string or NOT_FOUND"
}

Return ONLY valid JSON.""",

    "presenting_complaints": """Extract Presenting Complaints from hospital discharge summary.

REQUIRED FIELD:
presenting_complaints

INSTRUCTIONS:
- Extract ALL complaint text exactly as written
- Preserve medical terminology and abbreviations
- Concatenate multiple lines with single space
- Include duration mentions
- Use "NOT_FOUND" if missing
- If heading "Discharge Summary" is detected, ignore any meta-text or page headers.

SEARCH FOR HEADINGS:
"Chief Complaints", "Presenting Complaints", "Complaints", "History of Presenting Illness"

OUTPUT FORMAT:
{ "presenting_complaints": "string or NOT_FOUND" }

Return ONLY valid JSON.""",

    "diagnosis": """Extract diagnosis information from hospital discharge summary.

REQUIRED FIELDS:
provisional_diagnosis
final_diagnosis

INSTRUCTIONS:
- Extract diagnoses exactly as documented
- Separate multiple conditions with " | "
- Include ICD codes if present
- Preserve medical terminology
- Use "NOT_FOUND" if missing
- If heading "Discharge Summary" is detected, skip interpretation text or instructional data.

OUTPUT FORMAT:
{ "provisional_diagnosis": "string or NOT_FOUND", "final_diagnosis": "string or NOT_FOUND" }

Return ONLY valid JSON.""",

    "past_medical_history": """Extract Past Medical History from hospital document. Focus on OCR enhancement for handwritten and typed text.

REQUIRED FIELD:
* past History

EXTRACTION RULES:
* Extract ALL medical conditions marked as present (checked, ticked, or indicated with "Yes")
* For table formats: extract conditions where "Yes" is marked in status columns
* For checkbox formats: extract conditions with checkmarks or ticks
* For handwritten text: provide best readable interpretation
* For lists: extract all mentioned conditions
* Include chronic diseases, surgeries, and relevant medical history
* Preserve original medical terminology and abbreviations

SPECIFIC HANDLING:
* Look for sections: "Past History", "Past Medical History", "PMH", "Medical History"
* Common conditions: Hypertension, Diabetes, IHD, Tuberculosis, Surgery, Others
* For "Others" category: extract specific conditions if specified
* Include duration/timing if mentioned (e.g., "Since When" columns)
* If heading "Discharge Summary" is detected, skip unrelated template instructions or footer text.

TABLE/CHECKBOX PROCESSING:
1. Identify conditions with positive status (Yes, checked, ticked)
2. Ignore conditions marked "No" or left blank
3. Extract condition names exactly as written
4. Include additional details from "Since When" or notes columns

OUTPUT FORMAT (strict JSON):
{ "past_medical_history": "extracted conditions or NOT_FOUND" }

Return ONLY valid JSON. No explanations.""",
"systemic_examination_prompt" : """Extract Systemic Examination and Clinical Findings from hospital document. Handle tables, forms, and free text.

REQUIRED FIELDS:
- blood_pressure
- pulse_rate
- respiratory_rate
- temperature
- oxygen_saturation
- cns_examination
- cvs_examination
- rs_examination
- abdominal_examination
- other_findings

EXTRACTION RULES:
- Extract values EXACTLY as written in document
- For handwritten text: provide best readable interpretation
- For tables: extract values from appropriate columns
- For forms: extract filled values next to labels
- Preserve medical abbreviations and terminology
- Include units when present (mmhg, /min, %, etc.)
- Capture both normal and abnormal findings
- Use "NOT_RECORDED" for missing/unfilled fields

SPECIFIC SECTIONS TO SEARCH:
- "Systemic Examination", "Clinical Findings", "General Examination"
- "Vital Signs", "Physical Examination", "Clinical Examination"
- Tables with examination parameters and values

VITAL SIGNS MAPPING:
- BP, Blood Pressure → blood_pressure
- Pulse, Pulse Rate → pulse_rate
- RR, Respiratory Rate → respiratory_rate
- Temp, Temperature → temperature
- SpO2, Oxygen Saturation → oxygen_saturation

SYSTEM EXAMINATION MAPPING:
- CNS, Central Nervous System → cns_examination
- CVS, Cardiovascular System → cvs_examination
- RS, Respiratory System → rs_examination
- P/A, Abdominal Examination → abdominal_examination
- Others, Additional Findings → other_findings

CRITICAL INSTRUCTION:
- If "Discharge Summary" heading is detected on page, skip extraction from that page
- Focus only on examination and clinical findings sections
- Search entire document but prioritize examination-specific sections

OUTPUT FORMAT (strict JSON):
{
  "blood_pressure": "string or NOT_RECORDED",
  "pulse_rate": "string or NOT_RECORDED",
  "respiratory_rate": "string or NOT_RECORDED",
  "temperature": "string or NOT_RECORDED",
  "oxygen_saturation": "string or NOT_RECORDED",
  "cns_examination": "string or NOT_RECORDED",
  "cvs_examination": "string or NOT_RECORDED",
  "rs_examination": "string or NOT_RECORDED",
  "abdominal_examination": "string or NOT_RECORDED",
  "other_findings": "string or NOT_RECORDED"
}

Return ONLY valid JSON. No explanations."""
}

# Process each prompt separately
combined_output = {}

with st.spinner("Processing document..."):
    for section_name, prompt_text in prompts.items():
        try:
            # Create PDF part for this request
            pdf_part = types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",
                    data=pdf_bytes
                )
            )
            
            # Call Gemini
            response = client.models.generate_content(
                model=f"models/{model_option}",
                contents=[pdf_part, prompt_text]
            )
            
            text = (response.text or "").strip() if response else ""
            
            if not text:
                st.warning(f"No response for {section_name}")
                combined_output[section_name] = "NOT_FOUND"
                continue
            
            # Display section
            st.markdown(f"### 📋 {section_name.replace('_', ' ').title()}")
            
            # Show raw text
            with st.expander(f"View raw output - {section_name}"):
                st.text_area(f"Raw ({section_name})", value=text, height=200, key=f"raw_{section_name}")
            
            # Try parse JSON
            try:
                parsed = json.loads(text)
                st.json(parsed)
                combined_output[section_name] = parsed
                
                # Download button
                st.download_button(
                    f"💾 Download {section_name}",
                    data=json.dumps(parsed, indent=2),
                    file_name=f"{section_name}.json",
                    mime="application/json",
                    key=f"download_{section_name}"
                )
            except json.JSONDecodeError:
                st.warning(f"⚠️ {section_name} output is not valid JSON")
                st.code(text)
                combined_output[section_name] = {"raw_text": text}
            
            st.markdown("---")
            
        except Exception as e:
            st.error(f"Error processing {section_name}: {e}")
            combined_output[section_name] = {"error": str(e)}

# Show combined results
st.success(f"✅ Extraction completed using {model_option}!")

st.markdown("## 📊 Combined Results")
st.json(combined_output)

# Download combined JSON
st.download_button(
    "💾 Download All Results (Combined JSON)",
    data=json.dumps(combined_output, indent=2),
    file_name="combined_extracted_data.json",
    mime="application/json",
    key="download_combined"
)

st.markdown("---")
st.markdown("**Tips:**")
st.markdown("- **Best models for OCR:** gemini-2.0-flash-exp, gemini-2.5-flash")
st.markdown("- **For handwritten text:** Use gemini-2.0-flash-exp")
st.markdown("- **If JSON fails:** Try different model or check document quality")
