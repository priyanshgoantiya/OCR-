# app_pdf.py
import streamlit as st
from google import genai
from google.genai import types
from pdf2image import convert_from_bytes
import json
import pandas as pd
import io

st.set_page_config(page_title="PDF Text Extractor (Digital + Handwritten)", layout="wide")
st.title("📄 PDF Page-by-Page Text Extractor — Digital + Handwritten")
st.markdown("**Extracts text from each page using Gemini AI (supports printed and handwritten text)**")

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
    st.info("👆 Please upload a PDF file to extract text page by page.")
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

# OCR Prompt for text extraction
ocr_prompt = """
You are an expert OCR (Optical Character Recognition) system with advanced capabilities to read both digital printed text and handwritten text from documents.

TASK: Extract ALL text visible on this page, including:
- Printed/typed text (digital text)
- Handwritten text (cursive or printed handwriting)
- Numbers, dates, and special characters
- Text in any orientation or format

INSTRUCTIONS:
1. Read the ENTIRE page carefully
2. Extract ALL visible text exactly as it appears
3. Preserve the reading order (top to bottom, left to right)
4. Maintain paragraph breaks and line spacing where appropriate
5. If text is unclear or illegible, mark it as [ILLEGIBLE]
6. If the page is blank or has no text, return "NO_TEXT_FOUND"

Return ONLY the extracted text in plain format. Do NOT add any explanations, headers, or metadata.

BEGIN EXTRACTION:
"""

# Convert PDF to images
with st.spinner("📄 Converting PDF pages to images..."):
    try:
        images = convert_from_bytes(pdf_bytes, dpi=200)  # Higher DPI for better quality
        total_pages = len(images)
        st.success(f"✅ Converted PDF to {total_pages} page(s)")
    except Exception as e:
        st.error(f"❌ Failed to convert PDF to images: {e}")
        st.stop()

# Process each page
page_results = []

st.markdown("---")
st.subheader("📑 Extracting Text Page by Page")

progress_bar = st.progress(0)
status_text = st.empty()

for page_num, img in enumerate(images, start=1):
    status_text.text(f"Processing page {page_num}/{total_pages}...")
    progress_bar.progress(page_num / total_pages)
    
    try:
        # Convert PIL Image to bytes for Gemini
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        img_bytes = img_byte_arr.getvalue()
        
        # Create image part for Gemini
        image_part = types.Part(
            inline_data=types.Blob(
                mime_type="image/png",
                data=img_bytes
            )
        )
        
        # Call Gemini API
        response = client.models.generate_content(
            model=f"models/{model_option}",
            contents=[image_part, ocr_prompt]
        )
        
        # Extract text from response
        extracted_text = (response.text or "").strip()
        
        if not extracted_text:
            extracted_text = "NO_TEXT_FOUND"
        
        # Store result
        page_results.append({
            "Page": page_num,
            "Text": extracted_text,
            "Character_Count": len(extracted_text),
            "Status": "✅ Success" if extracted_text != "NO_TEXT_FOUND" else "⚠️ Empty"
        })
        
    except Exception as e:
        st.error(f"❌ Error processing page {page_num}: {e}")
        page_results.append({
            "Page": page_num,
            "Text": f"ERROR: {str(e)}",
            "Character_Count": 0,
            "Status": "❌ Failed"
        })

progress_bar.progress(1.0)
status_text.text("✅ Extraction complete!")

# Create DataFrame for results
df_results = pd.DataFrame(page_results)

# Display summary statistics
st.markdown("---")
st.subheader("📊 Extraction Summary")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Pages", total_pages)
with col2:
    successful_pages = len([r for r in page_results if r['Status'] == '✅ Success'])
    st.metric("Successful", successful_pages)
with col3:
    empty_pages = len([r for r in page_results if r['Status'] == '⚠️ Empty'])
    st.metric("Empty Pages", empty_pages)
with col4:
    total_chars = sum([r['Character_Count'] for r in page_results])
    st.metric("Total Characters", f"{total_chars:,}")

# Display page-by-page results
st.markdown("---")
st.subheader("📄 Page-by-Page Results")

# Show results in expandable sections
for result in page_results:
    page_num = result['Page']
    status = result['Status']
    text = result['Text']
    char_count = result['Character_Count']
    
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
        full_text += f"PAGE {result['Page']}\n"
        full_text += f"{'='*60}\n\n"
        full_text += f"{result['Text']}\n\n"
    
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
