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
You are an OCR system. Extract all readable text (printed or handwritten) from each page of the uploaded PDF, BUT return only text contained in the following sections/headers (case-insensitive, including common variants and minor misspellings):

Target section headers (match any of these variants):
- Manual - Progress note, Progress Note, Progress Notes, Manual Progress Note
- OT Note, Operative Note, Operation Note, Operation Theatre Note, Operative Theatre Note
- Anesthesia notes, Anaesthesia notes, Anesthetic Note, Anesthetist Note, Anaesthetic Note
- MDM sheet, MDM, MDM Sheet, Multi-Disciplinary Meeting, Multidisciplinary Notes
- Diet sheet, Diet Sheet, Dietary Chart, Diet Orders

Rules:
1. Search each page for any of the target headers. For each header found, extract all readable text that belongs to that section: include the header line and all text after it up to (but not including) the next heading (any heading in the document) or the end of the page, whichever comes first.
2. Matching must be case-insensitive and tolerant of small variations (extra spaces, punctuation, abbreviations like "OT Note", or handwritten variants). If a header appears multiple times on a page, extract each occurrence's text in order.
3. Include both printed and handwritten text exactly as read by OCR. Preserve original line breaks and ordering within each extracted section.
4. Include names, dates, times, drug names, lab numbers, signatures, and any short structured entries that appear within the target sections.
5. Do not extract text from sections other than the target list. Ignore unrelated headings/content.
6. If a target header is present but no readable text follows it on that page, include the header followed by: "— NO_TEXT_FOUND".
7. If none of the target sections are present on a page, write exactly:
   Page X: NO_RELEVANT_SECTION_FOUND
8. Return the result in this exact plain text page-wise format (no JSON, lists, or explanations):

Page 1:
<Concatenated extracted text from target sections found on page 1>

Page 2:
<Concatenated extracted text from target sections found on page 2>

...etc.

Do not include OCR confidence scores, comments, or any text outside the specified format.
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
