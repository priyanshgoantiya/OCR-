import streamlit as st
from PIL import Image
import pytesseract
from pdf2image import convert_from_bytes
import io

# Set page configuration
st.set_page_config(
    page_title="PDF OCR App",
    page_icon="📄",
    layout="wide"
)

# Title and description
st.title("📄 PDF OCR App")
st.markdown("Upload a PDF file to extract text using Optical Character Recognition (OCR)")

# File upload section
uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
    help="Upload a PDF file containing text to extract"
)

# Sidebar with information
with st.sidebar:
    st.header("About")
    st.markdown("""
    This app uses:
    - **pytesseract** for OCR
    - **pdf2image** for PDF conversion
    - **Streamlit** for the web interface
    
    Upload a PDF file to extract text content.
    """)
    
    st.header("Tips")
    st.markdown("""
    - Better results with clear, high-quality images
    - Text should be clearly visible
    - Works best with computer-generated text
    - Processing time depends on PDF size
    """)

# Function to perform OCR
def perform_ocr(pdf_file):
    """Convert PDF to images and perform OCR"""
    try:
        with st.spinner("Converting PDF to images..."):
            images = convert_from_bytes(pdf_file.read(), dpi=200)
        
        extracted_text = ""
        progress_bar = st.progress(0)
        
        for i, image in enumerate(images):
            st.info(f"Processing page {i+1} of {len(images)}...")
            page_text = pytesseract.image_to_string(image)
            extracted_text += f"\n--- Page {i+1} ---\n{page_text}\n"
            progress_bar.progress((i + 1) / len(images))
        
        return extracted_text, images
    
    except Exception as e:
        st.error(f"Error during OCR processing: {str(e)}")
        return None, None

# Main processing logic
if uploaded_file is not None:
    file_details = {
        "Filename": uploaded_file.name,
        "File size": f"{uploaded_file.size / 1024:.2f} KB"
    }
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("File Details")
        st.json(file_details)
    
    with col2:
        st.subheader("Actions")
        process_clicked = st.button("🚀 Start OCR Processing", type="primary")
        st.caption("Click the button above to start text extraction")
    
    if process_clicked:
        extracted_text, images = perform_ocr(uploaded_file)
        
        if extracted_text:
            st.success("✅ OCR processing completed successfully!")
            
            tab1, tab2 = st.tabs(["📝 Extracted Text", "🖼 Page Images"])
            
            with tab1:
                st.subheader("Extracted Text")
                st.text_area("Full OCR Text", extracted_text, height=500)
                st.download_button(
                    "💾 Download Text",
                    data=extracted_text,
                    file_name="extracted_text.txt",
                    mime="text/plain"
                )
            
            with tab2:
                st.subheader("PDF Pages as Images")
                for i, img in enumerate(images):
                    st.image(img, caption=f"Page {i+1}", use_column_width=True)
        else:
            st.warning("No text extracted. Ensure the PDF contains visible text or enable OCR on scanned documents.")

