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
    
    prompt = """Extract the following patient administrative information from the provided hospital discharge summary document. Return the data in structured JSON format with exact field names as specified.

REQUIRED FIELDS:
1. patient_full_name
2. age
3. gender
4. medical_record_number (MRN)
5. inpatient_number (IP_No)
6. admission_date_time
7. discharge_date_time
8. admitting_doctor_name
9. admitting_doctor_registration_number
10. hospital_name
11. discharge_summary_number

OPTIONAL FIELDS (extract if present):
- ward_details
- bed_number
- consultant_specialty
- emergency_contact

INSTRUCTIONS:
- Extract values exactly as they appear in the document
- Use "NOT_FOUND" for missing required fields
- Use null for missing optional fields
- Preserve date formats as shown (DD/MM/YYYY HH:MM:SS)
- For handwritten text, provide best-effort interpretation with confidence score
- If multiple values exist for same field, return array

OUTPUT FORMAT:
{
  "patient_full_name": "string",
  "age": "string",
  "gender": "string",
  "medical_record_number": "string",
  "inpatient_number": "string",
  "admission_date_time": "string",
  "discharge_date_time": "string",
  "admitting_doctor_name": "string",
  "admitting_doctor_registration_number": "string",
  "hospital_name": "string",
  "discharge_summary_number": "string",
  "optional_fields": {
    "ward_details": "string or null",
    "bed_number": "string or null",
    "consultant_specialty": "string or null"
  },
  "extraction_metadata": {
    "confidence_score": "float (0-1)",
    "handwritten_fields": ["array of field names"],
    "extraction_timestamp": "ISO 8601"
  }
}"""
    
    response = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents=[
            pdf_part,
            prompt,
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
    st.stop()

st.markdown("---")
st.markdown("**Tips:**")
st.markdown("- Try different models if one doesn't work")
st.markdown("- Make sure your API key is valid and has available quota")
st.markdown("- For free tier, use gemini-1.5-flash or gemini-1.0-pro")
