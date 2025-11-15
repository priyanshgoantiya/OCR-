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
You are a licensed medical practitioner, clinical reviewer, and OCR system experienced with typed and handwritten clinical notes. The uploaded document contains both printed text and doctor handwritten notes. Your job is to extract **only** the text that belongs to the following target sections/headers (case-insensitive, tolerant of small variants and common misspellings), and to provide a simple word-legibility metric for each extracted section.

Target section headers (match any of these variants):
- Manual - Progress note, Progress Note, Progress Notes, Manual Progress Note
- OT Note, Operative Note, Operation Note, Operation Theatre Note, Operative Theatre Note
- Anesthesia notes, Anaesthesia notes, Anesthetic Note, Anesthetist Note, Anaesthetic Note
- MDM sheet, MDM, MDM Sheet, Multi-Disciplinary Meeting, Multidisciplinary Notes
- Diet sheet, Diet Sheet, Dietary Chart, Diet Orders

Extraction rules (follow exactly):
1. For each page, search for any of the target headers. For each header found on that page, extract the header line AND all readable text that belongs to that section up to (but not including) the next heading (any heading) or the end of the page, whichever comes first.
2. Matching must be case-insensitive and tolerant of small variants (extra spaces, punctuation, abbreviations like "OT Note", or handwritten variants).
3. If a header appears multiple times on a page, extract each occurrence's text in order (header + its section).
4. Preserve the **exact original line breaks and ordering** within each extracted section. Do not normalize punctuation or merge lines.
5. Include both printed and handwritten text **verbatim** as read by OCR: names, dates, times, drug names, lab numbers, signatures, short structured entries, doodles/marks that are part of the section, etc.
6. If a word or scribble is **unreadable/illegible**, replace that word with a sequential placeholder of the form: **[ILLEGIBLE_n]** (where n starts at 1 for the first illegible token on that page and increments). Preserve punctuation around the placeholder exactly as in the source.
7. Immediately after each extracted section (on the next line), include a single **legibility summary line** in this exact format (no extra text):
   SECTION_LEGIBILITY: <legible_word_count>/<total_word_count> (legible %: <percentage_rounded_to_integer>%)
   - Compute total_word_count by counting all whitespace-separated tokens in the extracted section (placeholders [ILLEGIBLE_n] count as tokens).
   - Compute legible_word_count = total_word_count − number_of_[ILLEGIBLE_*] placeholders.
   - Round the percentage to the nearest whole number.
8. If a target header is present but **no readable text follows it** on that page, output the header line followed by:
   — NO_TEXT_FOUND
   and then the legibility line:
   SECTION_LEGIBILITY: 0/0 (legible %: 0%)
9. If none of the target sections are present on a page, write exactly:
   Page X: NO_RELEVANT_SECTION_FOUND
   (Replace X with the page number.)
10. Do **not** extract any text outside the listed target sections. Ignore unrelated headings and content.
11. DO NOT include OCR confidence scores, notes, comments, JSON, or any additional explanation. Return only the page-wise plain text in the exact format below.

Output format (exact plain text; follow this structure):
Page 1:
<Header line 1 found on page 1>
<lines of text belonging to that header, verbatim, with [ILLEGIBLE_n] placeholders if any>
SECTION_LEGIBILITY: <legible>/<total> (legible %: <N>%)
<If second target header appears on same page, include it next in the same Page 1 block using same pattern>

Page 2:
<...>

Examples of allowed inline content:
- Names, e.g., "Dr. Sagar Bhalerao"
- Dates/times, e.g., "26/03/2025 08:50 AM"
- Lab values and units, e.g., "Hb 13.4 g/dL"
- Short structured lines, e.g., "Drain: 200 ml"
- Handwritten transcription verbatim (or [ILLEGIBLE_n] if unreadable)

Strict requirements:
- Every extracted section must be followed immediately by its SECTION_LEGIBILITY line.
- Keep output minimal, page-wise, and exactly in the format above.
- Do not add any surrounding text, commentary, or metadata.

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
