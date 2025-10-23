# app.py
import streamlit as st
from google import genai
from google.genai import types
import json
import base64

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
pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

# Initialize client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# --- Prompt 1: administrative/patient fields (existing) ---
admin_prompt = """Extract patient administrative information from the hospital discharge summary. Apply OCR best practices and return data in JSON format.

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
- Extract values EXACTLY as they appear (preserve spelling, capitalization, punctuation).
- Use "NOT_FOUND" for genuinely missing fields.
- Preserve original date formats shown in the document.
- For age_gender use "age / gender" format.
- For mr_no_ip_no combine with " / ".
- For unclear handwriting: provide best interpretation.
- If a field appears multiple times, choose the most complete/authoritative value.

OUTPUT FORMAT (strict JSON):
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

CRITICAL: Return ONLY valid JSON. No explanations, no extra fields, no surrounding text.
"""

# --- Prompt 2: presenting complaints (user provided, enhanced) ---
presenting_prompt = """Extract Presenting Complaints information from the hospital discharge summary document. Return data in structured JSON format.

REQUIRED FIELD:
presenting_complaints

INSTRUCTIONS:
- Extract ALL complaint text exactly as written, preserving medical terminology, abbreviations, punctuation, and casing.
- If the presenting complaints span multiple lines or bullets, concatenate them into a single string separated by a single space.
- For handwritten text, provide the best readable interpretation; include uncertain text as-is.
- If the field appears more than once, return the most complete/authoritative occurrence.
- Include duration mentions (e.g., "7day", "2 weeks") with complaints.
- Remove only obvious OCR artifacts (repeated characters, accidental line-break tokens); do not paraphrase or summarize.
- If missing or genuinely unreadable, set value to "NOT_FOUND".

SPECIFIC HEADINGS TO SEARCH:
"Chief Complaints", "Presenting Complaints", "Complaints", "History of Presenting Illness"

OUTPUT FORMAT (strict JSON):
{ "presenting_complaints": "string or NOT_FOUND" }

CRITICAL: Return ONLY valid JSON. No explanations or extra fields.
"""

# --- Prompt 3: diagnosis (user provided) ---
diagnosis_prompt = """Extract diagnosis information from hospital discharge summary. Focus on handwritten and typed diagnosis sections.

REQUIRED FIELDS:
provisional_diagnosis
final_diagnosis

INSTRUCTIONS:
- Extract diagnoses exactly as documented.
- If diagnosis has multiple conditions, separate with " | " delimiter.
- Distinguish between primary and secondary diagnoses if specified.
- Include ICD codes if present in format: "condition (ICD-code)".
- Preserve medical terminology and abbreviations.
- For handwritten sections, provide best interpretation.
- Use "NOT_FOUND" if field not present or unreadable.

OUTPUT FORMAT (strict JSON):
{ "provisional_diagnosis": "extracted text or NOT_FOUND", "final_diagnosis": "extracted text or NOT_FOUND" }

CRITICAL: Return ONLY valid JSON. No explanations or extra fields.
"""

# --- Prompt 4: past medical history (user provided) ---
past_history_prompt = """Extract Past Medical History from hospital document. Focus on OCR enhancement for handwritten and typed text.

REQUIRED FIELD:
past_medical_history

EXTRACTION RULES:
- Extract ALL past medical conditions exactly as written.
- Preserve original medical terminology and abbreviations.
- For handwritten text: provide best readable interpretation; include uncertain text as-is.
- For lists/bullets: concatenate into single string with " | " separator.
- Include chronic conditions, surgeries, and relevant medical history.
- Preserve exact medication names if included in history.
- If missing or genuinely unreadable, set value to "NOT_FOUND".

SPECIFIC HEADINGS TO SEARCH:
"Past History", "Past Medical History", "PMH", "Medical History"

OUTPUT FORMAT (strict JSON):
{ "past_medical_history": "extracted text or NOT_FOUND" }

CRITICAL: Return ONLY valid JSON. No explanations or extra fields.
"""

# Build pdf part
pdf_part = types.Part(
    blob=types.Blob(
        mime_type="application/pdf",
        data=pdf_b64
    )
)

# Build all contents: each content = [pdf_part, prompt_part]
contents = [
    types.Content(parts=[pdf_part, types.Part(text=admin_prompt)]),
    types.Content(parts=[pdf_part, types.Part(text=presenting_prompt)]),
    types.Content(parts=[pdf_part, types.Part(text=diagnosis_prompt)]),
    types.Content(parts=[pdf_part, types.Part(text=past_history_prompt)]),
]

# Call Gemini once for all prompts
try:
    response = client.models.generate_content(
        model=model_option,
        contents=contents
    )
except Exception as e:
    st.error(f"Gemini request failed: {e}")
    st.stop()

# response.content should be a list with one entry per content
if not response or not getattr(response, "content", None):
    st.warning("No response content returned by Gemini.")
    st.stop()

combined_output = {}
st.success(f"✅ Responses received ({len(response.content)} items).")

# iterate and show each response
labels = [
    "administrative_data",
    "presenting_complaints",
    "diagnosis",
    "past_medical_history"
]

for idx, item in enumerate(response.content):
    label = labels[idx] if idx < len(labels) else f"item_{idx}"
    text = (item.text or "").strip() if item else ""
    st.markdown(f"### Result — {label}")
    if not text:
        st.warning("No text returned for this item.")
        combined_output[label] = "NOT_FOUND"
        continue

    # Show raw text area
    st.text_area(f"Raw output ({label})", value=text, height=240)

    # Try parse JSON
    try:
        parsed = json.loads(text)
        st.subheader(f"Parsed JSON ({label})")
        st.json(parsed)
        combined_output[label] = parsed
    except json.JSONDecodeError:
        st.info(f"Output for {label} is not valid JSON; storing raw text under 'raw_text'.")
        combined_output[label] = {"raw_text": text}

    # Download per-item outputs
    st.download_button(
        f"💾 Download {label} (raw)",
        data=text,
        file_name=f"{label}_raw.txt",
        mime="text/plain"
    )
    try:
        st.download_button(
            f"💾 Download {label} (json)",
            data=json.dumps(combined_output[label], indent=2),
            file_name=f"{label}.json",
            mime="application/json"
        )
    except Exception:
        # if value isn't JSON-serializable, skip
        pass

# Show combined JSON and allow download
st.markdown("---")
st.subheader("Combined Output")
st.json(combined_output)
st.download_button(
    "💾 Download combined JSON",
    data=json.dumps(combined_output, indent=2),
    file_name="combined_extracted_data.json",
    mime="application/json"
)

st.markdown("**Tips:**")
st.markdown("- Use OCR-capable Gemini models for better handwritten extraction (gemini-2.0-flash-exp, gemini-2.5-flash).")
st.markdown("- If outputs are not JSON, tweak the prompt to enforce stricter JSON-only output or try a different model.")
