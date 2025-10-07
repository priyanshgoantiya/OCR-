# app.py
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract
import shutil

st.set_page_config(page_title="PDF OCR App (no Poppler)", layout="wide")
st.title("📄 PDF OCR App (digital text first, optional OCR fallback)")

# Check if tesseract binary is available
tesseract_path = shutil.which("tesseract")
tesseract_ok = bool(tesseract_path)

# Allow user to set tesseract path manually (helpful on Windows)
manual_tesseract = st.text_input(
    "Optional: If pytesseract OCR is needed, provide Tesseract executable path (leave blank to auto-detect)",
    value=""
)
if manual_tesseract.strip():
    pytesseract.pytesseract.tesseract_cmd = manual_tesseract
    tesseract_ok = True

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
use_ocr = st.checkbox("Enable OCR fallback (use only if Tesseract is installed)", value=False)
show_page_breaks = st.checkbox("Show page separators in output", value=True)

if use_ocr and not tesseract_ok:
    st.warning(
        "Tesseract binary not detected. OCR fallback will not work unless you install Tesseract "
        "or provide its path above. For Streamlit Cloud, Tesseract usually isn't available — run locally."
    )

def extract_text_from_pdf_bytes(pdf_bytes, enable_ocr=False):
    """Return list of dicts per page: {'page': i, 'text': text, 'method': 'digital'|'ocr'|'none'}"""
    out_pages = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = ""
        method = "none"

        # 1) Try embedded (digital/selectable) text
        try:
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                method = "digital"
        except Exception:
            text = ""

        # 2) If no digital text and OCR enabled, render to image and run pytesseract
        if not text and enable_ocr and tesseract_ok:
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # zoom for better OCR
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                ocr_text = pytesseract.image_to_string(pil_img).strip()
                if ocr_text:
                    text = ocr_text
                    method = "ocr"
            except Exception as e:
                # keep method 'none' and text ""
                st.debug if False else None

        out_pages.append({"page": i + 1, "text": text, "method": method})

    return out_pages

# Main UI logic
if uploaded_file is not None:
    file_details = {"Filename": uploaded_file.name, "File size (KB)": f"{uploaded_file.size/1024:.2f}"}
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("File Details")
        st.json(file_details)
    with col2:
        st.subheader("Actions")
        st.caption("Click below to extract text (digital text first; OCR only if enabled).")
        start = st.button("🚀 Start OCR Processing")

    if start:
        with st.spinner("Processing PDF — extracting text..."):
            # read once as bytes
            try:
                pdf_bytes = uploaded_file.read()
            except Exception as e:
                st.error(f"Failed to read uploaded file: {e}")
                st.stop()

            pages = extract_text_from_pdf_bytes(pdf_bytes, enable_ocr=use_ocr)

        # Build single-string output and show diagnostics
        parts = []
        methods_used = {}
        any_text = False
        for p in pages:
            methods_used[p["page"]] = p["method"]
            snippet = p["text"] if p["text"] else "[no text found]"
            sep = f"\n\n--- Page {p['page']} | method: {p['method']} ---\n" if show_page_breaks else "\n"
            parts.append(sep + snippet)
            if p["text"]:
                any_text = True

        full_text = "\n".join(parts).strip()

        st.subheader("Extraction summary")
        st.write(f"Pages processed: {len(pages)}")
        st.write("Methods used per page:", methods_used)

        # Show first page preview for debugging (rendered)
        try:
            if len(pages) > 0:
                first_pix = fitz.open(stream=pdf_bytes, filetype="pdf").load_page(0).get_pixmap(matrix=fitz.Matrix(1,1))
                st.image(first_pix.tobytes("png"), caption="First page preview")
        except Exception:
            pass

        st.subheader("Extracted text (single string)")
        st.text_area("Full text", full_text, height=450)

        if full_text:
            st.download_button("Download extracted text (.txt)", full_text, file_name="extracted_text.txt", mime="text/plain")
        else:
            st.warning(
                "No text extracted. If this is a scanned PDF, enable OCR and ensure Tesseract is installed, "
                "or run the app locally where you can install system binaries."
            )

        # Extra note about tesseract
        st.info(f"Tesseract available: {tesseract_ok}. OCR enabled: {use_ocr}")


