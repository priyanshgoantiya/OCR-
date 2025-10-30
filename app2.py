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

# Define medication extraction prompt
medication_extraction_prompt = """
TASK:
You are a licensed medical practitioner and clinical pharmacist reviewing hospital treatment records. 
Extract ONLY pharmaceutical medications from the "Treatment Given" document, excluding all medical consumables, supplies, and non-medication items.

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
general_medication_extraction_prompt = """
TASK:
You are a licensed medical practitioner and clinical pharmacist performing medication reconciliation on the Excel workbook. Extract pharmaceutical medications and track consumables from the sheet named exactly "Treatment Given" (3rd sheet). Your primary goal is: (1) list true medications, (2) list consumables/devices (needles, soap, surgical hardware, plain IV fluids, etc.), and (3) surface any items you cannot confidently classify as "uncertain".

# PRIMARY MINDSET:
- Think like a pharmacist reviewing a Medication Administration Record (MAR).
- Prioritize patient safety and clinical plausibility.
- Use both lexical cues (tokens, units, codes) and clinical knowledge (drug suffixes, common brands, APIs) to classify items.
- Where ambiguity exists, do NOT invent — mark as "uncertain" and provide a short rationale.

# WHERE TO EXTRACT:
- Read the sheet named "Treatment Given" (3rd sheet).
- Use the column titled exactly "DRUG / IMPLANT NAME" as the source of truth for each row.

# DECISION LOGIC (applied in order):
1. **Direct format clues (high-confidence):**
   - If the item contains dosage form tokens: `INJ`, `INJECTION`, `TAB`, `TABLET`, `CAP`, `CAPSULE`, `SUPP`, `SUPPOSITORY`, `SYR`, `SYRUP`, `SYP`, `RESP`, `RESPULES`, `NEB`, `INHALER`, `GEL`, `OINT`, `CREAM`, `LOTION`, treat as probable medication **unless** the product name clearly identifies a non-drug (e.g., "sterile water for injection", "IV set", "syringe kit").
2. **Numeric dosing / unit clues:**
   - Presence of units/strengths like `mg`, `g`, `mcg`, `IU`, `ml`, `MG/ML`, `GM`, `%`, `IU/ML`, or patterns like `1GM`, `40MG/4ML` strongly indicate a medication.
3. **Device / implant patterns (high-confidence consumable/device):**
   - If the name contains `KIT`, `SCREW`, `ROD`, `NAIL`, `STENT`, `CONNECTOR`, `PLATE`, `MESH`, `MERSILK`, `SUTURE`, `NEEDLE`, `CANNULA`, `CATHTER`, `DJ STENT`, or size patterns like `5.5MM`, `40MM`, `500MM`, classify as **consumable/device**.
4. **IV fluid / diluent detection (consumable):**
   - Exact or close matches to `NS`, `NORMAL SALINE`, `D5%`, `D10%`, `DNS`, `RINGER`, `RL`, `WATER FOR INJ`, `D25%`, `D50%` → **consumable** (plain fluid).
5. **Topicals, mouthwashes, powders (medication vs consumable):**
   - If topical/mouthwash/cream contains an API or antiseptic name (e.g., `MUPIROCIN`, `POVIDONE`, `CHLORHEXIDINE`, `BETADINE`, `LIGNOCAINE`), classify as **medication**.
   - If topical item is generic/brand without API and clearly a hygiene product (e.g., "soap", "moisturizer", "non-medicated lotion"), classify as **consumable**.
   - If uncertain, put in **uncertain_items** and explain.
6. **Suffix/prefix heuristic for drug names (helpful when format ambiguous):**
   - Common drug suffix/prefix cues (if present, increase probability of medication): `-cillin`, `-floxacin`, `-azole`, `-vir`, `-statin`, `-pril`, `-sartan`, `-olol`, `-prazole`, `-dipine`, `-azole`, `-mycin`, `-cycline`, `-navir`, `-mab`, `-nib`, `-zepam`, `-zolam`, `-azole`, `-tidine`, `-cort`, `-sone`, `-azole`.
7. **Brand mapping and clinical synonyms:**
   - If brand name is present, use clinical knowledge (e.g., `PANTOCID` -> pantoprazole, `AEQUIMOL` -> paracetamol, `MERONEM/MEROZA/ZAXTER` -> meropenem) to classify as medication.
8. **Numeric-only / code-only entries:**
   - If entry looks like only a material code (e.g., `A27054053`) or only numbers/alpha codes with no drug tokens or strengths, classify as **consumable/device** unless surrounding text indicates drug.
9. **Fallback for ambiguous items:**
   - If after applying rules the item remains unclear, add it to **uncertain_items** with a brief reason (e.g., "Ambiguous: contains 'POWDER' but no API; possible topical or nutritive product").

# PROCESSING RULES:
- Extract the exact string from the "DRUG / IMPLANT NAME" column for each row.
- Remove exact duplicates (keep first occurrence order).
- Normalize whitespace but preserve casing, brand and parenthetical generic names.
- Do NOT return material codes separately—only the item string as it appears.
- Produce counts for each category.

# OUTPUT (STRICT JSON ONLY):
Return ONLY valid JSON with these keys:
{
  "medications_extracted": [
    "Exact medication name 1",
    "Exact medication name 2"
  ],
  "consumables_excluded": [
    "Exact consumable/device name 1",
    "Exact consumable/device name 2"
  ],
  "uncertain_items": [
    {
      "item": "Exact original string",
      "reason": "Brief rationale why uncertain"
    }
  ],
  "total_medications_count": <number>,
  "total_consumables_excluded_count": <number>,
  "total_uncertain_count": <number>,
  "clinical_notes": "Concise summary of any heuristic/classification rules you applied or edge cases encountered"
}

# ADDITIONAL GUIDANCE:
- Classify by clinical intent: if a product is likely prescribed/administered for a therapeutic effect, prefer medication.
- If identical item appears multiple times, list it once in medications_extracted or consumables_excluded (do not duplicate).
- For brand names without obvious API, use suffix/prefix heuristics and common-brand mappings; if still uncertain, list under uncertain_items.
- Provide short clinical_notes explaining any systematic rules or notable ambiguous clusters (e.g., "Many 'POWDER' entries lacked API; classified as uncertain").

# FINAL INSTRUCTION:
Now process the full "Treatment Given" sheet (3rd sheet) from the provided Excel workbook. Apply the rules above and return ONLY the JSON output described. Do not output any explanation or additional text.
"""
# Define all prompts dictionary
prompts = {
    "medication_extraction": medication_extraction_prompt,"General medication extraction prompt":general_medication_extraction_prompt
    # Add more prompts here as needed
    # "patient_info": patient_info_prompt,
    # "diagnosis": diagnosis_prompt,
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
