import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

def extract_text_with_ocr(page: fitz.Page) -> str:
    """
    Renders the PyMuPDF page to an image and uses Tesseract OCR to extract text.
    """
    pix = page.get_pixmap(dpi=150)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    text = pytesseract.image_to_string(img)
    return text

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text from a PDF file using PyMuPDF.
    
    Args:
        pdf_path (str): Path to the PDF file.
        
    Returns:
        str: Extracted text.
    """
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def clean_text(text: str) -> str:
    """
    Cleans extracted text by removing headers, footers, and extra whitespace.
    (Basic implementation - to be refined)
    """
    # TODO: Implement robust header/footer removal based on line position or repetition
    lines = text.split('\n')
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return '\n'.join(cleaned_lines)
