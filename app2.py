# app.py
import streamlit as st
from pypdf import PdfReader, PdfWriter
from google import genai
from google.genai import types
import io
import time
import json

# Streamlit Page Setup
st.set_page_config(page_title="PDF Text Extractor (Gemini OCR)", layout="wide")
st.title("📄 PDF Text Extractor — Gemini AI (Free API)")

# Upload PDF
uploaded = st.file_uploader("Upload your PDF", type=["pdf"])
api_key = st.text_input(
    "Enter your Gemini API key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

if uploaded is None:
    st.info("Please upload a PDF to continue.")
    st.stop()

if not api_key.strip():
    st.warning("Enter your Gemini API key to start processing.")
    st.stop()

# Initialize Gemini client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Read PDF
pdf_bytes = uploaded.read()
try:
    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(pdf_reader.pages)
    st.success(f"PDF loaded successfully — {total_pages} pages found.")
except Exception as e:
    st.error(f"Error reading PDF: {e}")
    st.stop()

# Extract text from each page
final_texts = []
methods = {}
progress = st.progress(0)

for i, page in enumerate(pdf_reader.pages, start=1):
    st.info(f"Processing page {i}/{total_pages} ...")
    progress.progress((i - 1) / total_pages)

    # Extract text directly if available
    try:
        page_text = page.extract_text() or ""
    except Exception:
        page_text = ""

    if page_text.strip():
        methods[i] = "digital"
        final_texts.append(page_text)
        st.success(f"✅ Page {i}: Extracted digital text ({len(page_text)} chars)")
    else:
        methods[i] = "gemini"
        # Convert single page to bytes
        writer = PdfWriter()
        writer.add_page(pdf_reader.pages[i - 1])
        single_page_io = io.BytesIO()
        writer.write(single_page_io)
        single_page_io.seek(0)
        page_bytes = single_page_io.getvalue()

        # Call Gemini OCR
        try:
            result = client.models.generate_content(
                model="gemini-1.5-flash-latest",  # ✅ Updated model
                contents=[
                    types.Part.from_bytes(page_bytes, mime_type="application/pdf"),
                    "Extract all readable text from this PDF page."
                ],
            )
            text = result.text.strip() if result and result.text else ""
            if text:
                final_texts.append(text)
                st.success(f"✅ Page {i}: Gemini extracted {len(text)} chars")
            else:
                final_texts.append("[No text found by Gemini]")
                st.warning(f"⚠️ Page {i}: Gemini returned no text.")
        except Exception as e:
            final_texts.append("[Gemini failed]")
            st.error(f"❌ Gemini request failed for page {i}: {e}")

    time.sleep(0.8)  # Gentle delay between requests

progress.progress(1.0)
st.success("✅ Extraction complete!")

# Combine all text into a single string
final_text = "\n\n".join(final_texts)

st.subheader("🧾 Final Combined Extracted Text")
st.text_area("All Extracted Text", final_text, height=480)

# Download button
st.download_button(
    "💾 Download Extracted Text",
    data=final_text,
    file_name="extracted_text.txt",
    mime="text/plain",
)

# Display method summary
st.subheader("Per-Page Extraction Summary")
st.json(methods)

st.markdown("---")
st.markdown("""
**Notes:**
- Gemini tries to extract visible text from each page image/PDF.
- If digital text is already present, it's extracted directly (no API usage).
- If a page is image-only, Gemini OCR extracts the text.
- Free Gemini API keys may have rate limits (1–2 pages per minute max).
""")
