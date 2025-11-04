# app.py
# app.py
import streamlit as st
from google import genai
from google.genai import types
import json

st.set_page_config(page_title="PDF → Gemini (multi-prompt OCR)", layout="wide")
st.title("📄 PDF → Gemini — multi-prompt extractor")

# Upload & API key
uploaded = st.file_uploader("Upload PDF", type=["pdf"])
api_key = st.text_input(
    "Paste Gemini API key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

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
    help="Best OCR models: gemini-2.0-flash-exp, gemini-2.5-flash"
)

if not uploaded:
    st.info("Upload a PDF to extract text.")
    st.stop()

if not api_key.strip():
    st.warning("Paste your Gemini API key to proceed.")
    st.stop()

pdf_bytes = uploaded.read()

# Initialize client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Define general medication extraction prompt
general_medication_extraction_prompt = """You are a licensed medical practitioner and clinical reviewer. From this medical document (digital, scanned, or handwritten), extract the Hospital Course / Clinical Summary paragraph and the two doctor names. 

Produce a single **plain text** sentence that follows this exact format, changing only the two doctor names:

Patient was admitted with above mentioned complaints and history. All relevant laboratory investigations done (Reports attached to the file). General condition and vitals of the patient closely monitored. Daily consulted by Dr. <SURGEON_OR_DAILY_DOCTOR_NAME>. Fitness for surgery given by Dr. <CONSULTANT_PHYSICIAN_NAME> (Consultant Physician). All preoperative assessment done, patient taken up for surgery.

RULES:
- Identify "Hospital Course" or "Clinical Summary" section.
- Replace only the two doctor names in the sentence above.
- Surgeon/Daily Doctor:
  * Labels: "Admitting Doctor", "Surgeon", "Daily consulted by"
  * Format: Dr. <Full Name>
- Consultant Physician:
  * Labels: "Consultant Physician", "Consultant Dr"
  * Format: Dr. <Full Name> (Consultant Physician)
- If name not found or unreadable → use "Dr. NOT_FOUND".
- Do NOT output anything else.
- Output this single line as plain text.

Additionally, return the same information in JSON format:
{
  "hospital_course_text": "<above sentence>",
  "surgeon_name": "<name>",
  "consultant_physician_name": "<name>"
}
END TASK."""

# Define all prompts dictionary - FIXED: Added opening brace
prompts = {
    "General medication extraction prompt": general_medication_extraction_prompt
}

# Process each prompt separately
combined_output = {}

with st.spinner("Processing document..."):
    for section_name, prompt_text in prompts.items():
        try:
            # Create PDF part for this request
            pdf_part = types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",
                    data=pdf_bytes
                )
            )
            
            # Call Gemini
            response = client.models.generate_content(
                model=f"models/{model_option}",
                contents=[pdf_part, prompt_text]
            )
            
            text = (response.text or "").strip() if response else ""
            
            if not text:
                st.warning(f"No response for {section_name}")
                combined_output[section_name] = "NOT_FOUND"
                continue
            
            # Display section
            st.markdown(f"### 📋 {section_name.replace('_', ' ').title()}")
            
            # Show raw text
            with st.expander(f"View raw output - {section_name}"):
                st.text_area(f"Raw ({section_name})", value=text, height=200, key=f"raw_{section_name}")
            
            # Try parse JSON
            try:
                parsed = json.loads(text)
                st.json(parsed)
                combined_output[section_name] = parsed
                
                # Download button
                st.download_button(
                    f"💾 Download {section_name}",
                    data=json.dumps(parsed, indent=2),
                    file_name=f"{section_name}.json",
                    mime="application/json",
                    key=f"download_{section_name}"
                )
            except json.JSONDecodeError:
                st.warning(f"⚠️ {section_name} output is not valid JSON")
                st.code(text)
                combined_output[section_name] = {"raw_text": text}
            
            st.markdown("---")
            
        except Exception as e:
            st.error(f"Error processing {section_name}: {e}")
            combined_output[section_name] = {"error": str(e)}

# Show combined results
st.success(f"✅ Extraction completed using {model_option}!")

st.markdown("## 📊 Combined Results")
st.json(combined_output)

# Download combined JSON
st.download_button(
    "💾 Download All Results (Combined JSON)",
    data=json.dumps(combined_output, indent=2),
    file_name="combined_extracted_data.json",
    mime="application/json",
    key="download_combined"
)

st.markdown("---")
st.markdown("**Tips:**")
st.markdown("- **Best models for OCR:** gemini-2.0-flash-exp, gemini-2.5-flash")
st.markdown("- **For handwritten text:** Use gemini-2.0-flash-exp")
st.markdown("- **If JSON fails:** Try different model or check document quality")
