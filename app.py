# app.py
# app.py
import streamlit as st
from pypdf import PdfReader
import io
import requests
import json

st.set_page_config(page_title="PDF OCR (OCR.space fallback)", layout="wide")
st.title("📄 PDF Text Extractor — digital text + OCR.space fallback")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
api_key = st.text_input("OCR.space API key (leave blank to use 'helloworld' test key)", value="helloworld", help="Get a free key from https://ocr.space/ if you plan to OCR many files or large PDFs.")

if uploaded is None:
    st.info("Upload a PDF to extract text.")
    st.stop()

pdf_bytes = uploaded.read()
try:
    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(pdf_reader.pages)
except Exception as e:
    st.error(f"Cannot read PDF: {e}")
    st.stop()

st.info(f"Opened PDF — {total_pages} pages found.")
extracted_text = []
methods = {}

# First pass: try to extract digital text from each page
for i, page in enumerate(pdf_reader.pages, start=1):
    try:
        page_text = page.extract_text() or ""
    except Exception:
        page_text = ""
    if page_text.strip():
        methods[i] = "digital"
        extracted_text.append(page_text)
    else:
        methods[i] = "needs_ocr"
        extracted_text.append(None)

needs_ocr_pages = [p for p, m in methods.items() if m == "needs_ocr"]

if not needs_ocr_pages:
    st.success("All pages contained digital (extractable) text — no OCR needed.")
else:
    st.warning(f"{len(needs_ocr_pages)} page(s) need OCR. Using OCR.space to OCR the full PDF (per-page results).")
    with st.spinner("Uploading PDF to OCR.space and running OCR..."):
        key_to_use = api_key.strip() or "helloworld"
        try:
            url = "https://api.ocr.space/parse/image"
            files = {"file": ("file.pdf", pdf_bytes)}
            data = {
                "apikey": key_to_use,
                "language": "eng",
                "isOverlayRequired": False,
                "detectOrientation": True,
                "OCREngine": 2
            }
            resp = requests.post(url, files=files, data=data, timeout=120)
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.RequestException as re:
            st.error(f"OCR request failed: {re}")
            result = {"IsErroredOnProcessing": True, "ErrorMessage": [str(re)], "ParsedResults": []}
        except json.JSONDecodeError as je:
            st.error(f"Bad response from OCR provider: {je}")
            result = {"IsErroredOnProcessing": True, "ErrorMessage": [str(je)], "ParsedResults": []}

        if result.get("IsErroredOnProcessing"):
            err_msg = result.get("ErrorMessage") or result.get("Error")
            st.error(f"OCR.space returned error: {err_msg}")
        else:
            parsed = result.get("ParsedResults") or []
            # parsed is usually a list with one entry per page (if PDF uploaded)
            for idx in range(1, total_pages + 1):
                if methods[idx] == "digital":
                    continue
                # map parsed results positionally; guard against shorter returned list
                parsed_index = idx - 1
                if parsed_index < len(parsed):
                    page_parsed = parsed[parsed_index]
                    page_text = page_parsed.get("ParsedText", "") or ""
                    if page_text.strip():
                        methods[idx] = "ocr.space"
                        extracted_text[idx - 1] = page_text
                    else:
                        methods[idx] = "ocr.space_empty"
                        extracted_text[idx - 1] = ""
                else:
                    methods[idx] = "ocr.space_missing"
                    extracted_text[idx - 1] = ""

# Build final joined output with clear per-page markers
final_text_parts = []
for i, txt in enumerate(extracted_text, start=1):
    method = methods.get(i, "unknown")
    content = txt or "[no text found]"
    final_text_parts.append(f"--- Page {i} | method: {method} ---\n{content}\n")

final_text = "\n".join(final_text_parts)

st.subheader("Extraction summary")
st.json(methods)

st.subheader("Extracted text (preview)")
st.text_area("Full extracted text", final_text.strip(), height=480)

st.download_button("💾 Download extracted text", final_text, "extracted_text.txt")

st.markdown("---")
st.markdown(
    "Notes:\n\n"
    "- This app first tries to extract digital text (fast). If any page lacks digital text, it uploads the PDF to OCR.space for OCR.\n"
    "- The default API key 'helloworld' works for small tests but is rate-limited. Get a free API key at https://ocr.space/ for production use.\n"
    "- If you prefer a local OCR (EasyOCR) or a renderer-based approach, let me know and I'll provide an alternate version."
)


