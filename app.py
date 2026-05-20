import re
import streamlit as st
import fitz  # PyMuPDF

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

    # Strategy assets + fund assets
    m = re.search(
        r"Total\s+(?:Europe Equity\s+)?Strategy Assets:\s*€\s*([\d.,]+)\s*million.*?Total Fund Assets:\s*€\s*([\d.,]+)\s*million",
        strategy_text,
        re.S | re.I,
    )

    if m:
        fields["strategy_assets"] = german_decimal(m.group(1))
        fields["fund_assets"] = german_decimal(m.group(2))

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
    ter_match = None

    lines = fact_text.splitlines()

    for line in lines:
        if line.strip().startswith("I "):
            numbers = re.findall(r"(\d+\.\d+)%", line)

            if numbers:
                ter_match = numbers[-1]
                break

    if ter_match:
        fields["ter"] = german_decimal(ter_match)
    return fields

def update_text(text, fields):

    replacements = {

        r">\*\d+\*\s+Jahre Investmenterfahrung":
        f">*{fields.get('investment_experience', 'MISSING')}* Jahre Investmenterfahrung",

       r"Gesamtstrategie ~\*[^*]+\*\s+Mio\. Euro":
        f"Gesamtstrategie ~*{fields.get('strategy_assets', 'MISSING')}* Mio. Euro",

       r"SICAV Fondsvolumen ~\*[^*]+\*\s+Mio\. Euro":
        f"SICAV Fondsvolumen ~*{fields.get('fund_assets', 'MISSING')}* Mio. Euro",

        r"Mgmt\. Fee \*[\d,]+\*%":
        f"Mgmt. Fee *{fields.get('mgmt_fee', 'MISSING')}*%",

        r"TER \*[\d,]+\*%":
        f"TER *{fields.get('ter', 'MISSING')}*%",
    }

    updated = text

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
