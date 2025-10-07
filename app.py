# app.py
import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
import io
import pytesseract
import easyocr

st.set_page_config(page_title="Simple PDF → Single-String OCR", layout="wide")
st.title("Simple PDF → Text (single string)")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
engine = st.radio("OCR engine", ("pytesseract", "easyocr"))
use_gpu = st.checkbox("Use GPU (EasyOCR only)", value=False)

if uploaded:
    try:
        pages = convert_from_bytes(uploaded.read(), dpi=150)
    except Exception as e:
        st.error("Failed to convert PDF to images. Is Poppler installed and in your PATH? Install poppler-utils (Linux) or add poppler to PATH on Windows/macOS.")
        st.stop()

    all_text = []
    if engine == "easyocr":
        reader = easyocr.Reader(["en"], gpu=use_gpu)
    else:
        reader = None

    with st.spinner("Running OCR... this can take a bit for large PDFs"):
        for i, page in enumerate(pages, start=1):
            if engine == "pytesseract":
                text = pytesseract.image_to_string(page)
            else:
                # EasyOCR accepts array-like input; convert PIL->bytes
                buf = io.BytesIO()
                page.save(buf, format="PNG")
                arr = buf.getvalue()
                results = reader.readtext(arr, detail=0)
                text = "\n".join(results)
            all_text.append(f"\n\n--- Page {i} ---\n{text.strip()}")

    full_text = "\n".join(all_text).strip()

    st.subheader("Extracted text (single string)")
    st.text_area("Full OCR text", full_text, height=400)

    if full_text:
        st.download_button("Download extracted text (.txt)", full_text, file_name="extracted_text.txt", mime="text/plain")
    st.success("Done")

