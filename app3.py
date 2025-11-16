import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="PDF Text Extractor", layout="wide")
st.title("📄 Simple PDF Text Extractor — Digital + Handwritten")
st.info("Uploads a PDF and extracts text (digital + handwritten) page by page using Gemini AI.")

# Upload and API Key
uploaded = st.file_uploader("Upload PDF File", type=["pdf"])
api_key = st.text_input(
    "Enter Gemini API Key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

model_option = st.selectbox(
    "Select Gemini Model",
    [
        "gemini-2.0-flash-exp",
        "gemini-2.5-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash"
    ],
    index=0
)

if not uploaded:
    st.stop()

if not api_key.strip():
    st.warning("⚠️ Please enter your Gemini API key to proceed.")
    st.stop()

pdf_bytes = uploaded.read()

try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"❌ Failed to initialize Gemini client: {e}")
    st.stop()

st.success(f"✅ Using model: {model_option}")

# Prompt for Gemini OCR
hospital_course_prompt = """
You are a licensed medical practitioner and clinical reviewer experienced with typed and handwritten clinical notes.

GOAL (short)
Extract ALL clinically relevant text that belongs to these target sections (priority list below) from the uploaded patient medical document (may be multi-page, scanned images + typed text). Return a simple page-wise plain text output containing only the extracted material (no JSON, no commentary).

TARGET SECTIONS (highest priority — search in this order)
1. Manual - Progress note / Progress Note / Doctor's Progress Notes (and variants)
2. OT Note / Operation Note / Operative Note / Operative Details / Operation Report
3. Anesthesia notes / Anaesthesia notes / Anesthetic Note / Anaesthesia Chart
4. MDM sheet / MDM / Multidisciplinary Meeting / MDT / Case Discussion
5. Diet sheet / Diet Orders / Dietary Chart

ALGORITHM (single pass preferred; be efficient)
1) Strict pass (one-pass, page-by-page):
   - Locate exact or near-exact header variants (case-insensitive; allow small OCR errors).
   - For each matched header on a page, extract the header line plus **all verbatim readable text belonging to that section** until the next recognized header, explicit terminator (e.g., "Post-op", "Discharge", "Signature"), or end-of-page.
   - Preserve original line breaks and token order. Include printed and handwritten text verbatim.

2) If any TARGET SECTION is not found (or the found text is extremely short / empty), perform a focused fallback **only for that missing section**:
   - Search the whole document for lines/paragraphs containing high-value keywords relevant to that section (e.g., for Operative/OT: "operation", "operat", "PTCA", "stent", "DES", "sheath", "foley", "drain", "intraop", "post-op", "post operative"; for Progress note: "progress", "daily", "condition", "improved", "worsened"; for Anaesthesia: "anesthesia", "anaesth", "GA", "spinal", "MAC", "anesthetist"; for MDM: "MDM", "case discussion"; for Diet: "diet", "NBM", "feeding").
   - Extract the nearest contiguous paragraph(s) around those matches and **prepend** the most likely target header (e.g., "Operative Details (AUTO-EXTRACT)") so it is clear this came from fallback.

3) If after the focused fallback a section still yields nothing legible, **do not invent content**: output the header line followed by the exact token `NOT_FOUND`.

MERGE RULE (final consolidation)
- After extraction, merge contiguous fragments for the same logical section (e.g., Operative Details typed + postoperative orders on different pages) in chronological/reading order into one block per page occurrence.
- If multiple pages contain the same heading (daily progress), keep them as separate occurrences in their page order.
- If some sections are absent and others present, do NOT drop the present ones — include everything found and mark missing ones as `NOT_FOUND`.

OUTPUT FORMAT (STRICT — do not add anything else)
For each page from 1..N, print either the concatenated extracted sections (in the order found) or a NO_RELEVANT_SECTION_FOUND line.

Page 1:
<Header line 1 found on page 1>
<lines belonging to that header, verbatim>
<if another target header on same page, include it next>
...
Page 2:
...

If a section header was searched with fallback, label it clearly by appending " (AUTO-EXTRACT)" to the header line.

If a header is present but nothing legible follows on that page:
<Header line>
NO_TEXT_FOUND

If a target header cannot be found anywhere after fallback:
<Header line>
NOT_FOUND

PERFORMANCE / EFFICIENCY INSTRUCTIONS (to keep runs fast)
- Use exact/regex matches first; only use fuzzy matching as a targeted fallback for headers that remain missing.
- Avoid multi-pass document-wide fuzzy scans unless a section is missing after the strict pass.
- Do not output any diagnostics, confidences, or extra metadata.
- Keep extracted text verbatim (no lengthy normalization) — this reduces token expansion and speeds the model.

HANDWRITING / OCR GUIDELINES
- Preserve readable tokens exactly. When a token/word is unreadable, replace the single unreadable token with the placeholder `[ILLEGIBLE_n]` where `n` increments per page if you choose to mark illegible tokens; otherwise prefer to include the verbatim nearest legible text and do not invent words.
- Allow only tiny conservative OCR fixes for well-known medical misspellings (e.g., `foil`→`Foley`, `hematura`→`hematuria`, `urethanotomy`→`urethrotomy`) — do not change procedure names or device tokens.

KEEP IT SIMPLE
- Return only the page blocks described above. No JSON, no summary lines, no extra commentary.

END.
"""




st.markdown("---")
st.subheader("📑 Extracting Text...")

with st.spinner("Processing PDF with Gemini AI..."):
    try:
        pdf_part = types.Part(
            inline_data=types.Blob(
                mime_type="application/pdf",
                data=pdf_bytes
            )
        )

        response = client.models.generate_content(
            model=f"models/{model_option}",
            contents=[pdf_part, hospital_course_prompt]
        )

        extracted_text = (response.text or "").strip()

        if not extracted_text:
            st.error("❌ No text returned from Gemini.")
            st.stop()

    except Exception as e:
        st.error(f"❌ Error processing PDF: {e}")
        st.stop()

st.success("✅ Text extraction complete!")

# Display output
st.subheader("📜 Extracted Text")
st.text_area("Full Text Output", value=extracted_text, height=500)

# Download button
st.download_button(
    label="📥 Download Extracted Text",
    data=extracted_text,
    file_name="extracted_text.txt",
    mime="text/plain",
    use_container_width=True
)
