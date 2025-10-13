# 📄 PDF Text Extractor with Dual OCR Engines

A powerful Streamlit web application that extracts text from PDF files using multiple advanced methods. Choose between traditional OCR processing with OCR.space or AI-powered extraction with Google Gemini based on your specific needs.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PDF](https://img.shields.io/badge/PDF-FF6B6B?style=for-the-badge)
![Google AI](https://img.shields.io/badge/Google_AI-4285F4?style=for-the-badge&logo=google&logoColor=white)

## 🌐 Live Demos

**App 1 (OCR.space Version)**: [https://4qfuvcqxovyuki4gqk8vd2.streamlit.app/](https://4qfuvcqxovyuki4gqk8vd2.streamlit.app/)

**App 2 (Gemini Version)**: [https://app2py-ldjkzaevpoxse6t4s6yh2q.streamlit.app/](https://app2py-ldjkzaevpoxse6t4s6yh2q.streamlit.app/)

## ✨ Features

### 🔍 OCR.space Method
- **Smart Dual Extraction**: Automatically detects digital text and only uses OCR for scanned pages
- **Per-Page Processing**: Uploads individual pages to OCR.space to bypass free plan limitations
- **Real-time Progress**: Live progress bar and status updates during OCR processing
- **Configurable API Settings**: Adjustable delays between requests to respect rate limits
- **Memory Efficient**: Processes files in-memory without saving to disk

### 🤖 Gemini AI Method
- **AI-Powered Extraction**: Uses Google Gemini 2.5 Flash for intelligent text extraction
- **Single API Call**: Processes entire PDF in one request
- **High Accuracy**: Leverages Google's advanced AI model for better text recognition
- **Simple Interface**: Clean, straightforward PDF-to-text conversion

### 🎯 Common Features
- **Detailed Analytics**: Extraction summary showing method used for each page
- **Export Results**: Download complete extracted text as `.txt` files
- **Error Handling**: Comprehensive error handling for API failures
- **User-Friendly**: Intuitive Streamlit interface

![Gemini Process Diagram](pdf/deepseek_mermaid_20251013_571fa1.png)
