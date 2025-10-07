# app.py
# app.py
import streamlit as st
from pypdf import PdfReader
import io

st.set_page_config(page_title="PDF OCR App (text-only)", layout="wide")
st.title("📄 PDF Text Extractor (selectable text only)")

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
show_page_breaks = st.checkbox("Show page separators in output", value=True)

if uploaded_file is None:
    st.info("Upload a PDF to extract selectable (embedded) text. Scanned PDFs (images) are not OCR'd here.")
else:
    # read bytes once
    pdf_bytes = uploaded_file.read()
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception as e:
        st.error(f"Failed to open PDF: {e}")
        st.stop()

    n_pages = len(reader.pages)
    st.info(f"PDF opened — {n_pages} pages found")

    parts = []
    any_text = False
    methods = {}

    with st.spinner("Extracting selectable text from PDF..."):
        for i, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            page_text = page_text.strip()
            methods[i] = "digital" if page_text else "none"
            sep = f"\n\n--- Page {i} ---\n" if show_page_breaks else "\n"
            parts.append(sep + (page_text if page_text else "[no selectable text]"))
            if page_text:
                any_text = True

    full_text = "\n".join(parts).strip()

    st.subheader("Extraction summary")
    st.write(f"Pages processed: {n_pages}")
    st.write("Methods used per page (digital means selectable text found):", methods)

    if any_text:
        st.subheader("Extracted text (single string)")
        st.text_area("Full text", full_text, height=450)
        st.download_button("Download extracted text (.txt)", full_text, file_name="extracted_text.txt", mime="text/plain")
    else:
        st.warning(
            "No selectable (digital) text found in this PDF. It looks like a scanned/image PDF.\n\n"
            "If you need OCR on scanned PDFs, run this app locally and enable OCR (instructions below)."
        )

    st.markdown(
        "### How to run with OCR locally\n"
        "1. Install requirements (locally): `pip install -r requirements_ocr.txt`\n"
        "2. Install system tools: `sudo apt install -y poppler-utils tesseract-ocr` (Linux) or use brew on macOS or Windows installer for Tesseract.\n"
        "3. Use the PyMuPDF / pdf2image + pytesseract version of the app (I can provide that file if you want)."
    )
