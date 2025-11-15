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
ocr_prompt = """
You are a licensed medical practitioner, clinical reviewer, and OCR system experienced with typed and handwritten clinical notes. The uploaded document contains both printed text and doctor handwritten notes. Your job is to extract text **only** from the target clinical sections listed below, but be robust to handwriting, page breaks, header variants, margins, and small misspellings. The final output must be the simple page-wise plain text format described at the end of this prompt and must include a per-section legibility line.

PRIMARY OBJECTIVE (strict): extract the text under these headers (case-insensitive; tolerant of spacing/punctuation/typographic errors; allow common misspellings and handwritten forms):
- Manual - Progress note, Progress Note, Progress Notes, Manual Progress Note, Progress Note(s), Doctor's Progress Notes
- OT Note, Operative Note, Operation Note, Operation Theatre Note, Operative Theatre Note, Operative Notes, Operative Details
- Anesthesia notes, Anaesthesia notes, Anesthetic Note, Anesthetist Note, Anaesthetic Note, Anaesthesia Record, Anaesthesia Chart
- MDM sheet, MDM, MDM Sheet, Multi-Disciplinary Meeting, Multidisciplinary Notes, MDT, Case Discussion
- Diet sheet, Diet Sheet, Dietary Chart, Diet Orders, Diet Plan

HEADER MATCHING (use all of the following heuristics):
- Exact match of any variant (case-insensitive) OR
- Regex match allowing small variations (e.g., optional punctuation, extra words like "Record/Notes/Sheet") OR
- Fuzzy match: accept if normalized token similarity ≥ 0.80 (or Levenshtein distance ≤ 2 for short headers) to tolerate OCR errors and handwriting.
- Recognize headers appearing in body, top-right/top-left margins, headers/footers, underlines, boxed text, or handwritten with underlines/arrows.
- If multiple candidate header matches overlap, treat them as distinct occurrences and extract each in the order they appear on the page.

EXTRACTION RULES (strictly enforce):
1. For each matched header on each page, extract the header line AND **all readable text that belongs to that section** up to (but not including) the next recognized heading (any heading) OR the explicit section terminator (e.g., "Post-op", "Discharge", "Signature") OR the end of that page — whichever comes first.
2. **Sections may span pages.** If a section continues to the next page without an intervening recognized header, continue extraction onto subsequent pages until the section ends. Preserve page ordering and line breaks.
3. Preserve exact original line breaks and ordering within each extracted section. Do not normalize punctuation, hyphenation, or line splitting.
4. Include printed and handwritten text **verbatim** as read by OCR: names, dates, times, drug names, lab numbers, signatures, short structured entries (e.g., "Drain: 200 ml"), and margin notes that clearly belong to the section.
5. If a word/character is unreadable, replace that single token with a sequential placeholder **[ILLEGIBLE_n]** (n resets to 1 for each page). Preserve punctuation immediately adjacent to the token.
6. **If a header is found but nothing legible follows on that page**, output the header line followed by:
   — NO_TEXT_FOUND
   Then the legibility line (see below).
7. **When the same section/header appears multiple times (duplicates) on the same document**, prefer the most complete occurrence (highest word count). If multiple occurrences are present on different pages and are clearly separate daily notes, keep all occurrences in chronological order.

ROBUSTNESS / FALLBACK (to avoid tiny/irrelevant extracts):
8. After the strict extraction pass, compute the total extracted character count across the entire document.
   - If total_extracted_chars >= 1,000 (approx) → accept strict extraction results.
   - If total_extracted_chars < 1,000 (i.e., extremely small) → perform one relaxed pass and **auto-extract** additional candidate lines to avoid missing content. Relaxed pass rules (ONLY if strict pass returns tiny output):
     a. Extract paragraphs or lines anywhere in the document that contain any of these keywords (case-insensitive, allow small OCR errors): "operat", "partial nephrectomy", "DJ stent", "cystoscopy", "methylene", "drain", "foley", "hematuria", "creat", "Hb", "WBC", "MRI", "USG", "CT", "histopath", "discharge", "post op", "post-op", "ICU", "NBM", "diet", "MDM", "anesth", "anaesth".
     b. For each extracted paragraph in the relaxed pass, prepend a header line using the nearest matching target header name if one is found on the same/adjacent page; if none is nearby, prepend the header line:
        AUTO_EXTRACTED_SECTION: <matching_keyword_context>
     c. Still apply [ILLEGIBLE_n] placeholders and SECTION_LEGIBILITY lines for these auto-extracted sections.
9. Do not include OCR confidences, internal scores, or comments in the output.

LEGIBILITY SUMMARY (required for each extracted section)
10. Immediately after each extracted section (on the next line), include:
    SECTION_LEGIBILITY: <legible_word_count>/<total_word_count> (legible %: <percentage_rounded_to_integer>%)
    - total_word_count = count of whitespace-separated tokens in the extracted section (placeholders [ILLEGIBLE_n] count as tokens).
    - legible_word_count = total_word_count − number_of_[ILLEGIBLE_*].
    - Round percentage to nearest whole number.

OUTPUT FORMAT (exact plain text — follow exactly; no JSON, no extra commentary):
- The output must be **page-wise**. For each page from 1..N, output either the concatenated extracted sections (in the order found) or the NO_RELEVANT_SECTION_FOUND line.

Page 1:
<Header line 1 found on page 1>
<lines of text belonging to that header, verbatim, with [ILLEGIBLE_n] placeholders if any>
SECTION_LEGIBILITY: <legible>/<total> (legible %: <N>%)
<If second target header appears on same page, include it next in the same Page 1 block using same pattern>

Page 2:
<...>

- If a section spans pages, include its continuation in the corresponding page blocks (i.e., split across Page X and Page X+1 blocks as it appears), each block followed by its SECTION_LEGIBILITY for that page's portion.
- If strict pass produced no target sections and relaxed pass generated AUTO_EXTRACTED_SECTION entries, include those in the same page-wise format.

ADDITIONAL RULES (do not change):
- Do NOT include any text outside the page blocks described above (no preface, no summary, no confidences, no JSON).
- Do NOT include OCR engine internal metadata or scores.
- Maintain the original character ordering and line breaks.

End of prompt.
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
            contents=[pdf_part, ocr_prompt]
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
