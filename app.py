# app.py
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import numpy as np
import pytesseract
import easyocr
import shutil
import traceback

st.set_page_config(page_title="PDF → Single-String OCR (robust)", layout="wide")
st.title("PDF → Single string extractor (auto-fallback to OCR)")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
force_ocr = st.checkbox("Force OCR for all pages (skip embedded text)", value=False)
prefer_engine = st.radio("Preferred OCR engine", ("pytesseract", "easyocr"))
use_gpu = st.checkbox("EasyOCR GPU (if using EasyOCR)", value=False)

def check_tesseract_available():
    return shutil.which("tesseract") is not None

tesseract_ok = check_tesseract_available()
if not tesseract_ok:
    st.info("Tesseract binary not found in PATH. pytesseract OCR will not work until Tesseract is installed.")

# Try to initialize EasyOCR reader lazily and catch errors
easyocr_reader = None
easyocr_ok = False
if prefer_engine == "easyocr" or not tesseract_ok:
    try:
        easyocr_reader = easyocr.Reader(["en"], gpu=use_gpu)
        easyocr_ok = True
    except Exception as e:
        easyocr_reader = None
        easyocr_ok = False
        st.warning("EasyOCR initialization failed (torch/CPU/GPU issue). EasyOCR will not be used.")
        st.write(traceback.format_exc())

if uploaded:
    try:
        pdf_bytes = uploaded.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        st.error(f"Failed to open PDF: {e}")
        st.stop()

    n_pages = doc.page_count
    st.info(f"Opened PDF — pages: {n_pages}")

    extracted_pages = []
    any_text_found = False

    with st.spinner("Extracting pages..."):
        for i in range(n_pages):
            page = doc.load_page(i)

            # 1) Try embedded (digital) text first (unless force_ocr is True)
            page_text = ""
            if not force_ocr:
                try:
                    page_text = page.get_text("text") or ""
                    page_text = page_text.strip()
                except Exception:
                    page_text = ""

            used_method = "embedded" if page_text else None

            # 2) If no embedded text (or forced), do OCR fallback
            if not page_text:
                # render page to image for OCR
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                    img_bytes = pix.tobytes("png")
                    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                except Exception as e:
                    st.error(f"Failed to render page {i+1} to image for OCR: {e}")
                    pil_img = None

                ocr_text = ""
                if pil_img is not None:
                    if prefer_engine == "pytesseract" and tesseract_ok:
                        try:
                            ocr_text = pytesseract.image_to_string(pil_img).strip()
                            used_method = "pytesseract"
                        except Exception as e:
                            ocr_text = ""
                            st.warning(f"pytesseract error on page {i+1}: {e}")
                    elif prefer_engine == "easyocr" and easyocr_ok:
                        try:
                            arr = np.array(pil_img)
                            res = easyocr_reader.readtext(arr, detail=0)
                            ocr_text = "\n".join(res).strip()
                            used_method = "easyocr"
                        except Exception as e:
                            ocr_text = ""
                            st.warning(f"EasyOCR error on page {i+1}: {e}")
                    else:
                        # Try whichever is available
                        if tesseract_ok:
                            try:
                                ocr_text = pytesseract.image_to_string(pil_img).strip()
                                used_method = "pytesseract"
                            except Exception:
                                ocr_text = ""
                        elif easyocr_ok:
                            try:
                                arr = np.array(pil_img)
                                res = easyocr_reader.readtext(arr, detail=0)
                                ocr_text = "\n".join(res).strip()
                                used_method = "easyocr"
                            except Exception:
                                ocr_text = ""
                        else:
                            ocr_text = ""
                page_text = ocr_text or ""

            if page_text:
                any_text_found = True
            else:
                # keep empty string, but indicate method attempted
                pass

            extracted_pages.append({"page": i + 1, "text": page_text, "method": used_method or "none"})

    # Prepare single concatenated string
    parts = []
    for p in extracted_pages:
        parts.append(f"\n\n--- Page {p['page']} | method: {p['method']} ---\n{p['text']}")
    full_text = "\n".join(parts).strip()

    # Show brief diagnostics and preview of first page image if available
    st.subheader("Extraction summary")
    st.write(f"Pages processed: {n_pages}")
    methods = {p['page']: p['method'] for p in extracted_pages}
    st.write("Methods used per page:", methods)

    # Show first page image (rendered) for debugging
    try:
        if n_pages > 0:
            first_pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1, 1))
            st.image(first_pix.tobytes("png"), caption="First page preview")
    except Exception:
        pass

    st.subheader("Extracted text (single string)")
    st.text_area("Full text", full_text, height=400)

    if full_text:
        st.download_button("Download .txt", full_text, file_name="extracted_text.txt", mime="text/plain")
    else:
        st.warning("No text extracted. If this is a scanned PDF, enable OCR or check that Tesseract/EasyOCR is installed. See notes below.")

    st.markdown("**Notes / Troubleshooting**")
    st.markdown(
        "- If pages show `method: embedded` but text is empty: the PDF may use non-standard encodings. Try forcing OCR.\n"
        "- To use pytesseract you must have the Tesseract binary installed and available in PATH (try `which tesseract` on Linux/macOS or ensure `tesseract.exe` in PATH on Windows).\n"
        "- If EasyOCR fails to initialize, ensure PyTorch is installed for your environment."
    )

    st.info(f"Tesseract available: {tesseract_ok}, EasyOCR available: {easyocr_ok}")
