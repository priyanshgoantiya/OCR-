# app.py
# app.py
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract
import shutil

st.set_page_config(page_title="PDF OCR App (no Poppler)", layout="wide")
st.title("📄 PDF OCR App (digital text first, optional OCR fallback)")

# Detect tesseract binary (pytesseract wrapper needs the system tesseract)
tesseract_path = shutil.which("tesseract")
tesseract_ok = bool(tesseract_path)

manual_tesseract = st.text_input(
    "Optional: Tesseract executable path (leave blank to auto-detect)",
    value=""
)
if manual_tesseract.strip():
    pytesseract.pytesseract.tesseract_cmd = manual_tesseract
    tesseract_ok = True

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
enable_ocr = st.checkbox("Enable OCR fallback (only if Tesseract installed)", value=False)
show_page_breaks = st.checkbox("Show page separators in output", value=True)

if enable_ocr and not tesseract_ok:
    st.warning(
        "Tesseract not found. OCR fallback will only work if you install Tesseract or provide its path. "
        "On Streamlit Cloud you typically cannot install system binaries — run locally for OCR."
    )

def extract_pages_with_pymupdf(pdf_bytes: bytes, use_ocr: bool):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        text = ""
        method = "none"

        # Try digital (embedded) text
        try:
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                method = "digital"
        except Exception:
            text = ""

        # If no digital text and OCR requested & tesseract available, render + OCR
        if not text and use_ocr and tesseract_ok:
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # zoom for better OCR
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                ocr_text = pytesseract.image_to_string(pil_img).strip()
                if ocr_text:
                    text = ocr_text
                    method = "ocr"
            except Exception:
                text = ""
                method = "none"

        pages.append({"page": i+1, "text": text, "method": method})
    return pages

if uploaded_file:
    file_info = {"Filename": uploaded_file.name, "Size (KB)": f"{uploaded_file.size/1024:.2f}"}
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("File details")
        st.json(file_info)
    with c2:
        st.subheader("Actions")
        st.caption("Digital text is extracted first. If none found, OCR fallback runs only if enabled and Tesseract is present.")
        start = st.button("🚀 Start extraction")

    if start:
        pdf_bytes = uploaded_file.read()
        with st.spinner("Processing PDF..."):
            pages = extract_pages_with_pymupdf(pdf_bytes, use_ocr=enable_ocr)

        # Build single concatenated string
        parts = []
        methods = {}
        any_text = False
        for p in pages:
            methods[p["page"]] = p["method"]
            body = p["text"] if p["text"] else "[no text found]"
            sep = f"\n\n--- Page {p['page']} | method: {p['method']} ---\n" if show_page_breaks else "\n"
            parts.append(sep + body)
            if p["text"]:
                any_text = True

        full_text = "\n".join(parts).strip()

        st.subheader("Extraction summary")
        st.write(f"Pages processed: {len(pages)}")
        st.write("Methods used per page:", methods)

        # first page preview (rendered) for debugging
        try:
            if len(pages) > 0:
                first_pix = fitz.open(stream=pdf_bytes, filetype="pdf").load_page(0).get_pixmap(matrix=fitz.Matrix(1,1))
                st.image(first_pix.tobytes("png"), caption="First page preview")
        except Exception:
            pass

        st.subheader("Extracted text (single string)")
        st.text_area("Full text", full_text, height=450)

        if full_text:
            st.download_button("Download text (.txt)", full_text, file_name="extracted_text.txt", mime="text/plain")
        else:
            st.warning("No text extracted. If the PDF is scanned, enable OCR and run locally with Tesseract installed.")

        st.info(f"Tesseract available: {tesseract_ok}. OCR requested: {enable_ocr}")


