import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'lumina-reader', 'backend'))

from services.pdf_parser import extract_text_from_pdf, clean_text

def test_extraction():
    pdf_path = "May-Short-Stories.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found")
        return

    print(f"Testing extraction for {pdf_path}...")
    try:
        text = extract_text_from_pdf(pdf_path)
        cleaned = clean_text(text)
        print(f"Extracted {len(text)} characters.")
        print("First 200 characters of cleaned text:")
        print("-" * 20)
        print(cleaned[:200])
        print("-" * 20)
    except Exception as e:
        print(f"Extraction failed: {e}")

if __name__ == "__main__":
    test_extraction()
