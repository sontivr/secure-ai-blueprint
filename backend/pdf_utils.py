import pdfplumber

def extract_text_from_pdf(file_path: str) -> str:
    text_chunks = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                text_chunks.append(text)

    return "\n".join(text_chunks)
