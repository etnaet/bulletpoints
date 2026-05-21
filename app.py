import re
import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import io

st.title("Fund Bulletpoints Updater")

st.markdown("""
**How to use:**
1. Upload the **Fact Sheet** and **Strategy Highlights** PDFs from Seismic for the fund you want to update.
2. Paste the **existing German text** from last month's Product Bullets Master File.
3. Click **Generate updated text** to get the refreshed version.

**What this tool can currently update** (numbers must be wrapped in `*asterisks*` in your template):
- **Strategy & Fund Total Assets**
- **Years of investment experience** of the portfolio manager *(note: currently captures the first manager listed only)*
- **Size of the Portfolio** — actual number of holdings/titles in the portfolio
- **Management fee & TER** — for the Class I share class
""")

st.divider()

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
    value = value.strip()
    if "," in value and "." in value:
        value = value.replace(",", "")
        integer, decimal = value.split(".")
        integer_formatted = ""
        for i, digit in enumerate(reversed(integer)):
            if i > 0 and i % 3 == 0:
                integer_formatted = "." + integer_formatted
            integer_formatted = digit + integer_formatted
        return integer_formatted + "," + decimal
    else:
        return value.replace(".", ",")

def extract_fields(fact_text, strategy_text, fact_sheet):

    fields = {}

    # Strategy assets + fund assets together on same line in strategy PDF
    m_strat = re.search(
        r"Total\s+(?:[\w\-]+\s+)*?Strategy Assets:\s*[$€`]([\d.,]+)\s*(million|billion)",
        strategy_text,
        re.I
    )
    if m_strat:
        fields["strategy_assets"] = german_decimal(m_strat.group(1))
        fields["strategy_assets_unit"] = "Mrd." if m_strat.group(2).lower() == "billion" else "Mio."

    # Fund assets: check fact sheet FIRST (more precise), then strategy PDF as fallback
    m = re.search(
        r"Total Fund Assets:\s*[$€`]\s*([\d.,]+)\s*(million|billion)",
        fact_text,
        re.I | re.M
    )
    if m:
        fields["fund_assets"] = german_decimal(m.group(1))
        fields["fund_assets_unit"] = "Mrd." if m.group(2).lower() == "billion" else "Mio."

    if "fund_assets" not in fields:
        m = re.search(
            r"Total Fund Assets:\s*[$€`]\s*([\d.,]+)\s*(million|billion)",
            strategy_text,
            re.I | re.M
        )
        if m:
            fields["fund_assets"] = german_decimal(m.group(1))
            fields["fund_assets_unit"] = "Mrd." if m.group(2).lower() == "billion" else "Mio."

    # Strategy assets alone fallback
    if "strategy_assets" not in fields:
        m = re.search(
            r"Total\s+(?:[\w\s]+?\s+)?Strategy Assets:\s*[$€`]([\d.,]+)\s*(million|billion)",
            strategy_text,
            re.I
        )
        if not m:
            m = re.search(
                r"Strategy Assets:\s*[$€`]([\d.,]+)\s*(million|billion)",
                strategy_text,
                re.I
            )
        if m:
            fields["strategy_assets"] = german_decimal(m.group(1))
            fields["strategy_assets_unit"] = "Mrd." if m.group(2).lower() == "billion" else "Mio."

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
        r"Class I\s+N/A\s+[\d,]+\s+([\d.]+)\s+basis points",
        strategy_text,
        re.I
    )
    if m:
        fields["mgmt_fee"] = german_decimal(str(float(m.group(1)) / 100))

    # TER / Ongoing Management Charge for Class I + Number of Holdings
    uploaded_bytes = fact_sheet.getvalue()
    with pdfplumber.open(io.BytesIO(uploaded_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row:
                        continue
                    clean_row = [
                        str(cell).strip() if cell else ""
                        for cell in row
                    ]

                    # TER: row starts with "I" and has 6+ columns
                    if len(clean_row) >= 6 and clean_row[0] == "I":
                        charge = clean_row[-1]
                        charge = charge.replace("%", "").strip()
                        fields["ter"] = german_decimal(charge)

                    # Number of Holdings: row starts with "Number of Holdings"
                    if clean_row[0].lower().startswith("number of holdings") or \
                       any("number of holdings" in cell.lower() for cell in clean_row):
                        for cell in clean_row[1:]:
                            cell_clean = cell.replace(",", "").strip()
                            if cell_clean.isdigit():
                                fields["number_of_holdings"] = cell_clean
                                break

    return fields

def update_text(text, fields):

    replacements = {
        r">\*\d+\*\s+Jahre Investmenterfahrung":
        f">*{fields.get('investment_experience', 'MISSING')}* Jahre Investmenterfahrung",

        r"Mgmt\. Fee \*[\d,]+\*%":
        f"Mgmt. Fee *{fields.get('mgmt_fee', 'MISSING')}*%",

        r"TER \*[\d,]+\*%":
        f"TER *{fields.get('ter', 'MISSING')}*%",

        r"\*\d+\*\)":
        f"*{fields.get('number_of_holdings', 'MISSING')}*)",
    }

    updated = text

    # Assets in der Gesamtstrategie: + SICAV Fondsvolumen: on same line (colon required for both)
    updated = re.sub(
        r"Assets in der Gesamtstrategie:\s*~?\*[^*]+\*[^/]+//\s*SICAV Fondsvolumen:\s*~?\*[^*]+\*[^•\n]+",
        f"Assets in der Gesamtstrategie: ~*{fields.get('strategy_assets', 'MISSING')} {fields.get('strategy_assets_unit', 'MISSING')}* USD // SICAV Fondsvolumen: ~*{fields.get('fund_assets', 'MISSING')} {fields.get('fund_assets_unit', 'MISSING')}* USD",
        updated
    )

    # SICAV Fondsvolumen standalone (colon required)
    updated = re.sub(
        r"SICAV Fondsvolumen:\s*~?\*[^*]+\*\s*(?:Mio\.|Mrd\.)?\s*(?:Euro|USD)",
        f"SICAV Fondsvolumen: ~*{fields.get('fund_assets', 'MISSING')} {fields.get('fund_assets_unit', 'MISSING')}* USD",
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
        st.error("Please upload both PDFs and paste the German text.")

    else:
        fact_text = read_pdf(fact_sheet)
        strategy_text = read_pdf(strategy)

        fields = extract_fields(
            fact_text,
            strategy_text,
            fact_sheet
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
