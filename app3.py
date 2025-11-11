import streamlit as st
from google import genai
from google.genai import types
import json
import pandas as pd
import io

st.set_page_config(page_title="PDF Text Extractor (Digital + Handwritten)", layout="wide")
st.title("📄 PDF Text Extractor — Digital + Handwritten")
st.markdown("**Extracts text from PDF using Gemini AI (supports printed and handwritten text)**")
st.info("💡 This version processes the entire PDF at once without requiring poppler/pdf2image")

# Upload and API key inputs
uploaded = st.file_uploader("Upload PDF File", type=["pdf"])
api_key = st.text_input(
    "Paste Gemini API key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

model_option = st.selectbox(
    "Select Gemini Model",
    [
        "gemini-2.0-flash-exp",  # Best for handwritten text
        "gemini-2.5-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash"
    ],
    index=0,
    help="gemini-2.0-flash-exp is recommended for handwritten text"
)

if not uploaded:
    st.info("👆 Please upload a PDF file to extract text.")
    st.stop()

if not api_key.strip():
    st.warning("⚠️ Please enter your Gemini API key to proceed.")
    st.stop()

# Read PDF bytes
pdf_bytes = uploaded.read()

# Configure Gemini client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"❌ Failed to initialize Gemini client: {e}")
    st.stop()

st.success(f"✅ Using model: **{model_option}**")

# OCR Prompt for text extraction with page-by-page structure
ocr_prompt = """
You are an expert OCR (Optical Character Recognition) system with advanced capabilities to read both digital printed text and handwritten text from PDF documents.

TASK: Extract ALL text from this PDF document, organizing it PAGE BY PAGE.

Extract text including:
- Printed/typed text (digital text)
- Handwritten text (cursive or printed handwriting)
- Numbers, dates, and special characters
- Text in any orientation or format

INSTRUCTIONS:
1. Process EACH page separately
2. Extract ALL visible text exactly as it appears
3. Preserve the reading order (top to bottom, left to right)
4. Maintain paragraph breaks within each page
5. If text is unclear or illegible, mark it as [ILLEGIBLE]
6. If a page is blank or has no text, mark it as "NO_TEXT_FOUND"

CRITICAL: Return results as a JSON array with this EXACT format:
[
  {
    "page": 1,
    "text": "extracted text from page 1...",
    "character_count": 1234
  },
  {
    "page": 2,
    "text": "extracted text from page 2...",
    "character_count": 5678
  }
]

Return ONLY the JSON array. Do NOT add explanations before or after the JSON.

BEGIN EXTRACTION:
"""

# Process PDF
st.markdown("---")
st.subheader("📑 Extracting Text from PDF")

with st.spinner("🤖 Processing PDF with Gemini AI..."):
    try:
        # Create PDF part for Gemini
        pdf_part = types.Part(
            inline_data=types.Blob(
                mime_type="application/pdf",
                data=pdf_bytes
            )
        )
        
        # Call Gemini API
        response = client.models.generate_content(
            model=f"models/{model_option}",
            contents=[pdf_part, ocr_prompt]
        )
        
        # Extract text from response
        response_text = (response.text or "").strip()
        
        if not response_text:
            st.error("❌ No response from Gemini")
            st.stop()
        
        # Clean JSON from markdown code blocks
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Show raw response in expander
        with st.expander("🔍 View Raw Gemini Response"):
            st.code(json_text, language="json")
        
        # Parse JSON
        try:
            page_results = json.loads(json_text)
            
            # Validate structure
            if not isinstance(page_results, list):
                st.error("❌ Response is not a list. Attempting to fix...")
                page_results = [page_results] if isinstance(page_results, dict) else []
            
            # Add status field to each page
            for page in page_results:
                text = page.get('text', '')
                if text == "NO_TEXT_FOUND" or not text.strip():
                    page['status'] = '⚠️ Empty'
                else:
                    page['status'] = '✅ Success'
                    
                # Ensure character_count exists
                if 'character_count' not in page:
                    page['character_count'] = len(text)
            
            st.success(f"✅ Successfully extracted text from {len(page_results)} page(s)")
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Failed to parse JSON: {e}")
            st.code(json_text[:1000])
            st.stop()
            
    except Exception as e:
        st.error(f"❌ Error processing PDF: {e}")
        st.stop()

# Create DataFrame for results
df_results = pd.DataFrame(page_results)

# Rename columns for display
column_mapping = {
    'page': 'Page',
    'text': 'Text',
    'character_count': 'Character_Count',
    'status': 'Status'
}
df_results = df_results.rename(columns=column_mapping)

# Display summary statistics
st.markdown("---")
st.subheader("📊 Extraction Summary")

total_pages = len(page_results)
successful_pages = len([p for p in page_results if p['status'] == '✅ Success'])
empty_pages = len([p for p in page_results if p['status'] == '⚠️ Empty'])
total_chars = sum([p.get('character_count', 0) for p in page_results])

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Pages", total_pages)
with col2:
    st.metric("Successful", successful_pages)
with col3:
    st.metric("Empty Pages", empty_pages)
with col4:
    st.metric("Total Characters", f"{total_chars:,}")

# Display page-by-page results
st.markdown("---")
st.subheader("📄 Page-by-Page Results")

# Show results in expandable sections
for result in page_results:
    page_num = result['page']
    status = result['status']
    text = result['text']
    char_count = result.get('character_count', 0)
    
    with st.expander(f"**Page {page_num}** — {status} ({char_count} characters)"):
        st.text_area(
            f"Text from Page {page_num}",
            value=text,
            height=200,
            key=f"page_{page_num}_text"
        )

# Display full results table
st.markdown("---")
st.subheader("📋 Full Results Table")
st.dataframe(df_results[['Page', 'Character_Count', 'Status']], use_container_width=True)

# Download options
st.markdown("---")
st.subheader("📥 Download Results")

col1, col2, col3 = st.columns(3)

with col1:
    # Download as plain text
    full_text = ""
    for result in page_results:
        full_text += f"{'='*60}\n"
        full_text += f"PAGE {result['page']}\n"
        full_text += f"{'='*60}\n\n"
        full_text += f"{result['text']}\n\n"
    
    st.download_button(
        label="📄 Download as Text File",
        data=full_text,
        file_name="extracted_text_all_pages.txt",
        mime="text/plain",
        use_container_width=True
    )

with col2:
    # Download as JSON
    json_data = json.dumps(page_results, indent=2, ensure_ascii=False)
    st.download_button(
        label="📋 Download as JSON",
        data=json_data,
        file_name="extracted_text_pages.json",
        mime="application/json",
        use_container_width=True
    )

with col3:
    # Download as Excel
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df_results.to_excel(writer, index=False, sheet_name='Extracted Text')
    excel_buffer.seek(0)
    
    st.download_button(
        label="📊 Download as Excel",
        data=excel_buffer,
        file_name="extracted_text_pages.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

