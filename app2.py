# app.py
import streamlit as st
from google import genai
from google.genai import types
import json
import base64

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
pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")  # Convert to base64 for Gemini SDK

# Initialize Gemini client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Prepare PDF part and prompt
pdf_part = types.Part(
    blob=types.Blob(
        mime_type="application/pdf",
        data=pdf_b64
    )
)

prompt = """Extract patient administrative information from the hospital discharge summary. Apply OCR best practices and return data in JSON format.

OCR PROCESSING INSTRUCTIONS:
- Scan entire document systematically (top to bottom, left to right)
- Check header section first (typically top 20% of page)
- Look for tables, boxes, or bordered sections containing patient info
- For handwritten text: analyze character shapes carefully, consider context
- Cross-verify similar fields (e.g., if MR No. appears twice, use most complete)
- Identify labels like "Name:", "Patient:", "MRN:", "IP No:", "Admission Date:"
- Handle multi-line fields by concatenating text logically
- Ignore watermarks, logos, and irrelevant decorative elements

REQUIRED FIELDS:
1. patient_full_name
2. age_gender
3. mr_no_ip_no
4. admission_date_time
5. discharge_date_time
6. admitting_doctor_name
7. admitting_doctor_registration_number
8. discharge_summary_number

EXTRACTION RULES:
- Extract values EXACTLY as they appear (preserve spelling, capitalization, punctuation)
- Use "NOT_FOUND" for genuinely missing fields
- Preserve date formats
- Combine age / gender and MR/IP numbers with " / "
- Remove extra spaces but keep intentional formatting
- For unclear handwriting: provide best interpretation, don't skip

OUTPUT FORMAT (strict JSON):
{
  "patient_full_name": "string",
  "age_gender": "string",
  "mr_no_ip_no": "string",
  "admission_date_time": "string",
  "discharge_date_time": "string",
  "admitting_doctor_name": "string",
  "admitting_doctor_registration_number": "string",
  "discharge_summary_number": "string"
}

CRITICAL: Return ONLY valid JSON."""

prompt_part = types.Part(text=prompt)

# Call Gemini API
try:
    response = client.models.generate_content(
        model=model_option,
        contents=[types.Content(parts=[pdf_part, prompt_part])]
    )

    text = (response.content[0].text or "").strip() if response and response.content else ""

    if not text:
        st.warning("No text returned by Gemini.")
    else:
        st.success(f"✅ Text extracted successfully using {model_option}!")

        # Display and download raw text
        st.subheader("🧾 Extracted Text")
        st.text_area("All text", value=text, height=480)
        st.download_button(
            "💾 Download text",
            data=text,
            file_name="extracted_text.txt",
            mime="text/plain"
        )

        # Try parsing JSON
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
        except json.JSONDecodeError:
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
