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
ocr_prompt =""" You are a licensed medical practitioner and OCR-capable clinical reviewer. The input is a patient medical document (printed and/or handwritten). Your job: extract **only** the text that documents the Hospital Course / Clinical Summary information (diagnostic tests/results, procedures/interventions, intra-op events, medications given verbatim, complications, immediate postoperative course, disposition/ discharge status) from the following target sections and return a simple page-wise plain-text output.

TARGET HEADINGS (case-insensitive; allow small OCR/handwriting errors):
Progress Note, Manual - Progress note, Doctor's Progress Note, OT Note, Operative Note, Operation Note, Operative Details, Operation Report, Anaesthesia notes, Anesthesia notes, MDM, MDM sheet, MDT, Diet sheet, Post-operative Orders, Post-op Notes, Postoperative Note.

EXTRACTION RULES (short & strict)
1. Find each target heading; extract that heading line and **all readable text that belongs to that section** up to the next recognized heading or page end. If a section continues across pages without a new heading, continue extraction onto the next page.
2. Include printed and handwritten text verbatim. Do **not** invent or infer clinical facts. If a token is unreadable, replace that single token with `[ILLEGIBLE_n]` (n resets per page).
3. For Hospital Course content, actively include any lines that mention: investigations/results (e.g., Hb, Cr, USG, CT), procedures/interventions (e.g., PTCA, PTCA to LCX), devices/implants (DES, stent, sheath, Foley), medications and doses **only if verbatim** (e.g., "Heparin IV 11,000 units"), intra-op events/complications (hypotension, bradycardia, vasovagal), immediate postop course (shifted to ICU/ward, sheath removed), and discharge statements (discharged, stable, improved). Preserve exact tokens and numbers as they appear.
4. If a heading is present but no readable text follows on that page, output the heading then the line: `NO_TEXT_FOUND`.
5. Do not add summaries, interpretations, or additional clinical facts. Minimal linking words are allowed only if needed to join adjacent fragments read from the document — do not invent content.
6. If no target headings/text are found on a page, output `NO_RELEVANT_SECTION_FOUND` for that page.

OUTPUT FORMAT (exact plain text)
For each page 1..N output either the concatenated extracted sections (in the order they appear) or `NO_RELEVANT_SECTION_FOUND`. Use this exact layout:

Page 1:
<Header line found on page 1>
<verbatim lines from that section, including handwriting, with [ILLEGIBLE_n] for unreadable tokens>
<next header on same page, if any>
<verbatim lines...>

Page 2:
...

Example for a page with no target content:
Page 3:
NO_RELEVANT_SECTION_FOUND

End — return only the page blocks as above. No JSON, no extra commentary, no confidences.
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
