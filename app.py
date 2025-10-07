# app.py
import streamlit as st
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import io
import easyocr

st.set_page_config(page_title="Simple PDF OCR", layout="wide")
st.title("📄 Simple PDF → Text Extractor")

uploaded = st.file_uploader("Upload a PDF file", type=["pdf"])
engine = st.radio("Choose OCR engine", ("pytesseract", "easyocr"))
use_gpu = st.checkbox("Use GPU (only for EasyOCR)", value=False)

if uploaded:
    st.info("Processing PDF... please wait ⏳")
    try:
        pages = convert_from_bytes(uploaded.read(), dpi=200)
    except Exception as e:
        st.error(f"Failed to convert PDF: {e}")
        st.stop()

    if engine == "easyocr":
        reader = easyocr.Reader(["en"], gpu=use_gpu)

    all_text = ""

    for i, img in enumerate(pages):
        st.write(f"OCR on Page {i+1}...")
        if engine == "pytesseract":
            text = pytesseract.image_to_string(img)
        else:
            results = reader.readtext(img, detail=0)
            text = "\n".join(results)
        all_text += f"\n\n--- Page {i+1} ---\n{text}"

    st.subheader("📝 Extracted Text")
    st.text_area("Full Text", all_text, height=500)
    st.success("✅ Extraction complete!")

