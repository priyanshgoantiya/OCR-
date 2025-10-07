# app.py
import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image
import io
import tempfile
import pytesseract
import easyocr
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="PDF → OCR", layout="wide")
st.title("PDF → OCR (select engine & performance options)")

uploaded = st.file_uploader("/content/PublicWaterMassMailing.pdf", type=["pdf"])
engine = st.radio("OCR engine", ("pytesseract", "easyocr"))
use_gpu = st.checkbox("Use GPU (EasyOCR only)", value=False)
max_workers = st.slider("Worker threads (parallel OCR)", 1, 8, 2)
resize_width = st.number_input("Resize width (px, 0 = keep original)", 0, 3000, 1600)

if uploaded:
    raw = uploaded.read()
    try:
        pages = convert_from_bytes(raw, dpi=200)
    except Exception as e:
        st.error(f"Failed to convert PDF: {e}")
        st.stop()

    st.info(f"Converted {len(pages)} page(s). Running OCR with {engine}...")

    if engine == "easyocr":
        reader = easyocr.Reader(["en"], gpu=use_gpu)
    else:
        reader = None

    def ocr_image(idx_img):
        idx, img = idx_img
        if resize_width and img.width > resize_width:
            h = int(resize_width * img.height / img.width)
            img = img.resize((resize_width, h))
        b = io.BytesIO()
        img.save(b, format="PNG")
        arr = b.getvalue()
        if engine == "pytesseract":
            text = pytesseract.image_to_string(Image.open(io.BytesIO(arr)))
        else:
            res = reader.readtext(arr, detail=0)
            text = "\n".join(res)
        return idx, text

    with st.spinner("Running OCR..."):
        inputs = list(enumerate(pages))
        outputs = {}
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for idx, text in ex.map(ocr_image, inputs):
                outputs[idx] = text

    for i in range(len(pages)):
        st.subheader(f"Page {i+1}")
        cols = st.columns([1,2])
        with cols[0]:
            st.image(pages[i], use_column_width=True)
        with cols[1]:
            st.text_area("OCR text", outputs.get(i, ""), height=300)
    st.success("Done")
