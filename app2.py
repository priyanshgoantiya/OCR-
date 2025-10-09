# app.py
# app.py — Safe Gemini PDF extractor with model discovery + per-page fallback
import io
import time
import streamlit as st

from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter

st.set_page_config(page_title="Gemini PDF Extractor (safe)", layout="wide")
st.title("📄 Gemini PDF Extractor — safe model selection & fallback")

uploaded = st.file_uploader("Upload PDF", type=["pdf"])
api_key = st.text_input("Paste Gemini API key", type="password", help="Get a key: https://aistudio.google.com/app/apikey")

if not uploaded:
    st.info("Upload a PDF to extract text.")
    st.stop()
if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

# Initialize client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

st.info("Listing models available to your key...")
models_list = []
try:
    # list returns an iterator of model objects — convert to list
    for m in client.models.list(config={"page_size": 200}):
        # supported_actions may be missing; default to empty list
        supported = getattr(m, "supported_actions", []) or []
        # include models that support generateContent (SDK naming)
        if "generateContent" in supported or "generate_content" in supported:
            models_list.append(m.name)
except Exception as e:
    st.error(f"Could not list models: {e}")
    st.stop()

if not models_list:
    st.error("No models supporting generateContent were found for this API key. "
             "Possible reasons: (1) key has limited access, (2) API region/permissions. "
             "Check your Google AI Studio key or try a different key.")
    # show all model names as extra info (non-blocking)
    try:
        all_models = [m.name for m in client.models.list(config={"page_size": 200})]
        st.write("Models visible to your key (partial list):", all_models[:30])
    except Exception:
        pass
    st.stop()

model_choice = st.selectbox("Choose a model (supports generateContent):", models_list, index=0)
st.write(f"Selected model: **{model_choice}**")

# Read PDF bytes and report pages
pdf_bytes = uploaded.read()
try:
    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(pdf_reader.pages)
    st.success(f"PDF loaded — {total_pages} pages found.")
except Exception as e:
    st.error(f"Failed to read PDF: {e}")
    st.stop()

# Helper: perform a generate_content call on bytes, returns text or raises
def call_gemini_with_pdf(model_name: str, pdf_bytes_blob: bytes):
    pdf_part = types.Part(inline_data=types.Blob(mime_type="application/pdf", data=pdf_bytes_blob))
    resp = client.models.generate_content(
        model=model_name,
        contents=[
            pdf_part,
            "Extract and return ONLY the readable plain textual content from this PDF. Return text only, no commentary."
        ],
        # you can set max_output_tokens or other params if desired
    )
    # resp.text is the aggregated text
    return (resp.text or "").strip()

# Try single-call for entire PDF
st.info("Attempting single-call extraction for whole PDF (faster).")
with st.spinner("Sending PDF to Gemini (single request)..."):
    try:
        whole_text = call_gemini_with_pdf(model_choice, pdf_bytes)
    except Exception as e_single:
        st.warning(f"Single-call failed: {e_single}")
        whole_text = None

# If single-call failed or returned empty, do per-page fallback
if not whole_text:
    st.info("Falling back to per-page requests (safer for large PDF / model limits).")
    per_page_texts = [""] * total_pages
    progress = st.progress(0)
    success_count = 0
    for i in range(total_pages):
        progress.progress(i / total_pages)
        st.write(f"Processing page {i+1}/{total_pages} ...")
        # make single-page pdf bytes
        writer = PdfWriter()
        writer.add_page(pdf_reader.pages[i])
        single_io = io.BytesIO()
        try:
            writer.write(single_io)
            single_io.seek(0)
            page_bytes = single_io.getvalue()
        except Exception as e:
            st.error(f"Failed to create single-page PDF for page {i+1}: {e}")
            per_page_texts[i] = ""
            continue

        # call gemini for this page
        try:
            page_text = call_gemini_with_pdf(model_choice, page_bytes)
            per_page_texts[i] = page_text or ""
            if page_text:
                success_count += 1
                st.write(f"Page {i+1} extracted ({len(page_text)} chars).")
            else:
                st.warning(f"Page {i+1} returned empty text.")
        except Exception as e_page:
            st.warning(f"Gemini failed for page {i+1}: {e_page}")
            per_page_texts[i] = ""
        time.sleep(0.6)  # polite delay to avoid rate limits

    progress.progress(1.0)
    st.success(f"Per-page extraction done — {success_count}/{total_pages} pages returned text.")
    # join pages
    final_text = "\n\n".join([t for t in per_page_texts if t])
else:
    final_text = whole_text

if not final_text:
    st.error("Gemini did not return any extracted text. Options:\n"
             "- Check API key permissions / quota in Google AI Studio.\n"
             "- Try another model from the dropdown.\n"
             "- Use a different OCR provider (OCR.space / Google Vision) as fallback.")
    st.stop()

# Show result and download
st.subheader("Extracted text (single string)")
st.text_area("All extracted text", value=final_text, height=480)
st.download_button("💾 Download text", data=final_text, file_name="extracted_text.txt", mime="text/plain")

st.subheader("Debug")
st.write({"model_used": model_choice, "pages": total_pages})
