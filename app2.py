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
From the provided medical document (may contain printed text, scanned pages, and handwriting), extract the following clinical information and return it in two outputs:

A) Plain-text output (human-readable) in this exact order and formatting:
   1) A single short paragraph labeled "Hospital Course" (one paragraph).
   2) A named block labeled "Operative Notes:" containing five single-line fields:
       Date: <Admission Date or NOT_FOUND>
       Surgery: <Proposed/Performed Surgery or NOT_FOUND>
       Surgeon: <Dr. Full Name or Dr. NOT_FOUND>
       Anesthesia: <Anesthesia type or NOT_FOUND>
       Anesthetist: <Dr. Full Name or Dr. NOT_FOUND>
   3) A single short paragraph labeled "Operative Details:" (one paragraph) describing the procedure, intra-op findings, catheter/foley/irrigation details and immediate postop course; if nothing found output exactly NOT_FOUND for this paragraph.

B) A single JSON block (exact schema below) after the plain-text block. The JSON must be the only JSON block returned (no extra commentary).

IMPORTANT PRINCIPLES (in order)
1. **Conservative extraction:** do NOT invent facts. If illegible or ambiguous, insert "NOT_FOUND".  
2. **Preserve tokens:** preserve original words where readable; when merging fragmented handwritten lines, produce a concise medically sensible sentence using only source tokens.  
3. **Name formatting & stripping:** Format person names as `Dr. First [Middle] Last`. Remove registration numbers, material codes, and parenthetical codes from names.  
4. **Page numbers:** return the page number where the heading or main block appears. If not found, return -1. If content appears across pages, use the page containing the main heading; if heading absent, use the earliest page containing the related sentence(s).

HOW TO LOCATE EACH ITEM
- **Hospital Course:** match tolerant headings: "Hospital Course", "Clinical Summary", "Clinical Course", "Course in Hospital", "Hospital Course / Clinical Summary". Condense the paragraph(s) under that heading into one short paragraph covering admission reason, investigations, monitoring, daily consultant (if present), consultant physician (fitness for surgery), pre-op assessment, and disposition at time of operation.

- **Operative Notes (fields):**
  - **Date:** Prefer the Admission Date shown top-right/header on the first few pages. If not present there, search the document for "Admission Date", "Admit Date", or dates near the Hospital Course or header.
  - **Surgery:** Look for fields labeled "Proposed Surgery", "Surgery", "Procedure", or operation header. Use the procedure name exactly as printed (e.g., "Cystoscopy with OIU with TURP + Bladder neck incision").
  - **Surgeon:** Label cues: "Surgeon:", "Operative Surgeon", "Consultant:", "Consultant Dr", "Consultant", "Daily consulted by", "Consulted by". Choose the name nearest to the Hospital Course or Operative heading (±3 lines). If ambiguous/unreadable → `Dr. NOT_FOUND`.
  - **Anesthesia:** Search for "Anesthesia", "Anaesthesia", "Type of Anaesthesia", "Spinal", "General", "Regional", etc. If multiple types mentioned, choose the type actually used for the surgery; otherwise return the most clearly stated value or NOT_FOUND.
  - **Anesthetist:** Label cues: "Anesthetist:", "Anesthesiologist:", "Anaesthetist". Return `Dr. Full Name` or `Dr. NOT_FOUND`.

- **Operative Details:** Search headings labelled "Operation Note", "Operative Notes", "Procedure details", "Procedure", "Operative Details". Capture handwritten/printed operation descriptions (intra-op findings, resection, catheter/foley/irrigation status, immediate postop condition, NBM/feeds, meds started). Merge into one concise paragraph. If absent, return exactly `NOT_FOUND`.

ALLOWED MINOR OCR CORRECTIONS
You may correct **single-word OCR errors** for common medical tokens only (examples):  
`urethanotomy→urethrotomy`, `uretheric→ureteric`, `hematura→hematuria`, `trabeculated→trabeculated`, `Foley→Foley`, `catheter→catheter`, `TURP→TURP`, `OIU→OIU`, `BNI→BNI`, `lobe→lobe`, `bladder→bladder`, `irrigation→irrigation`.  
Do NOT invent procedures, outcomes, dates, or timings. Corrections must be token-level and conservative.

OUTPUT FORMAT (exact - plain text + JSON)
Return EXACTLY the following plain-text structure (including labels and punctuation), then a blank line, then the JSON block (no extra text):

Plain-text (example formatting — replace extracted text or NOT_FOUND):

Hospital Course
Patient was admitted with the above mentioned complaints and history. All relevant laboratory investigations done (Reports attached to the file). General condition and vitals of the patient closely monitored. Daily consulted by Dr. <SURGEON_NAME>. Fitness for surgery given by Dr. <CONSULTANT_NAME> (Consultant Physician). All preoperative assessment done, patient taken up for surgery.

Operative Notes:
Date: <DD-MM-YYYY or NOT_FOUND>
Surgery: <Surgery name or NOT_FOUND>
Surgeon: <Dr. Full Name or Dr. NOT_FOUND>
Anesthesia: <Anesthesia type or NOT_FOUND>
Anesthetist: <Dr. Full Name or Dr. NOT_FOUND>

Operative Details:
<One concise paragraph assembled from operative note or NOT_FOUND>

After this (on a new line) output **only one** JSON object matching this exact schema:

{
  "hospital_course_text": "<Exact Hospital Course paragraph above>",
  "hospital_course_page": <page_number_or_-1>,
  "operative_notes": {
    "date": "<DD-MM-YYYY or NOT_FOUND>",
    "surgery": "<Surgery name or NOT_FOUND>",
    "surgeon": "<Dr. Full Name or Dr. NOT_FOUND>",
    "anesthesia": "<Anesthesia type or NOT_FOUND>",
    "anesthetist": "<Dr. Full Name or Dr. NOT_FOUND>",
    "page": <page_number_or_-1>
  },
  "operative_details_text": "<Exact Operative Details paragraph above or 'NOT_FOUND'>",
  "operative_details_page": <page_number_or_-1>,
  "surgeon_name": "<Dr. Full Name or Dr. NOT_FOUND>",
  "consultant_physician_name": "<Dr. Full Name (Consultant Physician) or Dr. NOT_FOUND (Consultant Physician)>"
}

ADDITIONAL RULES & FALLBACKS
- If multiple pages contain pieces of a section, set the section page to the page where the heading appears; if heading absent, set to earliest page where related sentences appear.
- If a doctor name in JSON is `Dr. NOT_FOUND` but you locate a clear `Dr. X` elsewhere by label regex (e.g., near "Consultant"), prefer that name and overwrite the NOT_FOUND.
- Do not return any other text, lists, confidence numbers, or debug info. The output must be exactly:
  1) Plain-text block as described (Hospital Course, Operative Notes, Operative Details),
  2) A blank line,
  3) A single JSON object (strict schema).

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
