# Import Streamlit for creating the web interface
import streamlit as st
# Import Google Generative AI library for accessing Gemini models
from google import genai
# Import types for structured API requests (file uploads, content generation)
from google.genai import types
# Import JSON library for parsing and formatting structured data
import json
# Import pandas for handling Google Sheets data
import pandas as pd
# Import gspread for Google Sheets API access
import gspread
# Import Google Auth for authentication
from google.oauth2.service_account import Credentials

# Configure Streamlit page settings with custom title and wide layout for better visibility
st.set_page_config(page_title="Medical Records Extractor", layout="wide")
# Display main title of the application
st.title("📄 Medical Records → Medication Extractor")

# Add tabs for different input methods
input_method = st.radio(
    "Select Input Method:",
    ["Upload PDF", "Google Sheets URL"],
    horizontal=True
)

# Initialize variables
uploaded = None
sheet_url = None
file_data = None

# Handle different input methods
if input_method == "Upload PDF":
    # Create file uploader widget that accepts only PDF files
    uploaded = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded:
        # Read the uploaded PDF file as bytes for API transmission
        file_data = uploaded.read()
        file_type = "pdf"
        
elif input_method == "Google Sheets URL":
    # Create text input for Google Sheets URL
    sheet_url = st.text_input(
        "Paste Google Sheets URL",
        placeholder="https://docs.google.com/spreadsheets/d/..."
    )
    
    # Option to upload service account credentials
    st.info("📌 For private sheets, upload service account JSON credentials (optional)")
    creds_file = st.file_uploader("Upload Service Account Credentials (JSON)", type=["json"])
    
    if sheet_url:
        try:
            # Extract spreadsheet ID from URL
            if "/d/" in sheet_url:
                sheet_id = sheet_url.split("/d/")[1].split("/")[0]
            else:
                st.error("Invalid Google Sheets URL format")
                st.stop()
            
            # Try to read the sheet (public access or with credentials)
            if creds_file:
                # Use service account credentials
                creds_data = json.load(creds_file)
                scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
                credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
                gc = gspread.authorize(credentials)
                spreadsheet = gc.open_by_key(sheet_id)
            else:
                # Try public access
                sheet_url_export = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
                
            # Read the third sheet (Treatment Given)
            if creds_file:
                # Get all worksheets
                worksheets = spreadsheet.worksheets()
                if len(worksheets) >= 3:
                    # Get the 3rd sheet (index 2)
                    sheet = worksheets[2]
                    data = sheet.get_all_values()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    st.success(f"✅ Loaded sheet: {sheet.title}")
                else:
                    st.error("Sheet does not have 3 tabs. Please check your Google Sheet.")
                    st.stop()
            else:
                # Public access - read as Excel
                df = pd.read_excel(sheet_url_export, sheet_name=2)  # 3rd sheet (0-indexed)
                st.success("✅ Loaded Treatment Given sheet")
            
            # Convert dataframe to text format for LLM
            file_data = df.to_string()
            file_type = "sheet"
            
            # Display preview
            with st.expander("📊 Preview of Treatment Given Sheet"):
                st.dataframe(df.head(20))
                
        except Exception as e:
            st.error(f"Failed to load Google Sheet: {e}")
            st.info("💡 Make sure the sheet is publicly accessible or provide service account credentials")
            st.stop()

# Create secure password input field for Gemini API key (hides characters as user types)
api_key = st.text_input(
    "Paste Gemini API key",
    type="password",  # Mask input for security
    help="Get a free key from https://aistudio.google.com/app/apikey"  # Helpful tooltip
)

# Create dropdown menu for selecting which Gemini model to use
model_option = st.selectbox(
    "Select Gemini Model",
    [
        "gemini-2.0-flash-exp",      # Latest experimental flash model
        "gemini-2.5-flash",           # Stable flash model v2.5
        "gemini-1.5-flash",           # Flash model v1.5
        "gemini-1.5-flash-8b",        # Lightweight 8-billion parameter model
        "gemini-1.5-pro",             # Pro model with better accuracy
        "gemini-exp-1206"             # Experimental model dated Dec 6
    ],
    index=0,  # Default to first option (gemini-2.0-flash-exp)
    help="Best OCR models: gemini-2.0-flash-exp, gemini-2.5-flash"  # Guide users to best models
)

# Check if user has provided input
if not file_data:
    st.info("📤 Upload a PDF or provide Google Sheets URL to extract medications.")
    st.stop()  # Halt execution until input is provided

# Check if user has provided API key; if not, show warning and stop execution
if not api_key.strip():
    st.warning("🔑 Paste your Gemini API key to proceed.")
    st.stop()  # Halt execution until API key is provided

# Initialize Gemini client with user-provided API key, wrapped in try-except for error handling
try:
    client = genai.Client(api_key=api_key)  # Create authenticated client
except Exception as e:
    # Display error message if client initialization fails (invalid key, network issues, etc.)
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()  # Halt execution on initialization failure

# Define medication extraction prompt
medication_extraction_prompt = """
TASK:
You are a licensed medical practitioner and clinical pharmacist reviewing hospital treatment records. Extract ONLY pharmaceutical medications from the "Treatment Given" sheet, excluding all medical consumables, supplies, and non-medication items.

# CONTEXT & MINDSET:
- Approach this as a trained pharmacist conducting medication reconciliation
- Apply clinical knowledge to distinguish medications from medical supplies
- Focus on therapeutic agents with pharmacological action
- Maintain precision and accuracy in medication identification

# EXTRACTION RULES:

## INCLUDE (Medications - Pharmacological Agents):
✓ Tablets, Capsules, Pills (TAB, CAP)
✓ Injections (INJ) - antibiotics, analgesics, vitamins, etc.
✓ Syrups, Suspensions, Solutions (SYR)
✓ Respules, Nebulizers with active drugs (NEB)
✓ Inhalers with pharmaceutical compounds (INH)
✓ Suppositories with active ingredients
✓ Medicated creams, ointments, gels (with drug compounds)
✓ Medicated mouthwash/gargle (with active pharmaceutical ingredients)
✓ IV fluids with medications (e.g., Paracetamol IV, Pantoprazole IV)

## EXCLUDE (Consumables & Medical Supplies):
✗ Needles, syringes, cannulas
✗ IV administration sets, infusion sets
✗ Bandages, gauze, dressings
✗ Surgical instruments (ice scrapper, etc.)
✗ Plain IV fluids without medication (NS, DNS, D5%, D10%, Ringer's Lactate, Water for Injection)
✗ Soap, hand wash, sanitizers
✗ Toothbrushes, toothpaste
✗ Cotton, swabs
✗ Gloves, masks
✗ Catheters, tubes
✗ Non-medicated dusting powders
✗ Plain saline (aqua), plain water for injection
✗ Medical devices and equipment

## AMBIGUOUS ITEMS - CLINICAL JUDGMENT:
- BETADINE GARGLE → INCLUDE (contains povidone-iodine)
- NS 100ML (AQUA) → EXCLUDE (plain saline)
- DUSTING POWDER-MYCODERM-C → INCLUDE (contains clotrimazole)
- ICE SCRAPPER → EXCLUDE (medical device)

# OUTPUT FORMAT:

Return JSON format:

{
  "medications_extracted": [
    "MEDICATION NAME 1",
    "MEDICATION NAME 2"
  ],
  "consumables_excluded": [
    "CONSUMABLE ITEM 1",
    "CONSUMABLE ITEM 2"
  ],
  "total_medications_count": <number>,
  "total_consumables_excluded_count": <number>
}

# MEDICAL REASONING:

For each item ask:
- Does this have a therapeutic effect on the patient?
- Is this prescribed for treatment/prevention of disease?
- Does this contain an active pharmaceutical ingredient (API)?
- Would a pharmacist dispense this as a medication?

If YES → INCLUDE
If NO → EXCLUDE (consumable/supply)

# EXAMPLES:

✓ INCLUDE:
- "INJECTIONS-PARACETAMOL INJ 1GM/100ML (AEQUIMOL)"
- "TABLETS-AZTOR 20MG (ATORVASTATIN)"
- "SYRUPS-DUPHALAC SYP 150ML (LACTULOSE)"

✗ EXCLUDE:
- "NS 100ML (AQUA)"
- "WATER FOR INJ 10ML"
- "CSSD INSTRUMENT-ICE SCRAPPER"
- "D10% 500ML(STERIPORT)"

Perform extraction now and return ONLY the JSON object.
"""

# Initialize empty dictionary to store extraction results
combined_output = {}

# Display spinner animation during processing to indicate work in progress
with st.spinner("🔄 Processing document and extracting medications..."):
    try:
        # Create appropriate content part based on file type
        if file_type == "pdf":
            # Create PDF part object containing the uploaded PDF bytes for API request
            content_part = types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",  # Specify MIME type as PDF
                    data=file_data  # Attach PDF bytes
                )
            )
        else:
            # For Google Sheets, send as text
            content_part = f"""
            Here is the Treatment Given sheet data (3rd sheet from Google Sheets):
            
            {file_data}
            """
        
        # Send content and prompt to Gemini API, requesting medication extraction
        response = client.models.generate_content(
            model=f"models/{model_option}",  # Use user-selected model
            contents=[content_part, medication_extraction_prompt]  # Send data and extraction instructions
        )
        
        # Extract text from API response, strip whitespace, handle None responses
        text = (response.text or "").strip() if response else ""
        
        # Check if response is empty or None
        if not text:
            # Show warning to user if no response received
            st.warning("⚠️ No response from AI model")
            st.stop()
        
        # Display raw response in expander
        with st.expander("🔍 View raw AI response"):
            st.text_area("Raw Response", value=text, height=300)
        
        # Attempt to parse the response text as JSON
        try:
            # Clean the response text (remove markdown code blocks if present)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON string into Python dictionary
            parsed = json.loads(text)
            
            # Store successfully parsed JSON in combined output
            combined_output = parsed
            
            # Display success message
            st.success(f"✅ Extraction completed using {model_option}!")
            
            # Display results in organized sections
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 💊 Medications Extracted")
                st.metric("Total Medications", parsed.get("total_medications_count", 0))
                
                medications = parsed.get("medications_extracted", [])
                if medications:
                    for idx, med in enumerate(medications, 1):
                        st.markdown(f"{idx}. {med}")
                else:
                    st.info("No medications found")
            
            with col2:
                st.markdown("### 🚫 Consumables Excluded")
                st.metric("Total Consumables", parsed.get("total_consumables_excluded_count", 0))
                
                consumables = parsed.get("consumables_excluded", [])
                if consumables:
                    for idx, item in enumerate(consumables, 1):
                        st.markdown(f"{idx}. {item}")
                else:
                    st.info("No consumables excluded")
            
            # Display complete JSON
            st.markdown("---")
            st.markdown("## 📊 Complete Results (JSON)")
            st.json(parsed)
            
            # Create download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Download complete JSON
                st.download_button(
                    "💾 Download Complete JSON",
                    data=json.dumps(parsed, indent=2),
                    file_name="medication_extraction_results.json",
                    mime="application/json",
                    key="download_complete"
                )
            
            with col2:
                # Download medications list only
                medications_text = "\n".join(parsed.get("medications_extracted", []))
                st.download_button(
                    "📝 Download Medications List (TXT)",
                    data=medications_text,
                    file_name="medications_list.txt",
                    mime="text/plain",
                    key="download_medications"
                )
            
            with col3:
                # Download as CSV
                if medications:
                    df_output = pd.DataFrame({
                        "Serial No": range(1, len(medications) + 1),
                        "Medication Name": medications
                    })
                    csv = df_output.to_csv(index=False)
                    st.download_button(
                        "📊 Download Medications (CSV)",
                        data=csv,
                        file_name="medications_list.csv",
                        mime="text/csv",
                        key="download_csv"
                    )
            
        # Handle case where response text is not valid JSON
        except json.JSONDecodeError as je:
            # Show warning that parsing failed
            st.warning(f"⚠️ Could not parse AI response as JSON")
            st.error(f"JSON Error: {str(je)}")
            # Display raw text in code block for debugging
            st.code(text)
            
    # Catch any exceptions during processing
    except Exception as e:
        # Display error message with exception details
        st.error(f"❌ Error during processing: {e}")
        import traceback
        st.code(traceback.format_exc())

# Add helpful tips at the bottom
st.markdown("---")
st.markdown("### 💡 Tips:")
st.markdown("""
- **For PDFs**: Upload hospital treatment sheets or discharge summaries
- **For Google Sheets**: 
  - Paste the full Google Sheets URL
  - Make sure the sheet has at least 3 tabs
  - The 3rd tab should contain "Treatment Given" data
  - For private sheets, upload service account JSON credentials
- **Best models for text extraction**: gemini-2.0-flash-exp, gemini-2.5-flash
- **Consumables excluded**: Plain IV fluids, saline, needles, bandages, medical devices, etc.
- **Medications included**: All pharmaceutical agents with therapeutic action
""")

st.markdown("---")
st.markdown("**Note**: This tool uses AI to distinguish medications from consumables based on clinical knowledge. Always verify results with a healthcare professional.")
