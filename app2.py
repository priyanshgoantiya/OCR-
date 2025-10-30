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

# Define all prompts
# Define medication extraction prompt
medication_extraction_prompt = """
TASK:
You are a licensed medical practitioner and clinical pharmacist reviewing hospital treatment records. Extract ONLY pharmaceutical medications from the "Treatment Given" document, excluding all medical consumables, supplies, and non-medication items.

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
✓ Respules, Nebulizers with active drugs (NEB, RESP, RESPULES)
✓ Inhalers with pharmaceutical compounds (INH)
✓ Suppositories with active ingredients (SUPP)
✓ Medicated creams, ointments, gels (OINT, CREAM with drug compounds)
✓ Medicated mouthwash/gargle (with active pharmaceutical ingredients like Betadine, CXT)
✓ Medicated dusting powders (POWDER with antifungal/antibiotic agents)
✓ IV medications with active drugs (Paracetamol IV, Pantoprazole IV, etc.)
✓ Enemas with medication (e.g., Duphalac Enema)
✓ Protein supplements prescribed as therapeutic nutrition (Albumin, Fitlivon)

## EXCLUDE (Consumables & Medical Supplies):
✗ Surgical implants (screws, rods, connectors, plates, prosthetics)
✗ Sutures and surgical threads (Mersilk, etc.)
✗ Needles, syringes, cannulas, IV sets
✗ Plain IV fluids WITHOUT medication: NS, DNS, D5%, D10%, D25%, D50%, Ringer's Lactate, Water for Injection, Aqua, Saline
✗ Bandages, gauze, dressings
✗ Surgical instruments (ice scrapper, etc.)
✗ Soap, sanitizers, hand wash
✗ Toothbrushes, toothpaste
✗ Cotton, swabs, gloves, masks
✗ Catheters, tubes
✗ Medical devices and equipment
✗ Non-medicated powders (plain talcum, cornstarch)
✗ Anesthetic gases (Sevoflurane) used during surgery

## CRITICAL EXAMPLES FROM REAL DATA:

✓ INCLUDE (Medications):
- "PARACETAMOL INJ 1GM/100ML (AEQUIMOL)" → Analgesic medication
- "MEROPENAM INJ 1GM (ZAXTER)" → Antibiotic
- "PANTOPRAZOLE 40MG (PANTOCID) INJ" → Proton pump inhibitor
- "BUDECORT RESPULES 0.5MG" → Corticosteroid for inhalation
- "DUOLIN 3 RESPULES" → Bronchodilator
- "DULCOFLEX 10MG SUPP (ADULT)" → Laxative suppository
- "FLUCONAZOLE (GOCAN) 200MG/100ML INJ" → Antifungal
- "TEICOPLANIN (T-PLANIN) 400MG INJ" → Antibiotic
- "SHELCAL-500 TAB 15'S" → Calcium supplement
- "LONAZEP MD 0.5 TAB" → Clonazepam (anxiolytic)
- "SERENACE 0.5MG (20TAB)" → Haloperidol (antipsychotic)
- "RANTAC 150 (30 TAB)" → Ranitidine (H2 blocker)
- "CXT MOUTH WASH 100ML" → Chlorhexidine mouthwash (antiseptic)
- "MUPREVENT OINT 5GM" → Mupirocin ointment (antibiotic)
- "BETADINE OINT 20GM" → Povidone-iodine (antiseptic)
- "DUPHALAC ENEMA" → Lactulose enema (laxative)
- "DUPHALAC SYP 250ML" → Lactulose syrup
- "KESOL-20 SYP" → Potassium supplement
- "FITLIVON POWDER (500GM)" → Nutritional supplement (if prescribed therapeutically)
- "ALBUREL 20% INJ 100ML" → Human albumin (therapeutic protein)
- "HUMAN ALBUMIN 20% 50ML (ZENALB)" → Therapeutic protein
- "RESTYL 0.25MG TAB" → Alprazolam (anxiolytic)
- "PRUVICT 2MG TAB" → Prucalopride (GI motility)
- "PARASOFT CREAM 200GM" → Medicated skin cream
- "LIGNOCAINE (LOCAM) 30GM GEL" → Local anesthetic gel

✗ EXCLUDE (Consumables & Supplies):
- "NS 100ML (AQUA)" → Plain normal saline (diluent)
- "NS INJ 500ML (EASY PORT)" → Plain saline
- "NS INJ 500ML (STERIPORT)" → Plain saline
- "NS 100 ML INJ (STERIPORT)" → Plain saline
- "WATER FOR INJ 10ML" → Diluent only
- "D10% 500ML(STERIPORT)" → Plain dextrose solution
- "D5% INJ 250ML (NIRLIFE)" → Plain dextrose
- "D25% INJ 100ML" → Plain dextrose
- "D50% 25ML INJ LIFECARE" → Plain dextrose
- "NS INJ 1000ML (STERIPORT)" → Plain saline
- "CROSSLINK CONNECTOR TIT 40/53MM AOSYS" → Surgical implant
- "POLYAXIAL SCREW DUAL THREAD TIT 5.5MM X 40MM AOSYS" → Surgical implant
- "SPINAL ROD TIT 5.5MM X 500MM AOSYS" → Surgical implant
- "MERSILK NW5028 26MM 3/8 RC 3-0 JJ" → Surgical suture
- "SEVITRUE (SEVOFLURANE) 250ML" → Anesthetic gas (exclude)

## IMPORTANT DISTINCTIONS:

**Human Albumin**: INCLUDE (therapeutic protein used for volume expansion, hypoalbuminemia)
**Plain NS/Saline/Water**: EXCLUDE (used only as diluent/carrier)
**Surgical Hardware**: EXCLUDE (screws, rods, connectors, plates are medical devices, not medications)
**Sutures**: EXCLUDE (surgical materials)

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

For each item in the "DRUG / IMPLANT NAME" column, ask yourself:
1. Does this have therapeutic/pharmacological action on the patient?
2. Does it contain an active pharmaceutical ingredient (API)?
3. Would a pharmacist dispense this as a medication?
4. Is it prescribed for treatment/prevention/diagnosis of disease?

If YES to above questions → INCLUDE as medication
If NO (it's hardware, diluent, or supply) → EXCLUDE as consumable

# SPECIAL INSTRUCTIONS:

- Look for the column named "DRUG / IMPLANT NAME" in the document
- Extract medication names exactly as they appear
- Remove duplicates (same medication appearing multiple times should be listed once)
- Preserve brand names and generic names in parentheses when present
- Do NOT extract material codes (alphanumeric codes in first column)

Extract medications now from the provided Treatment Given document.
""" 

# Process each prompt separately
combined_output = {}
with st.spinner("🔄 Extracting medications from Excel sheet..."):
            # Prepare full prompt with data
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
            
    except Exception as e:
        st.error(f"❌ Failed to process Excel file: {e}")
        st.info("💡 Make sure your Excel file has at least 3 sheets and the 3rd one contains Treatment Given data")
        st.stop()

else:
    st.error("❌ Unsupported file format")
    st.stop()

# Common processing for both file types
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
**Option 1: Upload PDF**
- Upload PDF containing Treatment Given data
- OCR will extract and identify medications

**Option 2: Upload Excel**
- Download Google Sheet as Excel (File → Download → Microsoft Excel)
- Upload the Excel file here
- The 3rd sheet will be automatically processed

**What gets extracted:**
- ✅ **Medications**: Tablets, injections, syrups, respules, medicated creams/ointments, therapeutic proteins
- ❌ **Excluded**: Plain IV fluids (NS, DNS, D10%), surgical implants (screws, rods), sutures, medical devices, consumables

**File Type Detection:**
- PDF: Uses OCR to extract text and identify medications
- Excel: Reads 3rd sheet directly (Treatment Given)
""")

st.markdown("---")
st.caption("⚠️ Always verify AI-extracted medications with a healthcare professional")
