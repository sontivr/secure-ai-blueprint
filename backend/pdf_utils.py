import pdfplumber


def extract_pages_from_pdf(file_path: str) -> list[dict]:
    pages = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append({
                    "page": page_num,
                    "text": text
                })

    return pages