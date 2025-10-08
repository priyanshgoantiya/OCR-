# app.py
import os
import io
import time
import streamlit as st
from pypdf import PdfReader, PdfWriter

# === optional: install google-genai and import ===
# pip package name: google-genai
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except Exception:
    genai = None
    types = None
    GEMINI_AVAILABLE = False

st.set_page_config(page_title="PDF → Gemini OCR", layout="wide")
st.title("📄 PDF → Gemini (image/pdf → text) — per-page processing")

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
gemini_key = st.text_input("Gemini API key (paste your key here)", value="", type="password",
                          help="Create/get a free key from Google AI Studio. For testing you can paste it here.")
model_choice = st.selectbox("Gemini model (choose)", options=["gemini-2.5-flash", "gemini-1.5-flash"])

if uploaded is None:
    st.info("Upload a PDF to extract text.")
    st.stop()

if not GEMINI_AVAILABLE:
    st.error("google-genai SDK not available. Add 'google-genai' to requirements.txt and redeploy.")
    st.stop()

pdf_bytes = uploaded.read()
try:
    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(pdf_reader.pages)
except Exception as e:
    st.error(f"Cannot read PDF: {e}")
    st.stop()

st.info(f"Opened PDF — {total_pages} pages found.")
# prepare containers
extracted_text = [None] * total_pages
methods = {i + 1: None for i in range(total_pages)}

# 1) Try to extract digital text
for i, page in enumerate(pdf_reader.pages, start=1):
    try:
        text = page.extract_text() or ""
    except Exception:
        text = ""
    if text.strip():
        methods[i] = "digital"
        extracted_text[i - 1] = text
    else:
        methods[i] = "needs_gemini"
        extracted_text[i - 1] = None

needs = [p for p, m in methods.items() if m == "needs_gemini"]
st.write(f"{len(needs)} page(s) need Gemini OCR")

if needs:
    if not gemini_key:
        st.warning("No Gemini API key provided — pages that require OCR will not be processed. Paste your key and re-run.")
    else:
        # configure API key in-process so SDK picks it up
        # it's OK to set environment variable here for the running process
        os.environ["GOOGLE_API_KEY"] = gemini_key
        client = genai.Client()  # uses env var if present

        per_page_delay = st.number_input("Delay between Gemini requests ( secs )", value=0.6, min_value=0.0, step=0.1)
        progress = st.progress(0)
        success_cnt = 0

        for idx, page_num in enumerate(needs, start=1):
            progress.progress((idx - 1) / len(needs))
            st.info(f"Gemini: processing page {page_num} ({idx}/{len(needs)}) ...")

            # create single page pdf bytes in memory
            writer = PdfWriter()
            try:
                writer.add_page(pdf_reader.pages[page_num - 1])
            except Exception as e:
                st.error(f"Failed to extract page {page_num}: {e}")
                methods[page_num] = "extract_failed"
                extracted_text[page_num - 1] = ""
                continue

            single_io = io.BytesIO()
            try:
                writer.write(single_io)
                single_io.seek(0)
            except Exception as e:
                st.error(f"Failed to write single-page PDF for page {page_num}: {e}")
                methods[page_num] = "write_failed"
                extracted_text[page_num - 1] = ""
                continue

            size_kb = len(single_io.getvalue()) / 1024
            st.write(f"Single-page PDF size: {size_kb:.1f} KB")

            # Build Gemini request: inline PDF bytes then a short task prompt
            try:
                contents = [
                    types.Part.from_bytes(data=single_io.getvalue(), mime_type="application/pdf"),
                    # instructions: be concise, return only plain text (no commentary)
                    "Extract and return the plain textual content from this page. Return only the text; do not add explanations, labels, or markup."
                ]

                response = client.models.generate_content(
                    model=model_choice,
                    contents=contents,
                    # you can add other request options if needed
                )

                page_text = (response.text or "").strip()
                if page_text:
                    methods[page_num] = "gemini"
                    extracted_text[page_num - 1] = page_text
                    success_cnt += 1
                    st.success(f"Page {page_num} OCR ok — {len(page_text)} chars.")
                else:
                    methods[page_num] = "gemini_empty"
                    extracted_text[page_num - 1] = ""
                    st.warning(f"Page {page_num} returned empty text.")
            except Exception as e:
                methods[page_num] = "gemini_error"
                extracted_text[page_num - 1] = ""
                st.error(f"Gemini request failed for page {page_num}: {e}")

            time.sleep(per_page_delay)

        progress.progress(1.0)
        st.success(f"Gemini OCR finished: {success_cnt}/{len(needs)} pages succeeded.")

# final: join into a single plain string (just the page texts concatenated)
plain_parts = []
for i, text in enumerate(extracted_text, start=1):
    method = methods.get(i, "unknown")
    block = text if text else ""
    plain_parts.append(block)

# join with two newlines between pages, then strip
all_text_single_string = "\n\n".join(plain_parts).strip()

st.subheader("Final concatenated plain text (single string)")
st.text_area("All text", value=all_text_single_string or "[no text found]", height=400)

st.download_button("Download plain text", all_text_single_string, file_name="extracted_text.txt", mime="text/plain")

st.subheader("Per-page extraction summary (method)")
st.json(methods)
