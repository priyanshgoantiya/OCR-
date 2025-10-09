# app.py
import streamlit as st
from google import genai
from google.genai import types

# Page configuration
st.set_page_config(
    page_title="PDF → Gemini (simple)",
    layout="wide"
)

st.title("📄 PDF → Gemini — simple extractor")

# File uploader
uploaded = st.file_uploader("Upload PDF", type=["pdf"])

# API key input
api_key = st.text_input(
    "Paste Gemini API key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

# # Model selection
# model_option = st.selectbox(
#     "Select Gemini Model",
#     [
#         "gemini-1.5-flash", 
#         "gemini-1.5-pro", 
#         "gemini-1.0-pro",
#         "gemini-1.5-flash-8b"
#     ],
#     index=0,
#     help="Try different models if one doesn't work"
# )

# Check if PDF is uploaded
if not uploaded:
    st.info("Upload a PDF to extract text.")
    st.stop()

# Check if API key is provided
if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

# Read file bytes
pdf_bytes = uploaded.read()

# Initialize Gemini client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()


try:
    # Correct usage in new google-genai SDK
    pdf_part = types.Part(
        inline_data=types.Blob(
            mime_type="application/pdf", 
            data=pdf_bytes
        )
    )
    
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[
            pdf_part,
            "Extract and return only the readable plain text from this PDF. Return text only, no explanation.",
        ],
    )
    
    text = (response.text or "").strip() if response else ""
    
    if not text:
        st.warning("No text returned by Gemini.")
    else:
        st.success("✅ Text extracted successfully!")
        
        # Display and download
        st.subheader("🧾 Extracted Text")
        st.text_area("All text", value=text, height=480)
        
        st.download_button(
            "💾 Download text", 
            data=text, 
            file_name="extracted_text.txt", 
            mime="text/plain"
        )

except Exception as e:
    st.error(f"Gemini request failed: {e}")
    st.error("Try selecting a different model from the dropdown above.")
    st.stop()

st.markdown("---")
st.markdown("**Tips:**")
st.markdown("- Try different models if one doesn't work")
st.markdown("- Make sure your API key is valid and has available quota")
st.markdown("- For free tier, use gemini-1.5-flash or gemini-1.0-pro")
