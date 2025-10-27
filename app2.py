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
    "administrative_data": """TASK:
Extract patient administrative information from a hospital discharge summary page and return a JSON object with exactly the REQUIRED FIELDS and format shown below.

⚠️ ABSOLUTE RULE (do not override):
If the page contains the heading text "Discharge Summary" (case-insensitive, exact words), DO NOT EXTRACT ANY TEXT FROM THAT PAGE. Immediately return all fields as "NOT_FOUND". No exceptions.

REQUIRED FIELDS (must appear in JSON exactly as keys):
1. patient_full_name
2. age_gender
3. mr_no_ip_no
4. admission_date_time
5. discharge_date_time
6. admitting_doctor_name
7. admitting_doctor_registration_number
8. discharge_summary_number

OUTPUT FORMAT (return ONLY this JSON):
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

HIGH-LEVEL INSTRUCTIONS:
- Extract values EXACTLY as they appear on the document (preserve punctuation, slashes, spacing, date/time formats, capitalization).
- If any field is missing or ambiguous after all heuristics, return "NOT_FOUND".
- Perform OCR best practices BEFORE extraction: deskew, set DPI >= 300, denoise, binarize, increase contrast, run layout/line segmentation, expand bounding boxes for clipped text.
- Use label → value proximity first (same line, then nearest neighbor horizontally). If label not on same line, check immediate next/previous line and the same text block.
- Allow a list of common OCR-misspellings as valid labels (see field-specific lists below).
- Do NOT normalize or reformat dates/times or names — return exactly as printed.
- If a field value contradicts context (e.g., discharge earlier than admission), return "NOT_FOUND".

SPECIAL FOCUS (explicit instruction):
- The two fields **most likely to be hard-to-find** are:
    • `discharge_summary_number` (Summary No.)
    • `discharge_date_time`
  These MUST be extracted using the explicit heading-style approach: search for heading labels (including common OCR-misspellings), then capture the value **immediately to the right** or **directly below** that heading. If heading is found but value is split across adjacent tokens/lines, join them preserving separators exactly as printed.

FIELD-SPECIFIC STRATEGIES (priority order & heuristics)

A) discharge_date_time (high priority — detailed)
- On Treatment Sheet pages, extract the value appearing next to the label “Date”.
- Accepted labels: “Date”, “Discharge Date/Time”, “Discharge Dt/Tm”, “Discharge Dt”.
- Return the extracted value exactly as printed (e.g., "16/05").

Fallback rules:
- If the label exists but OCR partially misreads it, capture the nearest date/time token to that label.
- If multiple date/time candidates are found, prioritize the one linked to an explicit “Discharge” label.
- If ambiguity remains after applying these rules, return "NOT_FOUND".

B) discharge_summary_number (high priority — detailed)
- Primary labels (case-insensitive & allow OCR variants):
  "Summary No.", "Summary No", "Summary No :", "Summary No:", "Summary#", "Discharge Summary No", "Summary Number"
  Also accept OCR variants: "Summery No", "Sumary No", "Smrnary No", "SummaryNo"
- Heading-style extraction rule:
  1. Locate the "Summary No." heading (exact or close). Capture the token immediately right of the label on the same line. If value is on next line in the same block, capture that line's first token(s).
  2. Preserve the entire matched token exactly (do NOT split or normalize).
- Preferred formats to capture (preserve exactly): codes like `DS-2025-0017224`, `DS/2025/0071224`, `12345`, or alphanumeric tokens with hyphens/slashes/underscores.
- Regex heuristics (fallback order):
  1. `(?i)(Summary\s*No\.?|Discharge\s*Summary\s*No\.?)\s*[:\-]?\s*([A-Za-z0-9\-\_/]{3,40})` → return group 2 exactly.
  2. Global fallback for DS-code: `\b(DS[-\s]?[0-9A-Za-z\/\-]{4,30})\b`
  3. If none found via label-based patterns, search full page for likely summary tokens (alphanumeric ≥ 3 chars with `DS` prefix or segmented by hyphen/slash).
- Spatial heuristic: top-right header region near MR No., Admission, Discharge fields. But label proximity trumps spatial heuristics.
- Tie-breaking:
  - If multiple DS-like tokens exist, prefer the one with an explicit "Summary" label nearby; otherwise choose token nearest the top-right administrative cluster; if still tied, return "NOT_FOUND".

C) patient_full_name
- Labels: "Name", "Patient Name", "Name :"
- Capture the text immediately following label on same line or nearest right-aligned cell. Allow titles (Mr., Mrs., Dr.), multiple name tokens. Stop capture when encountering another label (Age, MR No., Admission, etc.).
- Regex: `(?i)(?:Name|Patient Name)\s*[:\-]?\s*(.+)` → group 1 trimmed.

D) age_gender
- Required return format: `"age / gender"` (e.g., `040:08:07 / Male` or `45 / Female`).
- Labels: "Age / Gender", "Age/Gender", "Age / Gender :"
- If age and gender appear separately (Age on one token, Gender on nearby token), join them using " / " preserving age token exactly.

E) mr_no_ip_no
- Combine MR No and IP No with " / " exactly (e.g., `"286804 / 112352"`).
- Labels: "MR No.", "MR No / IP No", "MR No. / IP No."
- If they appear separately as labeled values, extract both and join with " / ". If only one found, still return combined pattern if other available elsewhere; otherwise "NOT_FOUND".

F) admission_date_time
- Labels: "Admission Dt / Tm", "Admission Date/Time", "Admission Dt"
- Extract remainder of line after label (preserve formatting). If split across tokens join preserving separator. Use same regex patterns as discharge_date_time.

G) admitting_doctor_name
- Labels: "Admitting Doctor", "Admitting Dr", "Admitting Doctor :"
- Capture the name exactly as printed. If registration number appears in parentheses or after "Reg.No." on same line, do not include the reg number in the name capture.

H) admitting_doctor_registration_number
- Labels: "Reg.No.", "Reg. No", "Regn No", "(Reg.No.)", "Regn No. :"
- Capture numeric/alphanumeric token exactly (e.g., "2004072639").

CONFIDENCE, TIE-BREAKING & FALLBACK RULES:
- Label-based matches > pattern-only matches.
- For administrative fields (MR, Admission, Discharge, Summary No): prefer candidates located in top-right administrative cluster if label proximity is equal.
- If OCR confidences are available, prefer highest average word confidence for the matched token(s).
- If a candidate clearly contradicts page context (e.g., discharge before admission), return "NOT_FOUND".
- If multiple plausible candidates remain after applying heuristics, return "NOT_FOUND".

EXTRA OCR PRACTICES TO IMPROVE ACCURACY:
- Focus on top 25–40% of page first for administrative headers.
- Use morphological closing to join broken hyphens (e.g., "D S - 2 0 2 5 - 0 0 7 1 2 2 4") and preserve dots after abbreviations.
- Expand search to adjacent lines and table cells — labels in left column frequently have values in right column cells.
- Maintain a short dictionary of label variants & common OCR misspellings for each field and apply tolerant matching.
- Log candidate matches with confidences for debugging; final output must be just the JSON.
EXAMPLES (preserve EXACT formatting):
- Name : Mr. Arvind Kumar Patel → "patient_full_name": "Mr. Arvind Kumar Patel"
- Age / Gender : 042 / Male → "age_gender": "042 / Male"

- MR No. / IP No. : MR458721 / IP239847 → "mr_no_ip_no": "MR458721 / IP239847"

- Admission Dt / Tm : 12/05/2025 / 08:45:22 → "admission_date_time": "12/05/2025 / 08:45:22"

- Discharge Dt / Tm : 15/05/2025 / 14:33:10 → "discharge_date_time": "15/05/2025 / 14:33:10"

- Admitting Doctor : Dr. Neha Sharma (Reg.No.: 2015123456) →
"admitting_doctor_name": "Dr. Neha Sharma", "admitting_doctor_registration_number": "2015123456"

Summary No. : DS-2025-0045891 → "discharge_summary_number": "DS-2025-0045891"

FINAL NOTE:
- The **discharge_summary_number** and **discharge_date_time** fields are explicitly prioritized and must be extracted using heading-style detection first (label → immediate right / below). The other fields should use your original pattern/context logic.
- Return ONLY the JSON object with the exact keys above. No additional text, commentary, or normalization.""",


    "presenting_complaints": """Extract Presenting Complaints from hospital discharge summary.

⚠️ STRICT INSTRUCTION:
If the page contains a heading 'Discharge Summary', do not extract ANY text from that page under any condition.

REQUIRED FIELD:
presenting_complaints

INSTRUCTIONS:
- Extract ALL complaint text exactly as written
- Preserve medical terminology and abbreviations
- Concatenate multiple lines with single space
- Include duration mentions
- Use "NOT_FOUND" if missing

SEARCH FOR HEADINGS:
"Chief Complaints", "Presenting Complaints", "Complaints", "History of Presenting Illness"

OUTPUT FORMAT:
{ "presenting_complaints": "string or NOT_FOUND" }

Return ONLY valid JSON.""",


    "diagnosis": """Extract diagnosis information from hospital discharge summary.

⚠️ STRICT INSTRUCTION:
If the page contains a heading 'Discharge Summary', do not extract ANY text from that page under any condition.

REQUIRED FIELDS:
provisional_diagnosis
final_diagnosis

INSTRUCTIONS:
- Extract diagnoses exactly as documented
- Separate multiple conditions with " | "
- Include ICD codes if present
- Preserve medical terminology
- Use "NOT_FOUND" if missing

OUTPUT FORMAT:
{ "provisional_diagnosis": "string or NOT_FOUND", "final_diagnosis": "string or NOT_FOUND" }

Return ONLY valid JSON.""",


    "past_medical_history": """Extract Past Medical History from hospital document. Focus on OCR enhancement for handwritten and typed text.

⚠️ STRICT INSTRUCTION:
If the page contains a heading 'Discharge Summary', do not extract ANY text from that page under any condition.

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

TABLE/CHECKBOX PROCESSING:
1. Identify conditions with positive status (Yes, checked, ticked)
2. Ignore conditions marked "No" or left blank
3. Extract condition names exactly as written
4. Include additional details from "Since When" or notes columns

OUTPUT FORMAT (strict JSON):
{ "past_medical_history": "extracted conditions or NOT_FOUND" }

Return ONLY valid JSON. No explanations.""",


    "systemic_examination_prompt": """Extract Systemic Examination and Clinical Findings from hospital document. Handle tables, forms, and free text.

⚠️ STRICT INSTRUCTION:
If the page contains a heading 'Discharge Summary', do not extract ANY text from that page under any condition.

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
- Include units when present (mmHg, /min, %, etc.)
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

Return ONLY valid JSON. No explanations.""",
      "treatment_on_discharge": """
Extract all valid medication entries from hospital documents containing the heading **"TREATMENT SHEET"** or **"Treatment on Discharge"**, and return them as structured JSON.

⚠️ GLOBAL EXTRACTION RULES:
1. Process only pages that contain the heading **"TREATMENT SHEET"** or **"Treatment on Discharge"** (case-insensitive).
2. Do NOT extract any information from pages with heading **"Discharge Summary"**.
3. Ignore administrative information, doctor signatures, checkboxes, and non-medication text.
4. Exclude any medication rows that are **crossed out / struck through**.
5. Output must be strictly valid JSON with no explanations or commentary.

---

### ✅ REQUIRED OUTPUT FORMAT:
Return a JSON object with one key `"treatment"` containing an array of medication rows.

Each row object must contain exactly:
- `"sr_no"`          : sequential integer (start from 1 if not printed)
- `"drug_name"`      : exact handwritten or typed medicine name (preserve abbreviations)
- `"dosage"`         : dose amount or strength (e.g., "500mg", "10ml", "SR")
- `"frequency"`      : dosage schedule in standard format (e.g., "1-0-1"); normalize where possible
- `"no_of_days"`     : duration in numeric form only (e.g., "3", "5"); if missing, use `"NOT_FOUND"`
- `"remark"`         : remarks exactly as written (e.g., "AFTER FOOD", "BEFORE FOOD"); if empty, `"NOT_FOUND"`

---

### 🔍 EXTRACTION RULES & IMPROVEMENTS:

#### 1. SOURCE TABLE / REGION
- Extract data only from the **table below the heading “TREATMENT SHEET”** or **“Treatment on Discharge”**.
- Each **horizontal row** represents a separate medication.
- If “Sr. No.” column is missing, number rows manually as `1, 2, 3, …` in visual order.

#### 2. EXCLUDE CROSSED ROWS
- If a row (medicine name or full line) is visibly **crossed out**, **ignore it completely**.
- Only include uncrossed rows in final JSON.

#### 3. HANDWRITTEN MEDICATIONS
- Read handwritten medicine names clearly (e.g., “TAB METFORMIN”, “T. UROTONE DS”).
- Keep abbreviations such as “TAB”, “CAP”, “INJ”, “SYP” as written.
- If any field is illegible or unclear, return `"NOT_FOUND"` for that field (do not guess).

#### 4. DOSAGE
- Capture the **dose strength** or unit next to the medicine (e.g., “500mg”, “15ml”, “10mg”).
- If the dosage is merged with the frequency or remark, separate logically using proximity (column order: Medicine → Dose → Frequency → Duration → Remark).
- If dosage missing or unclear, set `"dosage": "NOT_FOUND"`.

#### 5. FREQUENCY
- Normalize shorthand codes like:
  - `101`, `1 0 1`, `1-0-1` → `"1-0-1"`
  - `011` → `"0-1-1"`
  - `OD` → `"1-0-0"`
  - `BD` → `"1-1-0"`
  - `TDS` → `"1-1-1"`
  - `HS` → `"0-0-1"`
- If written in words (e.g., “once at night”), retain text if unambiguous, else `"NOT_FOUND"`.

#### 6. DURATION / NO. OF DAYS
- Extract numbers from formats like:
  - `x3days`, `for 3 days`, `5`, `15d`, etc.
  - Keep numeric only: e.g., `"3"`, `"5"`, `"15"`.
- If duration missing, set `"no_of_days": "NOT_FOUND"`.

#### 7. REMARK
- Extract remarks exactly as written (e.g., “AFTER FOOD”, “BEFORE FOOD”, “WITH WATER”).
- If absent, `"NOT_FOUND"`.

#### 8. COLUMN ALIGNMENT & OCR LOGIC
- Column mapping priority (left → right):
  **Medicine → Dose → Frequency → Duration → Remark**
- If multiple text blocks align horizontally within a row, map them using their vertical alignment.

---

### ⚙️ OUTPUT EXAMPLE:

{
  "treatment": [
    {
      "sr_no": "1",
      "drug_name": "TAB METFORMIN",
      "dosage": "500mg",
      "frequency": "1-0-1",
      "no_of_days": "3",
      "remark": "AFTER FOOD"
    },
    {
      "sr_no": "2",
      "drug_name": "T. UROTONE DS",
      "dosage": "1 TAB",
      "frequency": "1-0-1",
      "no_of_days": "5",
      "remark": "BEFORE FOOD"
    }
  ]
}

---

### 🚫 IF SECTION NOT FOUND:
If no valid “TREATMENT SHEET” or “Treatment on Discharge” section is detected,
return:
{ "treatment": "NOT_FOUND" }

---

### ✅ QUALITY TARGET:
- Prefer clarity over quantity: only return confident rows.
- Preserve exact capitalization, spacing, and punctuation of drug names.
- Never guess unclear tokens.
- Must exclude crossed or canceled medicines.

Return ONLY valid JSON as per this schema.
"""
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
