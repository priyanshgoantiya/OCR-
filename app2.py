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
    
    prompt = """Extract the following patient administrative information from the hospital discharge summary. Return data in JSON format.

REQUIRED FIELDS:
1. patient_full_name
2. age_gender (format: "age / gender")
3. mr_no_ip_no (format: "MR No. / IP No.")
4. admission_date_time
5. discharge_date_time
6. admitting_doctor_name
7. admitting_doctor_registration_number
8. discharge_summary_number

INSTRUCTIONS:
- Extract values exactly as they appear
- Use "NOT_FOUND" for missing fields
- Preserve date formats as shown
- Combine age and gender with " / " separator
- Combine MR No. and IP No. with " / " separator

OUTPUT FORMAT:
{
  "patient_full_name": "string",
  "age_gender": "string",
  "mr_no_ip_no": "string",
  "admission_date_time": "string",
  "discharge_date_time": "string",
  "admitting_doctor_name": "string",
  "admitting_doctor_registration_number": "string",
  "discharge_summary_number": "string"
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
