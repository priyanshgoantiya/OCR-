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
You are an OCR (Optical Character Recognition) system. 
Extract all readable text (printed or handwritten) from each page of the uploaded PDF.

Return the result in this simple plain text format:
Page 1:
<text of page 1>

Page 2:
<text of page 2>

If a page is blank, write: "Page X: NO_TEXT_FOUND"
Do not include JSON, lists, or explanations.
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
