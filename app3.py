# Import Streamlit for creating the web interface
import streamlit as st
# Import Google Generative AI library for accessing Gemini models
from google import genai
# Import types for structured API requests
from google.genai import types
# Import JSON library for parsing and formatting structured data
import json
# Import pandas for handling Excel/Sheets data
import pandas as pd

# Configure Streamlit page settings with custom title and wide layout for better visibility
st.set_page_config(page_title="Medical Records Extractor", layout="wide")
# Display main title of the application
st.title("📄 Medical Records → Medication Extractor")

# Create file uploader widget that accepts Excel files (Google Sheets exported as Excel)
uploaded_file = st.file_uploader(
    "Upload Google Sheet (as Excel/XLSX)", 
    type=["xlsx", "xls"],
    help="Download your Google Sheet as Excel file first, then upload here"
)

# Create secure password input field for Gemini API key
api_key = st.text_input(
    "Paste Gemini API key",
    type="password",
    help="Get a free key from https://aistudio.google.com/app/apikey"
)

# Create dropdown menu for selecting which Gemini model to use
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
    help="Best models: gemini-2.0-flash-exp, gemini-2.5-flash"
)

# Check if user has uploaded file
if not uploaded_file:
    st.info("📤 Upload your Google Sheet (as Excel file) to extract medications.")
    st.markdown("**How to download Google Sheet as Excel:**")
    st.markdown("1. Open your Google Sheet")
    st.markdown("2. Go to File → Download → Microsoft Excel (.xlsx)")
    st.markdown("3. Upload the downloaded file here")
    st.stop()

# Check if user has provided API key
if not api_key.strip():
    st.warning("🔑 Paste your Gemini API key to proceed.")
    st.stop()

# Initialize Gemini client
try:
    client = genai.Client(api_key=api_key)
except Exception as e:
    st.error(f"Failed to initialize Gemini client: {e}")
    st.stop()

# Read the 3rd sheet (Treatment Given) from uploaded Excel file
try:
    # Read the 3rd sheet (index 2, 0-based indexing)
    df = pd.read_excel(uploaded_file, sheet_name=2)
    st.success("✅ Successfully loaded Treatment Given sheet (3rd sheet)")
    
    # Display preview of the sheet
    with st.expander("📊 Preview of Treatment Given Sheet"):
        st.dataframe(df.head(20))
    
    # Convert dataframe to string format for LLM processing
    sheet_data = df.to_string()
    
except Exception as e:
    st.error(f"❌ Failed to read 3rd sheet: {e}")
    st.info("💡 Make sure your Excel file has at least 3 sheets and the 3rd one contains Treatment Given data")
    st.stop()

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
✓ Respules, Nebulizers with active drugs (NEB, RESP)
✓ Inhalers with pharmaceutical compounds (INH)
✓ Suppositories with active ingredients (SUPP)
✓ Medicated creams, ointments, gels (with drug compounds)
✓ Medicated mouthwash/gargle (with active pharmaceutical ingredients like Betadine)
✓ Medicated dusting powders (with antifungal/antibiotic agents like Clotrimazole, Neomycin)
✓ IV medications (Paracetamol IV, Pantoprazole IV, etc.)

## EXCLUDE (Consumables & Medical Supplies):
✗ Needles, syringes, cannulas, IV sets
✗ Plain IV fluids WITHOUT medication: NS, DNS, D5%, D10%, D25%, Ringer's Lactate, Water for Injection, Aqua
✗ Bandages, gauze, dressings
✗ Surgical instruments (ice scrapper, etc.)
✗ Soap, sanitizers, hand wash
✗ Toothbrushes, toothpaste
✗ Cotton, swabs, gloves, masks
✗ Catheters, tubes
✗ Medical devices and equipment
✗ Non-medicated powders (plain talcum, cornstarch)

## CRITICAL EXAMPLES:
✓ INCLUDE:
- "BETADINE GARGLE MINT 100ML" → Contains povidone-iodine (antiseptic)
- "DUSTING POWDER-MYCODERM-C 100GM" → Contains clotrimazole (antifungal)
- "DUSTING POWDER-NEOSPORIN 10GM" → Contains neomycin (antibiotic)
- "INJECTIONS-PARACETAMOL 1GM/100ML" → Active medication
- "TABLETS-AZTOR 20MG" → Atorvastatin medication

✗ EXCLUDE:
- "NS 100ML (AQUA)" → Plain normal saline
- "WATER FOR INJ 10ML" → Diluent only
- "D10% 500ML(STERIPORT)" → Plain dextrose
- "DNS INJ 500ML (EASY PORT)" → Plain dextrose-saline
- "CSSD INSTRUMENT-ICE SCRAPPER" → Medical device
- "NS 100 ML INJ (STERIPORT)" → Plain saline

# OUTPUT FORMAT:

Return ONLY this JSON structure:

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

# DECISION CRITERIA:

For each item, ask yourself:
1. Does this have therapeutic/pharmacological action?
2. Does it contain an active pharmaceutical ingredient (API)?
3. Would a pharmacist dispense this as a medication?
4. Is it prescribed for treatment/prevention of disease?

If YES to above → INCLUDE as medication
If NO → EXCLUDE as consumable

Extract medications now from the provided Treatment Given sheet data.
"""

# Process the sheet and extract medications
with st.spinner("🔄 Processing Treatment Given sheet and extracting medications..."):
    try:
        # Prepare content for LLM
        full_prompt = f"""
        Here is the Treatment Given sheet data (3rd sheet from uploaded Excel file):
        
        {sheet_data}
        
        {medication_extraction_prompt}
        """
        
        # Send to Gemini API
        response = client.models.generate_content(
            model=f"models/{model_option}",
            contents=[full_prompt]
        )
        
        # Extract response text
        text = (response.text or "").strip() if response else ""
        
        if not text:
            st.warning("⚠️ No response from AI model")
            st.stop()
        
        # Display raw response in expander
        with st.expander("🔍 View raw AI response"):
            st.text_area("Raw Response", value=text, height=300, key="raw_response")
        
        # Parse JSON response
        try:
            # Clean markdown code blocks if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            result = json.loads(text)
            
            # Display success message
            st.success(f"✅ Extraction completed using {model_option}!")
            
            # Display results in two columns
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 💊 Medications Extracted")
                st.metric("Total Medications", result.get("total_medications_count", 0))
                
                medications = result.get("medications_extracted", [])
                if medications:
                    for idx, med in enumerate(medications, 1):
                        st.markdown(f"{idx}. {med}")
                else:
                    st.info("No medications found")
            
            with col2:
                st.markdown("### 🚫 Consumables Excluded")
                st.metric("Total Consumables", result.get("total_consumables_excluded_count", 0))
                
                consumables = result.get("consumables_excluded", [])
                if consumables:
                    with st.expander("View excluded items"):
                        for idx, item in enumerate(consumables, 1):
                            st.markdown(f"{idx}. {item}")
                else:
                    st.info("No consumables excluded")
            
            # Display complete JSON
            st.markdown("---")
            st.markdown("## 📊 Complete Results")
            st.json(result)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.download_button(
                    "💾 Download JSON",
                    data=json.dumps(result, indent=2),
                    file_name="medication_extraction.json",
                    mime="application/json"
                )
            
            with col2:
                medications_text = "\n".join(result.get("medications_extracted", []))
                st.download_button(
                    "📝 Download TXT",
                    data=medications_text,
                    file_name="medications_list.txt",
                    mime="text/plain"
                )
            
            with col3:
                if medications:
                    df_output = pd.DataFrame({
                        "Sr No": range(1, len(medications) + 1),
                        "Medication Name": medications
                    })
                    csv = df_output.to_csv(index=False)
                    st.download_button(
                        "📊 Download CSV",
                        data=csv,
                        file_name="medications_list.csv",
                        mime="text/csv"
                    )
        
        except json.JSONDecodeError as je:
            st.warning("⚠️ Could not parse AI response as JSON")
            st.error(f"JSON Error: {str(je)}")
            st.code(text)
    
    except Exception as e:
        st.error(f"❌ Error during processing: {e}")
        import traceback
        st.code(traceback.format_exc())

# Help section
st.markdown("---")
st.markdown("### 💡 How to Use:")
st.markdown("""
1. **Download your Google Sheet as Excel:**
   - Open Google Sheet → File → Download → Microsoft Excel (.xlsx)
2. **Upload the Excel file** using the uploader above
3. **Enter your Gemini API key**
4. **Click Process** - The app will automatically read the 3rd sheet (Treatment Given)
5. **Download results** in JSON, TXT, or CSV format

**What gets extracted:**
- ✅ All medications: tablets, injections, syrups, respules, medicated items
- ❌ Excluded: Plain IV fluids (NS, DNS, D10%), medical devices, consumables
""")

st.markdown("---")
st.caption("⚠️ Always verify AI-extracted medications with a healthcare professional")
