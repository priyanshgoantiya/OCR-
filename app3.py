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

GOAL
Extract ALL clinically relevant text from target sections that collectively form the hospital course narrative, then merge into a single chronological record of the patient's hospitalization.

TARGET SECTIONS (search in this order)
1. Manual - Progress note / Progress Note / Doctor's Progress Notes (and variants)
2. OT Note / Operation Note / Operative Note / Operative Details / Operation Report
3. Anesthesia notes / Anaesthesia notes / Anesthetic Note / Anaesthesia Chart
4. MDM sheet / MDM / Multidisciplinary Meeting / MDT / Case Discussion
5. Diet sheet / Diet Orders / Dietary Chart

ALGORITHM
1) Page-by-page extraction:
   - Locate exact or near-exact header variants (case-insensitive; allow small OCR errors)
   - For each matched header, extract header line plus all verbatim readable text until next recognized header, explicit terminator, or end-of-page
   - Preserve original line breaks and token order

2) Focused fallback for missing sections:
   - If any target section not found, search document for relevant keywords
   - Extract nearest contiguous paragraphs and prepend appropriate header with "(AUTO-EXTRACT)"

3) Content merging:
   - Combine ALL extracted sections into ONE continuous narrative
   - Arrange in chronological/document reading order
   - Remove duplicate header lines but preserve chronological flow
   - Maintain all clinically relevant content from progress notes, operative details, anesthesia records, MDM discussions, and diet information

OUTPUT FORMAT (SIMPLE TEXT)
Merge all extracted content into a single, continuous hospital course narrative that includes:
- Diagnostic investigations and test results
- Medical/surgical interventions  
- Response to treatment
- Complications (if any)
- Overall progress
- Patient condition
- Clinical reasoning behind decisions

Format as plain text with natural paragraph breaks. Do not include page numbers, JSON, or commentary.

HANDWRITING/OCR GUIDELINES
- Preserve readable tokens exactly
- Use [ILLEGIBLE] for unreadable words
- Allow minor conservative medical spelling corrections
- Include both printed and handwritten text

FINAL OUTPUT: Single merged hospital course text only.
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
