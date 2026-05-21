import re
import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import io

st.title("Fund Text Updater")

fact_sheet = st.file_uploader(
    "Upload Fact Sheet PDF",
    type="pdf"
)

strategy = st.file_uploader(
    "Upload Strategy Highlights PDF",
    type="pdf"
)

template = st.text_area(
    "Paste German fund text template",
    height=300
)

def read_pdf(uploaded_file):
    doc = fitz.open(
        stream=uploaded_file.read(),
        filetype="pdf"
    )

    text = ""

    for page in doc:
        text += page.get_text()

    return text

def german_decimal(value):
    return value.replace(".", ",")

def extract_fields(fact_text, strategy_text):

    fields = {}

    # Strategy assets + fund assets from Strategy Highlights title area
    m = re.search(
        r"Total\s+Strategy\s+Assets:\s*[$€]\s*([\d.,]+)\s*(million|billion)\s*\|\s*Total\s+Fund\s+Assets:\s*[$€]\s*([\d.,]+)\s*(million|billion)",
        strategy_text,
        re.I,
    )

    if m:
        fields["strategy_assets"] = german_decimal(m.group(1))
        fields["strategy_assets_unit"] = "Mrd." if m.group(2).lower() == "billion" else "Mio."
        fields["fund_assets"] = german_decimal(m.group(3))
        fields["fund_assets_unit"] = "Mrd." if m.group(4).lower() == "billion" else "Mio."

    # Investment experience
    m = re.search(
        r"(\d+)\s+years of investment experience",
        strategy_text,
        re.I
    )

    if m:
        fields["investment_experience"] = m.group(1)

    # Management fee: Class I
    m = re.search(
        r"Class I\s+N/A\s+[\d,]+\s+(\d+)\s+basis points",
        strategy_text,
        re.I
    )

    if m:
        fields["mgmt_fee"] = german_decimal(str(int(m.group(1)) / 100))
        
       # TER / Ongoing Management Charge for Class I
    import pdfplumber

    uploaded_bytes = fact_sheet.getvalue()

    with pdfplumber.open(io.BytesIO(uploaded_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                for row in table:
                    if row and len(row) >= 6:
                        clean_row = [
                            str(cell).strip() if cell else ""
                            for cell in row
                        ]

                        if clean_row[0] == "I":
                            charge = clean_row[-1]
                            charge = charge.replace("%", "").strip()
                            fields["ter"] = german_decimal(charge)
    return fields

def update_text(text, fields):

    replacements = {

        r">\*\d+\*\s+Jahre Investmenterfahrung":
        f">*{fields.get('investment_experience', 'MISSING')}* Jahre Investmenterfahrung",

        r"Mgmt\. Fee \*[\d,]+\*%":
        f"Mgmt. Fee *{fields.get('mgmt_fee', 'MISSING')}*%",

        r"TER \*[\d,]+\*%":
        f"TER *{fields.get('ter', 'MISSING')}*%",
    }

    updated = text

        updated = re.sub(
        r"Gesamtstrategie ~\*[^*]+\*\s+(?:Mio\.|Mrd\.)\s+(?:Euro|USD)\s*//\s*SICAV Fondsvolumen ~\*[^*]+\*\s+(?:Mio\.|Mrd\.)\s+(?:Euro|USD)",
        f"Gesamtstrategie ~*{fields.get('strategy_assets', 'MISSING')}* {fields.get('strategy_assets_unit', 'MISSING')} USD // SICAV Fondsvolumen ~*{fields.get('fund_assets', 'MISSING')}* {fields.get('fund_assets_unit', 'MISSING')} USD",
        updated
    )

    for pattern, replacement in replacements.items():
        updated = re.sub(
            pattern,
            replacement,
            updated
        )

    return updated

if st.button("Generate updated text"):

    if not fact_sheet or not strategy or not template:

        st.error(
            "Please upload both PDFs and paste the German text."
        )

    else:

        fact_text = read_pdf(fact_sheet)
        strategy_text = read_pdf(strategy)

        fields = extract_fields(
            fact_text,
            strategy_text
        )

        updated = update_text(
            template,
            fields
        )

        st.subheader("Updated text")

        st.text_area(
            "Copy this",
            updated,
            height=350
        )

        st.download_button(
            "Download updated text",
            updated,
            file_name="updated_fund_text.txt",
            mime="text/plain",
        )
