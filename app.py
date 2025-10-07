# app.py
import streamlit as st
import fitz  # PyMuPDF
import io
from PIL import Image
import numpy as np
import pytesseract
import easyocr

st.set_page_config(page_title="Simple PDF → Single String (no Poppler)", layout="wide")
st.title("Simple PDF → Single-String Text Extractor (Poppler NOT required)")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
use_ocr = st.checkbox("Use OCR (for scanned PDFs)", value=False)
engine = st.radio("OCR engine (only used if OCR selected)", ("pytesseract", "easyocr"))

if uploaded:
    try:
        pdf_bytes = uploaded.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Failed to open PDF: {e}")
        st.stop()

    total_pages = doc.page_count
    st.info(f"Opened PDF with {total_pages} page(s). Processing...")

    if use_ocr and engine == "easyocr":
        reader = easyocr.Reader(["en"], gpu=False)
    else:
        reader = None

    all_text_parts = []

    with st.spinner("Extracting text..."):
        for i in range(total_pages):
            page = doc.load_page(i)

            if not use_ocr:
                # Try to extract embedded (digital) text first
                text = page.get_text("text").strip()
                if not text:
                    # If empty and OCR not requested, still attempt OCR fallback
                    text = ""
                all_text_parts.append(f"\n\n--- Page {i+1} ---\n{text}")
            else:
                # Render page to image via PyMuPDF (no Poppler)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # zoom=2 for better OCR
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

                if engine == "pytesseract":
                    try:
                        text = pytesseract.image_to_string(pil_img)
                    except Exception as ex:
                        st.error(f"pytesseract error: {ex}")
                        text = ""
                else:
                    arr = np.array(pil_img)
                    try:
                        results = reader.readtext(arr, detail=0)
                        text = "\n".join(results)
                    except Exception as ex:
                        st.error(f"EasyOCR error: {ex}")
                        text = ""

                all_text_parts.append(f"\n\n--- Page {i+1} ---\n{text.strip()}")

    full_text = "\n".join(all_text_parts).strip()
    if not full_text:
        st.warning("No text extracted. If this is a scanned PDF, enable 'Use OCR' and try EasyOCR or pytesseract.")
    st.subheader("Extracted text (single string)")
    st.text_area("Full OCR text", full_text, height=450)

    if full_text:
        st.download_button("Download extracted text (.txt)", full_text, file_name="extracted_text.txt", mime="text/plain")
    st.success("Done")
