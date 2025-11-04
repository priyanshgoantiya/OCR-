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

# Define general medication extraction prompt
general_medication_extraction_prompt = """You are a licensed medical practitioner and clinical reviewer.

TASK (high level)
From the provided medical document (may contain printed text, scanned pages, and handwriting), extract two pieces of clinical information:

  A) Hospital Course / Clinical Summary paragraph
  B) Operation Note / Procedure Details paragraph

Produce two outputs:
  1. Two plain-text paragraphs (human-readable). Each must be a short, coherent, clinically-sensible paragraph assembled only from text found in the document. Do NOT invent clinical facts; you may only correct obvious single-word OCR errors for common medical terms (see Allowed Corrections below). If a required name or phrase is unreadable or absent, insert "NOT_FOUND" at that position.
  2. A JSON object (exact schema shown below) specifying the extracted text and page numbers and extracted doctor names.

PRINCIPLES (order of priority)
1. **Conservative extraction:** never hallucinate. If illegible, use "NOT_FOUND".
2. **Preserve source tokens** where readable. If text fragments occur across lines, merge logically but keep original words.
3. **Name normalization:** strip registration numbers, trailing codes or parentheticals from person names. Format names exactly as `Dr. First [Middle] Last`.
4. **Page numbers:** return the page number where the heading or main block appears; if not located, use -1.

HOW TO LOCATE & EXTRACT
- Hospital Course / Clinical Summary:
  Search tolerant headings: "Hospital Course", "HospitalCourse", "Clinical Summary", "Clinical Course", "Course in Hospital", "Hospital Course / Clinical Summary". Extract the paragraph(s) under that heading and condense into one short paragraph describing admission reason, investigations, monitoring, daily consultant/surgeon, consultant physician (fitness for surgery), pre-op assessment, and disposition at surgery/time of operation (if present).

- Operation Note / Procedure Details:
  Search headings/labels: "Operation Note", "Operative Notes", "Procedure details", "Procedure", "Surgery", "Operative Details". Capture handwritten or printed operation notes (including catheter/foley/irrigation notes, immediate postop state) and merge into one concise paragraph that reads medically. If no operation note exists, output exactly: NOT_FOUND

DOCTOR NAME RULES (use proximity & label cues)
- **Surgeon / Daily-consulted Doctor:** choose candidate named nearest to Hospital Course or Operation heading. Label cues: "Surgeon:", "Operative Surgeon", "Daily consulted by", "Consulted by", "Admitting Doctor", "Dr." Format: `Dr. <Full Name>`; if ambiguous or unreadable → `Dr. NOT_FOUND`.
- **Consultant Physician:** label cues: "Consultant Physician:", "Consultant:", "Fitness for surgery given by", "Fitness for surgery". Format: `Dr. <Full Name> (Consultant Physician)`; if ambiguous/unreadable → `Dr. NOT_FOUND (Consultant Physician)`.

ALLOWED OCR CORRECTIONS (only these single-token / word fixes)
- You MAY correct obvious OCR misspellings of common terms: e.g., urethanotomy→urethrotomy, uretheric→ureteric, hematura→hematuria, trabeculated→trabeculated, Foley→Foley, catheter→catheter, TURP→TURP, OIU→OIU, BNI→BNI, lobe→lobe, bladder→bladder, irrigation→irrigation.
- Do NOT invent procedures, durations, outcomes, or dates. Corrections must be minimal, token-level, and preserve clinical meaning.

OUTPUT FORMAT (exact)
1) Return **two plain-text paragraphs** only (separated by one blank line). No extra commentary.

Paragraph 1 — Hospital Course (single paragraph). Example structure to follow:
Patient was admitted with the above mentioned complaints and history. All relevant laboratory investigations were performed (reports attached). General condition and vitals of the patient were closely monitored. Daily consulted by Dr. <SURGEON_NAME>. Fitness for surgery given by Dr. <CONSULTANT_NAME> (Consultant Physician). All preoperative assessment was completed and the patient was taken up for surgery.

Paragraph 2 — Operation Note / Procedure Details (single paragraph). If missing, output exactly:
NOT_FOUND

2) After the two paragraphs (separated by one blank line), output a single JSON block (and nothing else) with this exact schema:

{
  "hospital_course_text": "<exact paragraph 1 here>",
  "hospital_course_page": <page_number_or_-1>,
  "operation_note_text": "<exact paragraph 2 here or 'NOT_FOUND'>",
  "operation_note_page": <page_number_or_-1>,
  "surgeon_name": "Dr. <Full Name>" or "Dr. NOT_FOUND",
  "consultant_physician_name": "Dr. <Full Name> (Consultant Physician)" or "Dr. NOT_FOUND (Consultant Physician)"
}

ADDITIONAL INSTRUCTIONS
- If you find multiple candidate names, choose the one closest to the relevant heading (within ±3 lines). If distances tie, return `Dr. NOT_FOUND`.
- If you detect page numbers in the raw OCR (e.g., "Page 2"), use those. If not, return -1 for page.
- Output must be strictly: 2 paragraphs, one blank line, then the JSON block. No extra text.

END TASK.
"""

# Define all prompts dictionary - FIXED: Added opening brace
prompts = {
    "General medication extraction prompt": general_medication_extraction_prompt
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
