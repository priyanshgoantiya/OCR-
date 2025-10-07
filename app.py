# app.py
import streamlit as st
from pypdf import PdfReader
from pdf2image import convert_from_bytes
import io

# Try to import EasyOCR safely
try:
    import easyocr
    OCR_AVAILABLE = True
    reader = easyocr.Reader(['en'])
except Exception as e:
    OCR_AVAILABLE = False

st.set_page_config(page_title="📄 PDF OCR App", layout="wide")
st.title("📄 PDF Text Extractor (with EasyOCR fallback)")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded is None:
    st.info("Upload a PDF to extract text.")
else:
    pdf_bytes = uploaded.read()
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
            methods[i] = "ocr" if OCR_AVAILABLE else "none"
            if OCR_AVAILABLE:
                st.info(f"Running OCR on page {i} ...")
                try:
                    images = convert_from_bytes(pdf_bytes, first_page=i, last_page=i, dpi=200)
                    page_image = images[0]
                    result = reader.readtext(np.array(page_image))
                    page_text = " ".join([x[1] for x in result])
                    extracted_text += f"\n--- Page {i} | method: ocr ---\n{page_text}\n"
                except Exception as e:
                    st.warning(f"OCR failed on page {i}: {e}")
                    extracted_text += f"\n--- Page {i} | method: ocr ---\n[no text found]\n"
            else:
                extracted_text += f"\n--- Page {i} | method: none ---\n[no text found]\n"

    st.subheader("Extraction summary")
    st.json(methods)

    st.text_area("Full text", extracted_text.strip(), height=500)
    st.download_button("💾 Download Text", extracted_text, "extracted_text.txt")

    if not OCR_AVAILABLE:
        st.warning("""
        ⚠️ OCR requested but EasyOCR/Tesseract not available.
        To use OCR locally:
        1. Install Tesseract and Poppler
        2. Or, redeploy with EasyOCR (see requirements below)
        """)

st.markdown("""
---
### 🧩 Requirements (for Streamlit Cloud)

