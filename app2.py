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
  B) Operation Note / Procedure Details paragraph (also called "Procedure details" or "Operation Note")

Produce two outputs:
  1. Two plain-text paragraphs (human-readable). Each paragraph must be a short, coherent, clinically-sensible paragraph assembled from the original text. Do NOT invent clinical facts; only rephrase/merge tokens found in the document. If any field is missing or unreadable, insert the token "NOT_FOUND" in that paragraph where the missing element would appear.
  2. A JSON object (exact schema below) specifying the extracted text and metadata (page numbers and extracted doctor names).

IMPORTANT PRINCIPLES (follow in order)
1. Conservative extraction: if a name or phrase is illegible or low-confidence, use "NOT_FOUND". Do NOT hallucinate.
2. Preserve word-to-word accuracy where readable; where text is fragmented (handwriting lines), merge logically to make a single coherent sentence/paragraph while keeping original words.
3. Strip registration numbers, material codes, trailing parentheticals, and numeric item-codes from extracted person names.
4. Provide page numbers when you can locate the text; if not found, set page number to -1.

HOW TO FIND EACH SECTION
- Hospital Course / Clinical Summary:
  Search for headings or tolerant variants: "Hospital Course", "Clinical Summary", "Clinical Course", "Course in Hospital", "Hospital Course / Clinical Summary", "HospitalCourse".
  Capture the paragraph(s) under that heading and condense/merge into a single short paragraph describing: admission reason, investigations, monitoring, daily consultant/surgeon name, consultant physician name (fitness for surgery), preop assessment, and disposition at surgery/time of operation (if present).

- Operation Note / Procedure Details:
  Search for headings/labels: "Operation Note", "Operative Notes", "Procedure details", "Procedure", "Surgery", "Operative Details".
  Capture handwritten or printed operation notes / procedure descriptions (including immediate postop state, catheter/foley/irrigation notes, complications) and merge into a concise paragraph that reads medically (one paragraph, preserve original tokens and order as much as possible).

DOCTOR NAMES (formatting rules)
- Surgeon / Daily-consulted Doctor: format exactly as `Dr. <Full Name>` (example `Dr. Sahil Kiran Pethe`).
  Candidate label cues: "Surgeon:", "Operative Surgeon", "Daily consulted by", "Consulted by", "Admitting Doctor", "Dr."
  If multiple candidates near hospital-course region, choose the name closest to the Hospital Course or Operative header. If ambiguous/unreadable → `Dr. NOT_FOUND`.

- Consultant Physician: format as `Dr. <Full Name> (Consultant Physician)`.
  Candidate label cues: "Consultant Physician:", "Consultant:", "Consultant Dr", "Fitness for surgery given by"
  If ambiguous/unreadable → `Dr. NOT_FOUND (Consultant Physician)`.

OUTPUT SPECIFICATIONS — PLAIN TEXT
Return exactly two paragraphs separated by a blank line. Do NOT return any additional explanatory text.

Paragraph 1 — Hospital Course (single paragraph):
Example structure to follow (you must produce real extracted names/phrases or NOT_FOUND):
Patient was admitted with the above mentioned complaints and history. All relevant laboratory investigations were performed (reports attached). General condition and vitals of the patient were closely monitored. Daily consulted by Dr. <SURGEON_OR_DAILY_DOCTOR_NAME>. Fitness for surgery given by Dr. <CONSULTANT_PHYSICIAN_NAME> (Consultant Physician). All preoperative assessment was completed and the patient was taken up for surgery.

Paragraph 2 — Operation Note / Procedure Details (single paragraph):
Concise summary of the operative/procedure notes (word-to-word where possible). Include operative procedure performed, key intraoperative findings, catheter/irrigation/foley details, immediate postop status and disposition. If no operation/procedure details present, output exactly: NOT_FOUND

OUTPUT SPECIFICATIONS — JSON
Return the following JSON object **after** the two paragraphs (separated by a blank line). The JSON must be the ONLY JSON block returned (no extra commentary). Keys and types must match exactly:

{
  "hospital_course_text": "<Exact paragraph 1 above as a single string>",
  "hospital_course_page": <page_number_or_-1>,
  "operation_note_text": "<Exact paragraph 2 above as a single string or 'NOT_FOUND'>",
  "operation_note_page": <page_number_or_-1>,
  "surgeon_name": "Dr. <Full Name>" or "Dr. NOT_FOUND",
  "consultant_physician_name": "Dr. <Full Name> (Consultant Physician)" or "Dr. NOT_FOUND (Consultant Physician)"
}

ADDITIONAL RULES & EXAMPLES
- Names MUST use prefix "Dr." and full name (first + middle + last when present).
- If you find multiple pages containing pieces of the hospital course, merge them into the paragraph and set hospital_course_page to the page number where the main heading appears; if the heading isn't available but the text is found across pages, set page to the earliest page where related sentences appear.
- For operation_note_page, set to the page containing the handwritten Operation Note / Procedure details (prefer the page where the heading appears). If only handwritten body exists without heading, use that page number.
- Do not output intermediate lists, confidence scores, or other metadata.
- Return the plain text paragraphs first (two paragraphs separated by one blank line), then the JSON object (on a new line).

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
