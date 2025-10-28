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
prompts =  {"administrative_data":"""TASK:
Extract patient administrative information from hospital pages and return a JSON object with exactly the REQUIRED FIELDS and format shown below.

REQUIRED FIELDS (exact JSON keys):
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

PRINCIPLES (follow these first — concise & general):
- Be conservative: return exactly what is printed/handwritten. Prefer "NOT_FOUND" to risky guesses.
- Preserve word-to-word accuracy for extracted tokens (do not normalize formatting or reformat dates/times).
- Be supportive of medical context and handwritten notes — interpret medically when clear and unambiguous, but do not invent.
- Always run OCR best practices before extraction (deskew, DPI ≥ 300, denoise, binarize, increase contrast, layout/line segmentation, expand bounding boxes).

SEARCH LOCATIONS & PRIORITIES:
- Goal: Do not assume a single fixed location. Detect candidate administrative clusters across the document, 
score them, and choose the best information using label→value proximity, positional heuristics, and OCR confidence.

1.) Top-right administrative cluster (high priority): often contains Name, MR/IP, Admission/Discharge, 
Summary No, ,admission_date_time and Admitting Doctor — treat it as a strong candidate but not mandatory; always score and compare it against other candidate clusters.

LABEL-TOLERANT MATCHING:
- Use label → value proximity (same line, then immediate right, then next line in same block).
- Accept common OCR-misspellings and punctuation variations for labels (e.g., "Admn Date", "Admsn Dt", "Disch Dt/Tm", "MR No", "MrNo", "SummaryNo") — but require clear proximity to a candidate value.
- Prefer exact textual capture of the value immediately adjacent to the matched label.

FIELD-SPECIFIC INSTRUCTIONS:
A) patient_full_name
- Labels to match (case-insensitive): "Name", "Patient Name", "Name :"
- Capture contiguous text tokens after label on same line or in nearest right-aligned cell until next label/token that clearly marks a new field.
- Preserve titles (Mr., Ms., Dr.) and punctuation exactly.

B) age_gender
- Labels: "Age / Gender", "Age/Gender", "Age / Gender :"
- If age and gender are on separate tokens/lines, join them with " / " preserving original tokens exactly (e.g., "042 / Male").

C) mr_no_ip_no
- Combine MR No and IP No with " / " (preserve the tokens exactly as printed).
- Labels: "MR No.", "MR No / IP No", "MR No. / IP No.", "MR:" etc.
- If one is missing, attempt to find the other elsewhere; return combined string only if both found; otherwise return "NOT_FOUND".

D) admission_date_time
- Labels: "Admission Dt / Tm", "Admission Date/Time", "Admission Dt"
- Capture the value exactly as printed; if split across tokens/lines join preserving separators.

E) discharge_date_time (short — robust)
- Search candidate regions: Treatment Sheet header(s) first (look for TREATMENT SHEET), then Patient Pending Slip / header bands, then global label search for Date, Date/Time, Discharge Dt/Tm, tolerant to OCR variants.
- Capture exact nearby substring (same line or immediately below) — keep original punctuation/spacing; do not normalize for output.
- Score candidates by label proximity, region weight (treatment-sheet high), presence of date(+time), and OCR confidence; if multiple, prefer the latest treatment-sheet date or the most complete (date+time).
- Validate: ensure discharge ≥ admission when possible; if contradiction or low confidence, discard candidate.
- If no confident candidate remains, return "discharge_date_time": "NOT_FOUND".

F) admitting_doctor_name
- Labels: "Admitting Doctor", "Admitting Dr", "Admitting Doctor :"
- Capture name exactly. If registration number appears on same line/in parentheses, omit it from this field.

G) admitting_doctor_registration_number
- Labels: "Reg.No.", "Reg. No", "Regn No", "(Reg.No.)", "Regn No. :"
- Capture the adjacent numeric/alphanumeric token exactly.

H) discharge_summary_number (PRIORITY)
- Labels: "Summary No.", "Summary No :", "Summary#", "Discharge Summary No", "Summary Number" and tolerant OCR variants.
- Heading-style extraction: capture token immediately to right or directly below label. Preserve entire matched token exactly.
- Preferred formats: DS-xxxxx, DS/xxxx, or alphanumeric codes with hyphens/slashes/underscores.

CONFIDENCE, TIE-BREAKING & FALLBACK:
- Label proximity (explicit label near a value) > pure regex search.
- If multiple  values found for a field:
  - Prefer the value closest to the canonical administrative cluster (top-right or cover page).
  - Prefer higher OCR confidence scores if available.
  - If still ambiguous, return "NOT_FOUND" for that field (do not guess).
- If a field value would contradict context (e.g., discharge before admission), return "NOT_FOUND" for the contradictory field.

SELF-VALIDATION & ASSUMPTION-RECOVERY (new — important):
- After initial extraction perform these checks:
  1. Was `discharge_summary_number` extracted using heading-style search? If label not found, try tolerant label variants; if still not found, mark field "NOT_FOUND".
  2. Was `discharge_date_time` found per priority rules (treatment sheet last date or patient-pending Date/Time)? If not, attempt label-tolerant search; if still not found, "NOT_FOUND".
  3. Does any extracted date/time contradict (discharge < admission)? If yes, mark the problematic field "NOT_FOUND" and re-check candidates.
  4. If a field relied on checkbox/tick detection, confirm the tick is visually clear; otherwise set field "NOT_FOUND".
- If any of the above assumptions fail, the extractor MUST attempt the fallback searches described (tolerant labels, top-25–40% header scan, nearest-neighbor label matches).
   If fallback still fails, return fields as "NOT_FOUND".
- If all fields are extracted successfully and pass validation, proceed to output the final JSON.

ADDITIONAL OCR PRACTICES:
- Focus initial search on top 25–40% of page for administrative headers.
- Use morphological closing to join broken tokens (e.g., "D S - 2 0 2 5 - 0 0 7 1 2 2 4").
- Expand search to adjacent lines and right-column cells when labels appear in left column.
- Preserve punctuation, slashes and spacing exactly as printed.

FINAL NOTE ON MEDICAL CONTEXT:
- When interpretation is required (e.g., minor OCR errors in names), operate in the mindset of a medical data reviewer: favor patient safety (no hallucination), preserve exact printed tokens when possible, and convert only when medically unambiguous.
- Word-for-word fidelity is required for administrative tokens.

RETURN:
- Output exactly the specified JSON object and nothing else."""}
# ,"presenting_complaints": """Extract Presenting Complaints from hospital clinical pages and return a single JSON object with the required field.

# CONSTANT:
# hospital_name = "Jupiter Hospital"

# ⚠️ STRICT INSTRUCTIONS:
# - If the page contains a heading exactly equal to "Discharge Summary" (case-insensitive exact words), DO NOT EXTRACT ANY TEXT FROM THAT PAGE. Immediately return: {"presenting_complaints":"NOT_FOUND"}.
# - Do NOT include illustrative examples in the prompt (avoid bias). Output MUST be valid JSON only (no extra text or explanation).

# REQUIRED FIELD:
# presenting_complaints

# HIGH-LEVEL GOAL:
# - Produce a single coherent, medically sensible sentence that begins with:
#   "Patient presented with complaints of <symptom list>."
# - Immediately after that sentence append the admission clause (inside the same string) exactly like this:
#   " hence admitted in Jupiter Hospital under care of {admitting_doctor_name} for further management."
#   *Always prefer the admitting_doctor_name value from the document's `administrative_data.admitting_doctor_name` (global/extracted administrative section). If that value is "NOT_FOUND", attempt a targeted, limited re-extraction from the document as a fallback (see ADMIT NAME SOURCE). If still not found, insert "NOT_FOUND".*

# SEARCH HEADINGS (case-insensitive):
# "Chief Complaints", "Presenting Complaints", "Complaints", "History of Presenting Illness", or any handwritten/printed variant containing the word "Complaint" or "Complaints".

# INPUT CHARACTERISTICS:
# - Content may be multi-line, bulleted, handwritten, or noisy OCR output.
# - Handwriting may contain spelling/OCR errors.

# PREPROCESSING (apply before textual extraction):
# - Deskew, set DPI >= 300, denoise, binarize, increase contrast.
# - Run layout/line segmentation and expand bounding boxes for clipped text.
# - Use morphological closing to join broken characters.

# EXTRACTION & NORMALIZATION RULES:
# 1. Locate the presenting complaints block under one of the SEARCH HEADINGS. If multiple such blocks exist, prefer the first clinical "Chief Complaints"/"Presenting Complaints" block on the patient's initial clinical pages (skip pages titled exactly "Discharge Summary").
# 2. Extract ALL complaint lines and tokens under that heading. Concatenate multiple lines into a single symptom list separated by commas, using "and" before the last item.
# 3. Apply automatic spelling/term normalization using a comprehensive medical dictionary and fuzzy-matching techniques — DO NOT hardcode small correction lists into the prompt. Only perform a correction when the mapping to a standard medical term is medically unambiguous (high-confidence fuzzy match or dictionary lookup). If a token cannot be confidently mapped, retain the original token.
# 4. If more than two tokens across the extracted complaints remain ambiguous or unreadable after attempted correction, return: {"presenting_complaints":"NOT_FOUND"}.
# 5. Preserve and include duration mentions exactly as printed when present (e.g., "for 3 days", "2 weeks").
# 6. Preserve well-known abbreviations (e.g., "SOB", "HTN", "DM") exactly as written **only if** they appear clearly and unambiguously.
# 7. Ensure grammatical correctness of the final sentence: prepend "Patient presented with complaints of " before the symptom list; use commas and "and" appropriately; end the sentence with a period before appending the admission clause.

# ADMIT NAME SOURCE (how to populate {admitting_doctor_name}):
# - Primary source: use `administrative_data.admitting_doctor_name` (the extracted administrative section). If this field contains a non-"NOT_FOUND" value, substitute that exact string (preserve spacing and punctuation).
# - Fallback (only if administrative_data.admitting_doctor_name == "NOT_FOUND"):
#   1. Search the document's administrative/header cluster (top ~25-40% of pages) and the earliest pages for labels: "Admitting Doctor", "Admitting Dr", "Admitting Doctor :", "Admitted under", or OCR variants (case-insensitive).
#   2. Use label → value proximity (same line, then nearest right/next line) to capture the name exactly as printed. Accept common OCR misspellings of the label but require a confident label match.
#   3. If multiple candidate names found, prefer the one appearing in the document's administrative cluster or the first page-level administrative block.
#   4. If name still ambiguous or low-confidence, set admitting_doctor_name to "NOT_FOUND".
# - Do NOT attempt a broad re-extraction across all pages; only attempt the targeted fallback above. Primary preference is the administrative_data value.

# ADMISSION CLAUSE:
# - After the complaint sentence append a single space then:
#   "hence admitted in Jupiter Hospital under care of {admitting_doctor_name} for further management."
# - Use the admitting_doctor_name determined by ADMIT NAME SOURCE above.

# CONFIDENCE / FALLBACKS:
# - If the presenting complaints section is present but OCR produces unreadable text and you cannot confidently correct at least the primary symptom, return: {"presenting_complaints":"NOT_FOUND"}.
# - If symptoms extracted but admitting_doctor_name is unavailable even after fallback, still return the presenting_complaints sentence and set the admitting doctor placeholder to "NOT_FOUND".
# - Do NOT output any extra fields; only the required JSON object.

# OUTPUT FORMAT (exact):
# { "presenting_complaints": "Patient presented with complaints of <symptom1>, <symptom2> and <symptomN> hence admitted in Jupiter Hospital under care of {admitting_doctor_name} for further management." }
# OR
# { "presenting_complaints": "NOT_FOUND" }

# Return ONLY valid JSON. """
# ,


#     "diagnosis": """Extract diagnosis information from hospital discharge summary.

# ⚠️ STRICT INSTRUCTION:
# If the page contains a heading 'Discharge Summary', do not extract ANY text from that page under any condition.

# REQUIRED FIELDS:
# provisional_diagnosis
# final_diagnosis

# INSTRUCTIONS:
# - Extract diagnoses exactly as documented
# - Separate multiple conditions with " | "
# - Include ICD codes if present
# - Preserve medical terminology
# - Use "NOT_FOUND" if missing

# OUTPUT FORMAT:
# { "provisional_diagnosis": "string or NOT_FOUND", "final_diagnosis": "string or NOT_FOUND" }

# Return ONLY valid JSON.""","past_medical_history": """Extract Past Medical History from hospital document. Focus on OCR enhancement for handwritten and typed text.

# ⚠️ STRICT INSTRUCTION:
# - If the page contains a heading exactly equal to "Discharge Summary" (case-insensitive exact words), DO NOT EXTRACT ANY TEXT FROM THAT PAGE. Immediately return: {"past_medical_history":"NOT_FOUND"}.
# - The images shown to you are only samples for understanding; do NOT hard-code rules that rely on those exact visuals. Make logic general and robust.
# - Output MUST be valid JSON only (no extra text or explanation).

# REQUIRED FIELD:
# past_medical_history

# GOAL:
# Return a single string listing all past medical conditions that are explicitly indicated as PRESENT in the document (comma-separated). If none confidently present, return "NOT_FOUND".

# PREPROCESSING (apply before extraction):
# - Deskew, set DPI >= 300, denoise, binarize, increase contrast, run layout/line segmentation, and expand bounding boxes for clipped text.
# - Detect table/grid structure and label/value cell boundaries for rows that list conditions and their Yes/No status.

# DETECTION RULES (decide whether a condition is PRESENT):

# For each condition row (e.g., Hypertension, Diabetes, IHD, Tuberculosis, Surgery, Others, etc.) determine presence using the following prioritized signals:

# 1. Explicit "Yes" token selected:
#    - If the cell labelled "Yes" (or the token "Yes" adjacent to the condition) contains a selection mark (tick ✔, check ✓, filled box, darkened box, dot •, 'x' or 'X', or an overlaid handwritten mark), treat condition as PRESENT.
#    - If the word "Yes" itself is handwritten/typed next to the condition (and not contradicted), treat as PRESENT.

# 2. No-cell strike-through / negation of "No":
#    - If the "No" cell contains a clear strike-through (a horizontal or diagonal line through the "No" token) that visually negates the "No", and the "Yes" cell is empty, infer condition as PRESENT.
#    - If the "No" cell is crossed out but there is also a mark in the Yes cell, still treat as PRESENT (Yes takes precedence).

# 3. Mark in condition-name cell indicating selection:
#    - If a mark (tick/X/circle) sits directly on or overlaps the condition name cell in a way consistent with the document's checkstyle (some forms place the mark beside the item instead of in Yes/No columns), treat as PRESENT only if the form's pattern indicates marks imply Yes.

# 4. Handwritten affirmative text:
#    - If freehand notes next to the condition contain affirmative words ("Yes", "Y", "Present", "√") treat as PRESENT.

# 5. Ambiguity & contradiction:
#    - If BOTH Yes and No cells show comparable selection marks (e.g., both ticked or both heavily marked) OR there is a conflicting/unclear mark making it impossible to decide, return NOT_FOUND for that specific condition (do not include it).
#    - If selection marks are faint/uncertain and OCR/vision confidence is low, treat that condition as NOT_FOUND.

# GENERAL HEURISTICS:
# - Spatial proximity: evaluate marks within the bounding boxes of the Yes/No cells for each row. A mark overlapping a Yes cell counts for Yes; a mark overlapping a No cell counts for No (unless struck-through as above).
# - Visual types considered as selection: ticks, checkmarks, filled squares/circles, 'x', 'X', dots, bold underline, or clear darkening.
# - Strike-through detection: a continuous line passing through the text token (No) is considered a negation of that token.
# - If an "Others" row is marked PRESENT, attempt to extract the handwritten description that follows; include that exact text after the condition name (e.g., "Others: [text]"). If the "Others" description is unreadable, include just "Others" to indicate positive history.
# - Do NOT infer presence from absence of marks. Only include conditions with explicit positive indications per rules above.

# POST-PROCESSING & OUTPUT:
# - Aggregate all detected PRESENT conditions into a single comma-separated string in their original printed/handwritten form (normalize obvious OCR spacing issues but preserve medical terms and abbreviations).
# - If duration/timing ("Since when") is present and clearly linked to a condition row, append it in parentheses immediately after that condition (e.g., "Hypertension (since 2015)").
# - If no conditions confidently detected as PRESENT, return: { "past_medical_history": "NOT_FOUND" }
# - Otherwise return: { "past_medical_history": "<Condition1>, <Condition2>, <Condition3>" }

# CONFIDENCE & FALLBACKS:
# - Prefer visual evidence (marks) over textual OCR only. Text "No" without a mark must be treated as negative.
# - If a row shows a faint mark and OCR/vision confidence metrics are available, require a minimum confidence threshold to accept it as PRESENT; otherwise treat as NOT_FOUND.
# - If any single row is ambiguous after heuristics, exclude that row rather than risking a false positive. Do not list conditions marked as "No".

# OUTPUT FORMAT (exact):
# { "past_medical_history": "Hypertension, Diabetes, IHD" }
# OR
# { "past_medical_history": "NOT_FOUND" }

# Return ONLY valid JSON. """,


#     "systemic_examination_prompt": """Extract Systemic Examination and Clinical Findings from hospital document. Handle tables, forms, and free text.

# ⚠️ STRICT INSTRUCTION:
# If the page contains a heading 'Discharge Summary', do not extract ANY text from that page under any condition.

# REQUIRED FIELDS:
# - blood_pressure
# - pulse_rate
# - respiratory_rate
# - temperature
# - oxygen_saturation
# - cns_examination
# - cvs_examination
# - rs_examination
# - abdominal_examination
# - other_findings

# EXTRACTION RULES:
# - Extract values EXACTLY as written in document
# - For handwritten text: provide best readable interpretation
# - For tables: extract values from appropriate columns
# - For forms: extract filled values next to labels
# - Preserve medical abbreviations and terminology
# - Include units when present (mmHg, /min, %, etc.)
# - Capture both normal and abnormal findings
# - Use "NOT_RECORDED" for missing/unfilled fields

# SPECIFIC SECTIONS TO SEARCH:
# - "Systemic Examination", "Clinical Findings", "General Examination"
# - "Vital Signs", "Physical Examination", "Clinical Examination"
# - Tables with examination parameters and values

# VITAL SIGNS MAPPING:
# - BP, Blood Pressure → blood_pressure
# - Pulse, Pulse Rate → pulse_rate
# - RR, Respiratory Rate → respiratory_rate
# - Temp, Temperature → temperature
# - SpO2, Oxygen Saturation → oxygen_saturation

# SYSTEM EXAMINATION MAPPING:
# - CNS, Central Nervous System → cns_examination
# - CVS, Cardiovascular System → cvs_examination
# - RS, Respiratory System → rs_examination
# - P/A, Abdominal Examination → abdominal_examination
# - Others, Additional Findings → other_findings

# OUTPUT FORMAT (strict JSON):
# {
#   "blood_pressure": "string or NOT_RECORDED",
#   "pulse_rate": "string or NOT_RECORDED",
#   "respiratory_rate": "string or NOT_RECORDED",
#   "temperature": "string or NOT_RECORDED",
#   "oxygen_saturation": "string or NOT_RECORDED",
#   "cns_examination": "string or NOT_RECORDED",
#   "cvs_examination": "string or NOT_RECORDED",
#   "rs_examination": "string or NOT_RECORDED",
#   "abdominal_examination": "string or NOT_RECORDED",
#   "other_findings": "string or NOT_RECORDED"
# }

# Return ONLY valid JSON. No explanations.""",
#       "treatment_on_discharge": """Extract medication prescription rows from the hospital document's "Treatment on Discharge" table or handwritten treatment section and return a JSON array representing the table rows.

# medical_acronyms = [ "OD", "BD", "BID", "TDS", "TID", "QID", "HS", "QHS", "SOS", "QOD", "Q4H", "Q6H", "Q8H", "AC", "PC", "STAT", "PRN", "QAM", "QPM", "NPO" ]

# ⚠️ COMPULSORY GLOBAL RULES:

# Locate and extract ONLY from a section whose heading contains the phrase "Treatment on Discharge" (case-insensitive). This includes exact headings like "Treatment on Discharge" AND headings where the phrase appears as part of a larger heading or with adjacent words (e.g., "Treatment on Discharge - Home", "Treatment on Discharge (Doctor's Notes)", or the same phrase appearing inside doctor progress/handwritten notes). Handwritten headings that include the phrase should be treated the same as printed headings. HOWEVER — if the page's main heading is exactly "Discharge Summary" (case-insensitive exact words), DO NOT EXTRACT ANY TEXT FROM THAT PAGE. Immediately return all fields as "NOT_FOUND". No exceptions.

# Ignore patient administrative info, headers, footers, doctor signatures, and other non-medication text.

# Output MUST be valid JSON only (no extra text or explanation).

# REQUIRED OUTPUT (table-style JSON array): Return JSON with a single key "treatment" containing an array of row objects in the same order as they appear in the table.

# Each row object MUST have these keys:

# "sr_no" : if not explicitly given, assign sequentially starting from 1 (e.g., 1, 2, 3…). Use strings for serials if the original printed value used strings; otherwise it's acceptable to return numeric serials as integers. "drug_name" : string (preserve exact drug name, e.g., "TAB CEFTUM"). If unreadable, use "NOT_FOUND". "dosage" : string (preserve format exactly, e.g., "500mg", "15ml", "SR"). If unreadable, use "NOT_FOUND". "frequency" : string (see FREQUENCY HANDLING below). "no_of_days" : string or integer (extract numeric days only, e.g., "3", "15"; if not present use "NOT_FOUND") "remark" : string (preserve remark exactly, e.g., "AFTER FOOD"; if empty use "NOT_FOUND")

# EXTRACTION RULES / DETAILS:

# TABLE SOURCE:

# Locate the table/rows directly under any heading that contains the phrase "Treatment on Discharge" (case-insensitive). This covers printed tables, typed headings inside progress notes, and handwritten headings that include the phrase even if other words appear beside it.
# Extract ALL medication rows from that table (do not skip blank rows).
# Preserve the table order.
# If "Sr. No." column is not printed, assign serial numbers manually (1, 2, 3, …).
# HANDWRITTEN PRESCRIPTIONS:

# Handwriting will be present but clear. Provide the best medically sensible interpretation for drug names and dosages.
# If multiple plausible readings exist, choose the most likely standard medication name and preserve the original capitalization/abbreviation (e.g., "TAB VOVERON SR").
# If uncertain about a token (e.g., ambiguous letters/digits), return "NOT_FOUND" for that field rather than guessing.
# FREQUENCY HANDLING (IMPORTANT):

# DO NOT convert common medical acronym frequencies to numeric patterns. If the original frequency token exactly matches any entry in the medical_acronyms list (case-insensitive match), PRESERVE that token exactly as written (maintain original casing/abbreviation). Examples: "OD", "BD", "BID", "TDS" must remain as-is, not converted to "1-0-0" or similar.
# For frequency tokens that are numeric patterns (e.g., "101", "1 0 1", "1-0-1", "110", "011"), normalize them to the dashed "X-X-X" format (e.g., "1-0-1", "1-1-0", "0-1-1") when the conversion is unambiguous.
# If frequency is written in words (e.g., "once at night"), convert to the appropriate 3-slot code only when unambiguous; otherwise preserve the original text.
# If frequency cannot be determined, set "frequency": "NOT_FOUND".
# DURATION / NO. OF DAYS:

# Duration may be written like "x-3 days", "x3days", "03", "15", "for 3 days".
# Extract numeric only (e.g., "3", "15", "03" → "3").
# If multiple durations found, choose the one aligned with the medication row.
# If not present or unreadable, return "NOT_FOUND".
# REMARKS:

# Preserve remarks exactly as written (e.g., "AFTER FOOD", "BEFORE FOOD"). Use "NOT_FOUND" if empty.
# DOSAGE:

# Preserve the dosage token exactly (e.g., "500mg", "15ml", "SR").
# If dosage text merges with frequency or duration in handwriting, separate fields per the table column mapping; prefer explicit dosage units (mg, ml, IU, mcg) when present.
# ROUTE (optional):

# Do not add a separate route field in this output.
# OUTPUT FORMAT (strict JSON example): { "treatment": [ { "sr_no": "sr_no or NOT_FOUND", "drug_name": "drug_name or NOT_FOUND", "dosage": "dosage or NOT_FOUND", "frequency": "frequency or NOT_FOUND", "no_of_days": "no_of_days or NOT_FOUND", "remark": "remark or NOT_FOUND" } ] }

# ADDITIONAL NOTES:

# If the entire "Treatment on Discharge" section is missing (i.e., no heading that contains the phrase "Treatment on Discharge" is found on the page, or only the page-level main heading is exactly "Discharge Summary"), return: { "treatment": "NOT_FOUND" }
# Always return a JSON object as shown; do NOT include explanatory text, reasoning, or logs.
# Return ONLY valid JSON for every document processed. """ 

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
