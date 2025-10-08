# app.py
# app.py
import streamlit as st
from pypdf import PdfReader, PdfWriter
import io
import requests
import time
import json

st.set_page_config(page_title="PDF OCR (per-page upload)", layout="wide")
st.title("📄 PDF Text Extractor — digital text + per-page OCR.space uploads")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
api_key = st.text_input(
    "OCR.space API key (leave blank to use 'helloworld' test key)",
    value="helloworld",
    help="Get a free key from https://ocr.space/ if you plan to OCR many files or large PDFs."
)

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
extracted_text = [None] * total_pages
methods = {i+1: None for i in range(total_pages)}

# 1) Try to read digital text from each page
for i, page in enumerate(pdf_reader.pages, start=1):
    try:
        page_text = page.extract_text() or ""
    except Exception:
        page_text = ""
    if page_text.strip():
        methods[i] = "digital"
        extracted_text[i-1] = page_text
    else:
        methods[i] = "needs_ocr"
        extracted_text[i-1] = None

needs_ocr_pages = [i for i, m in methods.items() if m == "needs_ocr"]

if not needs_ocr_pages:
    st.success("All pages contained digital (extractable) text — no OCR required.")
else:
    st.warning(f"{len(needs_ocr_pages)} page(s) need OCR. We'll upload them one-by-one to OCR.space.")
    key_to_use = (api_key.strip() or "helloworld")

    # OCR.space endpoint
    OCR_URL = "https://api.ocr.space/parse/image"

    # Optional small delay between requests to be gentle on rate-limits
    per_page_delay = st.number_input("Delay between page requests (seconds)", min_value=0.0, max_value=10.0, value=0.8, step=0.2)

    progress = st.progress(0)
    success_count = 0
    for idx, page_num in enumerate(needs_ocr_pages, start=1):
        progress.progress((idx-1) / len(needs_ocr_pages))
        st.info(f"OCR: processing page {page_num} ({idx}/{len(needs_ocr_pages)}) ...")

        # Create a single-page PDF in-memory
        writer = PdfWriter()
        try:
            writer.add_page(pdf_reader.pages[page_num - 1])
        except Exception as e:
            st.error(f"Failed to extract page {page_num} for OCR: {e}")
            methods[page_num] = "extract_failed"
            extracted_text[page_num - 1] = ""
            continue

        single_page_io = io.BytesIO()
        try:
            writer.write(single_page_io)
            single_page_io.seek(0)
        except Exception as e:
            st.error(f"Failed to write single-page PDF for page {page_num}: {e}")
            methods[page_num] = "write_failed"
            extracted_text[page_num - 1] = ""
            continue

        single_size = len(single_page_io.getvalue())
        st.write(f"Single-page PDF size: {single_size/1024:.1f} KB")
        # If the single page still exceeds 1MB, warn and continue (may still be rejected)
        if single_size > 1024 * 1024:
            st.warning(f"Page {page_num} single-page PDF is {single_size/1024:.1f} KB — may exceed OCR.space free limit.")

        # Send to OCR.space
        files = {"file": (f"page_{page_num}.pdf", single_page_io.getvalue())}
        data = {
            "apikey": key_to_use,
            "language": "eng",
            "isOverlayRequired": False,
            "detectOrientation": True,
            "OCREngine": 2
        }

        try:
            resp = requests.post(OCR_URL, files=files, data=data, timeout=120)
            resp.raise_for_status()
            resp_json = resp.json()
        except requests.exceptions.RequestException as re:
            st.error(f"Network or request error on page {page_num}: {re}")
            methods[page_num] = "network_error"
            extracted_text[page_num - 1] = ""
            # wait a little before next try
            time.sleep(per_page_delay)
            continue
        except json.JSONDecodeError as je:
            st.error(f"Invalid JSON response for page {page_num}: {je}")
            methods[page_num] = "bad_json"
            extracted_text[page_num - 1] = ""
            time.sleep(per_page_delay)
            continue

        # Check API response for errors
        if resp_json.get("IsErroredOnProcessing"):
            err = resp_json.get("ErrorMessage") or resp_json.get("Error")
            st.error(f"OCR.space returned error for page {page_num}: {err}")
            methods[page_num] = "ocr_error"
            extracted_text[page_num - 1] = ""
        else:
            parsed_results = resp_json.get("ParsedResults") or []
            if parsed_results:
                # Usually one object per page (since we uploaded single page)
                parsed_text = parsed_results[0].get("ParsedText", "") or ""
                if parsed_text.strip():
                    methods[page_num] = "ocr.space"
                    extracted_text[page_num - 1] = parsed_text
                    success_count += 1
                    st.success(f"OCR success for page {page_num} ({len(parsed_text)} chars).")
                else:
                    methods[page_num] = "ocr_empty"
                    extracted_text[page_num - 1] = ""
                    st.warning(f"OCR returned empty text for page {page_num}.")
            else:
                methods[page_num] = "no_parsed_results"
                extracted_text[page_num - 1] = ""
                st.error(f"No parsed results for page {page_num} from OCR.space.")

        # small delay to avoid hitting rate limits
        time.sleep(per_page_delay)

    progress.progress(1.0)
    st.success(f"Finished OCR pages. Successful OCR pages: {success_count}/{len(needs_ocr_pages)}")

# Build final output text
final_parts = []
for i, content in enumerate(extracted_text, start=1):
    method = methods.get(i, "unknown")
    text_block = content if content else "[no text found]"
    final_parts.append(f"--- Page {i} | method: {method} ---\n{text_block}\n")

final_text = "\n".join(final_parts)

st.subheader("Extraction summary")
st.json(methods)

st.subheader("Extracted text (preview)")
st.text_area("Full extracted text", final_text.strip(), height=480)

st.download_button("💾 Download extracted text", final_text, "extracted_text.txt")

st.markdown("---")
st.markdown(
    "- This app first tries to extract digital text (fast). Pages without digital text are uploaded one-by-one to OCR.space.\n"
    "- Single-page uploads are used to work around OCR.space free-plan limit (1 MB). If a single page still exceeds the limit, OCR.space may still reject it.\n"
    "- If many pages are large or OCR.space keeps rejecting pages, consider: (A) using a paid OCR.space plan with larger upload limits, (B) using a different OCR API (Google Vision / Azure), or (C) rendering & downscaling images locally before OCR (requires installing rendering libraries)."
)



