# app.py
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract

st.set_page_config(page_title="Simple PDF OCR", layout="wide")
st.title("Simple PDF → Text (single string)")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
force_ocr = st.checkbox("Force OCR for all pages (use pytesseract)", value=False)
show_page_breaks = st.checkbox("Show page separators in output", value=True)

if uploaded:
    try:
        pdf_bytes = uploaded.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Cannot open PDF: {e}")
        st.stop()

    n = doc.page_count
    st.info(f"Opened PDF — {n} page(s). Working...")

    parts = []
    for i in range(n):
        page = doc.load_page(i)
        text = ""
        if not force_ocr:
            try:
                text = page.get_text("text") or ""
                text = text.strip()
            except Exception:
                text = ""

        if not text:
            # render page to image and OCR with pytesseract
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                ocr_text = pytesseract.image_to_string(pil).strip()
                text = ocr_text
            except Exception as e:
                text = ""
                st.warning(f"OCR failed on page {i+1}: {e}")

        sep = f"\n\n--- Page {i+1} ---\n" if show_page_breaks else "\n"
        parts.append(sep + (text if text else "[no text found]"))

    full_text = "\n".join(parts).strip()

    st.subheader("Extracted text (single string)")
    st.text_area("Full text", full_text, height=500)

    if full_text:
        st.download_button("Download extracted text (.txt)", full_text, file_name="extracted_text.txt", mime="text/plain")
    else:
        st.warning("No text extracted. If your PDF is scanned, try enabling 'Force OCR' and ensure Tesseract is installed.")
