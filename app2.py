# app.py
# app.py — minimal PDF -> Gemini text extractor
import streamlit as st
from google import genai
from google.genai import types
import io

st.set_page_config(page_title="PDF → Gemini (simple)", layout="wide")
st.title("PDF → Gemini — simple extractor")

uploaded = st.file_uploader("Upload PDF", type=["pdf"])
api_key = st.text_input("Paste Gemini API key", type="password", help="Get a key from https://aistudio.google.com/app/apikey")

if not uploaded:
    st.info("Upload a PDF to extract text.")
    st.stop()

if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

# read pdf bytes
pdf_bytes = uploaded.read()

# init client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

st.info("Sending PDF to Gemini — please wait (may take several seconds)...")
try:
    response = client.models.generate_content(
        model="gemini-1.5-flash-latest",  # try this model; change if needed
        contents=[
            types.Part.from_bytes(pdf_bytes, mime_type="application/pdf"),
            "Extract and return only the plain textual content from this PDF. Return text only — no commentary, no labels."
        ],
    )
except Exception as e:
    st.error(f"Gemini request failed: {e}")
    st.stop()

text = (response.text or "").strip() if response else ""
if not text:
    st.warning("No text returned by Gemini.")
else:
    st.success("Text extracted.")

# show as single string
st.subheader("Extracted text (single string)")
st.text_area("All text", value=text or "[no text found]", height=480)

# download
st.download_button("Download text", data=text, file_name="extracted_text.txt", mime="text/plain")

st.markdown("---")
st.markdown("Notes: If you see model / quota errors, try a different model name or check your API key/quota.")

