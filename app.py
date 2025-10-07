# app.py
# app.py
import streamlit as st
import io
import os
import logging
from typing import List, Dict, Optional

# lightweight imports always available
from pypdf import PdfReader

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf-ocr-app")

st.set_page_config(page_title="PDF → OCR (single string)", layout="wide")
st.title("📄 PDF → OCR (single string)")

st.markdown(
    """
Upload a PDF and this app will extract **selectable text** automatically.
If the PDF is scanned (images only), enable OCR — OCR runs only if the environment
supports it (PyMuPDF + EasyOCR or pytesseract + Tesseract).
"""
)

# UI options
uploaded = st.file_uploader("Upload PDF", type=["pdf"], help="Select a PDF file")
force_ocr = st.checkbox("Force OCR (try OCR even if digital text found)", value=False)
preferred_ocr = st.selectbox(
    "Preferred OCR backend (used only if available)",
    options=["auto", "easyocr", "pytesseract"],
    index=0,
    help="auto = pick best available; easyocr requires torch, pytesseract requires Tesseract binary"
)
show_page_separators = st.checkbox("Show page separators in output", True)


# -------------------- helper functions --------------------
def extract_digital_text(pdf_bytes: bytes) -> List[Dict]:
    """Extract selectable/digital text from pdf bytes using pypdf (pure python)."""
    out = []
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for i, page in enumerate(reader.pages, start=1):
            try:
                txt = page.extract_text() or ""
            except Exception as e:
                logger.exception("pypdf page.extract_text error")
                txt = ""
            out.append({"page": i, "text": txt.strip(), "method": "digital" if txt.strip() else "none"})
    except Exception as e:
        logger.exception("pypdf failed to read PDF")
        raise
    return out


# Lazy loaders for heavy OCR backends
@st.cache_resource
def init_easyocr_reader(lang: List[str] = ["en"], gpu: bool = False):
    try:
        import easyocr
        reader = easyocr.Reader(lang, gpu=gpu)
        return reader
    except Exception as e:
        logger.warning("EasyOCR not available: %s", e)
        return None


def is_tesseract_available() -> bool:
    import shutil
    return shutil.which("tesseract") is not None


def render_pages_with_pymupdf(pdf_bytes: bytes) -> List[bytes]:
    """
    Render PDF pages to PNG bytes using PyMuPDF (fitz).
    Returns list of PNG bytes (one per page).
    """
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        logger.warning("PyMuPDF (fitz) not available: %s", e)
        raise

    pix_pages = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # zoom for better OCR
        png_bytes = pix.tobytes("png")
        pix_pages.append(png_bytes)
    return pix_pages


def ocr_with_easyocr_from_images(img_bytes_list: List[bytes], reader) -> List[str]:
    """Run EasyOCR on list of PNG bytes. Returns list of text strings per page."""
    results = []
    import numpy as np
    from PIL import Image
    for b in img_bytes_list:
        img = Image.open(io.BytesIO(b)).convert("RGB")
        arr = np.array(img)
        try:
            res = reader.readtext(arr, detail=0)
            text = "\n".join(res)
        except Exception as e:
            logger.exception("EasyOCR readtext failed")
            text = ""
        results.append(text)
    return results


def ocr_with_pytesseract_from_images(img_bytes_list: List[bytes], tesseract_cmd: Optional[str] = None) -> List[str]:
    """Run pytesseract on list of PNG bytes. Returns list of text strings per page."""
    try:
        import pytesseract
        from PIL import Image
    except Exception as e:
        logger.warning("pytesseract or PIL missing: %s", e)
        raise

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    out = []
    for b in img_bytes_list:
        img = Image.open(io.BytesIO(b)).convert("RGB")
        try:
            txt = pytesseract.image_to_string(img)
        except Exception as e:
            logger.exception("pytesseract failed")
            txt = ""
        out.append(txt)
    return out


# -------------------- Main processing --------------------
if uploaded is None:
    st.info("Upload a PDF (or drag & drop).")
    st.caption("Tip: For scanned PDFs, enable OCR and deploy/run locally with OCR dependencies installed.")
    st.stop()

# read bytes once
pdf_bytes = uploaded.read()

# 1) Try digital extraction first (fast, pure-Python)
with st.spinner("Extracting selectable (digital) text..."):
    try:
        pages = extract_digital_text(pdf_bytes)
    except Exception as e:
        st.error("Failed extracting with pypdf: " + str(e))
        pages = []

# check whether any digital text was found
digital_found = any(p["method"] == "digital" for p in pages)

# decide whether to OCR
do_ocr = force_ocr or not digital_found
ocr_available = False
easyocr_reader = None
pytesseract_ok = False

if do_ocr:
    st.info("Preparing OCR backends (this may take extra time on first run)...")
    # try easyocr first (auto mode)
    if preferred_ocr in ("auto", "easyocr"):
        easyocr_reader = init_easyocr_reader(["en"], gpu=False)
        if easyocr_reader:
            ocr_available = True

    # try pytesseract
    if preferred_ocr in ("auto", "pytesseract") or not ocr_available:
        if is_tesseract_available():
            pytesseract_ok = True
            ocr_available = True

# If we will OCR but no backend available, show instructions and skip OCR
if do_ocr and not ocr_available:
    st.warning(
        "OCR requested but no OCR backend is available in this environment.\n\n"
        "- For Streamlit Cloud: installing system binaries (Tesseract / Poppler) is not allowed. "
        "Use local deployment for OCR or use EasyOCR if you include torch in requirements.\n"
        "- To run OCR locally, install PyMuPDF (pymupdf), Tesseract (for pytesseract) OR install EasyOCR with torch.\n\n"
        "App will show selectable text (if any). If you want, re-deploy with OCR-capable requirements or run locally."
    )

# If OCR is available, try to render pages and run OCR
if do_ocr and ocr_available:
    try:
        # render pages to images via PyMuPDF (fitz)
        try:
            img_bytes_list = render_pages_with_pymupdf(pdf_bytes)
        except Exception as e:
            # if PyMuPDF not available, try pdf2image (requires poppler)
            try:
                from pdf2image import convert_from_bytes
                imgs = convert_from_bytes(pdf_bytes, dpi=200)
                img_bytes_list = []
                from PIL import Image
                for im in imgs:
                    buf = io.BytesIO()
                    im.save(buf, format="PNG")
                    img_bytes_list.append(buf.getvalue())
            except Exception as e2:
                logger.exception("Failed to produce images for OCR (PyMuPDF & pdf2image failed)")
                img_bytes_list = []

        ocr_texts = []
        if img_bytes_list:
            if easyocr_reader:
                ocr_texts = ocr_with_easyocr_from_images(img_bytes_list, easyocr_reader)
            elif pytesseract_ok:
                # use system tesseract; optional: let user set path via env var TESSERACT_CMD
                t_cmd = os.getenv("TESSERACT_CMD")
                if t_cmd:
                    pytesseract_ok = True
                    ocr_texts = ocr_with_pytesseract_from_images(img_bytes_list, tesseract_cmd=t_cmd)
                else:
                    ocr_texts = ocr_with_pytesseract_from_images(img_bytes_list)
        else:
            ocr_texts = []
    except Exception as e:
        logger.exception("OCR stage failed")
        st.error("OCR stage failed: " + str(e))
        ocr_texts = []

    # integrate OCR results into pages list (override empty text)
    if ocr_texts:
        # if pages empty (pypdf failed), prepare skeleton
        if not pages:
            pages = [{"page": i + 1, "text": "", "method": "none"} for i in range(len(ocr_texts))]
        for idx, ocr_txt in enumerate(ocr_texts):
            if idx < len(pages):
                if pages[idx]["text"].strip() == "" or force_ocr:
                    pages[idx]["text"] = ocr_txt.strip()
                    pages[idx]["method"] = "ocr" if ocr_txt.strip() else pages[idx]["method"]
            else:
                pages.append({"page": idx + 1, "text": ocr_txt.strip(), "method": "ocr" if ocr_txt.strip() else "none"})

# Build final single-string output
parts = []
methods_map = {}
for p in pages:
    methods_map[p["page"]] = p.get("method", "none")
    sep = f"\n\n--- Page {p['page']} | method: {p.get('method','none')} ---\n" if show_page_separators else "\n"
    parts.append(sep + (p["text"] if p["text"] else "[no text found]"))

full_text = "\n".join(parts).strip()

# Show summary and results
st.subheader("Extraction summary")
st.write(f"Pages processed: {len(pages)}")
st.write("Methods used per page:", methods_map)

# show first page preview if we were able to render images
if do_ocr and 'img_bytes_list' in locals() and img_bytes_list:
    try:
        st.image(img_bytes_list[0], caption="First page preview (rendered for OCR)", use_column_width=True)
    except Exception:
        pass

st.subheader("Extracted text (single string)")
st.text_area("Full text", full_text, height=520)

if full_text:
    st.download_button("Download extracted text (.txt)", data=full_text, file_name="extracted_text.txt", mime="text/plain")

# final guidance
st.markdown("---")
st.markdown("**Notes / deployment guidance**")
st.markdown(
    "- `pypdf` (digital text extraction) works on Streamlit Cloud without system binaries.\n"
    "- For OCR on scanned PDFs you must either run the app **locally** and install Tesseract/Poppler and/or PyMuPDF, or deploy with EasyOCR+torch (larger requirements).\n"
    "- If running locally and using pytesseract, set Tesseract path either in PATH or environment variable `TESSERACT_CMD`.\n"
)

