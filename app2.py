# app.py
import streamlit as st
from google import genai
from google.genai import types
import json

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

# Model selection
model_option = st.selectbox(
    "Select Gemini Model",
    [
        "gemini-2.0-flash-exp",
        "gemini-2.5-flash", 
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-exp-1206"
    ],
    index=0,
    help="Best OCR models: gemini-2.0-flash-exp, gemini-2.5-flash, gemini-1.5-flash"
)

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
    
    prompt = """Extract diagnosis information from the hospital discharge summary document. Return data in structured JSON format.

REQUIRED FIELDS:
1. provisional_diagnosis - Initial diagnosis made at admission (may be labeled as "Provisional Diagnosis", "Admitting Diagnosis", "Working Diagnosis", or "Impression on Admission")
2. final_diagnosis - Confirmed diagnosis at discharge (may be labeled as "Final Diagnosis", "Discharge Diagnosis", "Principal Diagnosis", or simply "Diagnosis")

INSTRUCTIONS:
- Extract diagnoses exactly as documented
- If diagnosis has multiple conditions, separate with " | " delimiter
- Distinguish between primary and secondary diagnoses if specified
- Include ICD codes if present in format: "condition (ICD-code)"
- Use "NOT_FOUND" if field not present in document
- Preserve medical terminology and abbreviations
- For handwritten sections, provide best interpretation

OUTPUT FORMAT:
{
  "provisional_diagnosis": "string or NOT_FOUND",
  "final_diagnosis": "string or NOT_FOUND"
}"""
    
    response = client.models.generate_content(
        model=f"models/{model_option}",
        contents=[
            pdf_part,
            prompt,
        ],
    )
    
    text = (response.text or "").strip() if response else ""
    
    if not text:
        st.warning("No text returned by Gemini.")
    else:
        st.success(f"✅ Text extracted successfully using {model_option}!")
        
        # Display and download
        st.subheader("🧾 Extracted Text")
        st.text_area("All text", value=text, height=480)
        
        st.download_button(
            "💾 Download text", 
            data=text, 
            file_name="extracted_text.txt", 
            mime="text/plain"
        )
        
        # Try to parse as JSON
        try:
            parsed_json = json.loads(text)
            st.subheader("📋 Structured Data")
            st.json(parsed_json)
            
            st.download_button(
                "💾 Download JSON", 
                data=json.dumps(parsed_json, indent=2), 
                file_name="extracted_data.json", 
                mime="application/json"
            )
        except:
            st.info("Output is not valid JSON. Displaying as plain text.")
            
except Exception as e:
    st.error(f"Gemini request failed: {e}")
    st.error(f"Try selecting a different model from the dropdown above.")
    st.stop()

st.markdown("---")
st.markdown("**Tips:**")
st.markdown("- **Best for OCR:** gemini-2.0-flash-exp, gemini-2.5-flash")
st.markdown("- **Fastest:** gemini-1.5-flash-8b")
st.markdown("- **Most accurate:** gemini-1.5-pro")
st.markdown("- Make sure your API key is valid and has available quota")
