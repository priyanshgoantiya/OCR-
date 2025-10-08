# app.py
# app.py (relevant parts)
import streamlit as st
from pypdf import PdfReader
import io
import numpy as np
from PIL import Image
import logging

# Use PyMuPDF for rendering PDF pages to images (no poppler required)
try:
    import fitz  # pymupdf
    HAS_FITZ = True
except Exception:
    fitz = None
    HAS_FITZ = False

# Try to import EasyOCR safely
try:
    import easyocr
    OCR_AVAILABLE = True
    # Use cpu by default on Streamlit Cloud (gpu=False)
    ocr_reader = easyocr.Reader(['en'], gpu=False)
except Exception as e:
    OCR_AVAILABLE = False
    ocr_reader = None

st.set_page_config(page_title="📄 PDF OCR App", layout="wide")
st.title("📄 PDF Text Extractor (with EasyOCR / PyMuPDF)")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded is None:
    st.info("Upload a PDF to extract text.")
    st.stop()

pdf_bytes = uploaded.read()

# Read PDF for digital text first
try:
    reader_pdf = PdfReader(io.BytesIO(pdf_bytes))
    n = len(reader_pdf.pages)
except Exception as e:
    st.error(f"Cannot read PDF: {e}")
    st.stop()

st.info(f"Opened PDF — {n} pages found.")
extracted_text = ""
methods = {}

for i, page in enumerate(reader_pdf.pages, start=1):
    text = page.extract_text() or ""
    if text.strip():
        methods[i] = "digital"
        extracted_text += f"\n--- Page {i} | method: digital ---\n{text}\n"
    else:
        # OCR path
        methods[i] = "ocr" if OCR_AVAILABLE else "none"
        if not OCR_AVAILABLE:
            extracted_text += f"\n--- Page {i} | method: none ---\n[no text found: OCR lib not available]\n"
            continue

        if not HAS_FITZ:
            st.error(
                "PDF->image renderer (PyMuPDF) not available. "
                "Add 'pymupdf' to requirements.txt and redeploy, or install poppler for pdf2image."
            )
            extracted_text += f"\n--- Page {i} | method: ocr ---\n[no text found: renderer missing]\n"
            continue

        st.info(f"Running OCR on page {i} ...")
        try:
            # Open PDF as fitz doc from bytes
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            fitz_page = doc.load_page(i - 1)  # 0-indexed
            pix = fitz_page.get_pixmap(dpi=200)  # render page
            img_bytes = pix.tobytes(output="png")  # PNG bytes
            page_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # easyocr accepts numpy arrays
            result = ocr_reader.readtext(np.array(page_image))
            page_text = " ".join([item[1] for item in result]) if result else ""
            if page_text.strip():
                extracted_text += f"\n--- Page {i} | method: ocr ---\n{page_text}\n"
            else:
                extracted_text += f"\n--- Page {i} | method: ocr ---\n[no text found]\n"
        except Exception as e:
            st.warning(f"OCR failed on page {i}: {e}")
            extracted_text += f"\n--- Page {i} | method: ocr ---\n[no text found: {e}]\n"

st.subheader("Extraction summary")
st.json(methods)
st.text_area("Full text", extracted_text.strip(), height=500)
st.download_button("💾 Download Text", extracted_text, "extracted_text.txt")


