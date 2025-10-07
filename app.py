# app.py
import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

st.set_page_config(page_title="PDF OCR Extractor", layout="wide")
st.title("📘 PDF OCR Text Extractor")

uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])
use_ocr = st.checkbox("Enable OCR for scanned PDFs", value=True)
show_page_breaks = st.checkbox("Show page separators", value=True)

if uploaded_file is None:
    st.info("Upload a PDF to extract text (OCR can read scanned/image PDFs).")
else:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n_pages = len(doc)
    st.info(f"PDF loaded with {n_pages} pages")

    all_text = []
    methods = {}

    with st.spinner("Extracting text..."):
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text")
            if not text.strip() and use_ocr:
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_text = pytesseract.image_to_string(img)
                text = ocr_text.strip()
                methods[i] = "ocr"
            elif text.strip():
                methods[i] = "digital"
            else:
                methods[i] = "none"

            sep = f"\n\n--- Page {i} ({methods[i]}) ---\n" if show_page_breaks else "\n"
            all_text.append(sep + (text if text else "[no text found]"))

    full_text = "\n".join(all_text).strip()

    st.subheader("Extraction Summary")
    st.write(f"Pages processed: {n_pages}")
    st.json(methods)

    if full_text:
        st.subheader("Extracted Text")
        st.text_area("Full Text", full_text, height=450)
        st.download_button("Download Text", full_text, file_name="extracted_text.txt", mime="text/plain")
    else:
        st.warning("No text could be extracted. Check if the PDF pages are blank or heavily blurred.")
