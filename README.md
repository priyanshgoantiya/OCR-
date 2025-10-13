# OCR
deploylink app1--https://4qfuvcqxovyuki4gqk8vd2.streamlit.app/
deploylink app2--https://app2py-ldjkzaevpoxse6t4s6yh2q.streamlit.app/
# PDF Text Extractor with OCR

A Streamlit web application that extracts text from PDF files using both digital text extraction and OCR.space API for scanned pages. Automatically detects pages with digital text and only uses OCR for scanned pages that need it.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PDF](https://img.shields.io/badge/PDF-FF6B6B?style=for-the-badge)

## 🚀 Features

- **Smart Dual Extraction**: Automatically detects digital text and only uses OCR for scanned pages
- **Per-Page Processing**: Uploads individual pages to OCR.space to bypass free plan limitations
- **Real-time Progress**: Live progress bar and status updates during OCR processing
- **Configurable API Settings**: Adjustable delays between requests to respect rate limits
- **Detailed Analytics**: Extraction summary showing method used for each page
- **Export Results**: Download complete extracted text as a `.txt` file
- **Memory Efficient**: Processes files in-memory without saving to disk

## 📋 How It Works

1. **Digital Text Detection**: Uses `pypdf` to extract directly accessible text from each PDF page
2. **OCR Fallback**: For pages without digital text, creates single-page PDFs and sends to OCR.space API
3. **Smart Optimization**: Only processes pages that actually need OCR, saving time and API calls
4. **Results Compilation**: Combines all extracted text with detailed page-by-page method tracking

## 🛠️ Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Quick Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/priyanshgoantiya/OCR-.git
   cd OCR-
