from reportlab.pdfgen import canvas

def create_pdf(path):
    c = canvas.Canvas(path)
    c.drawString(100, 750, "Chapter 1: The Beginning")
    c.drawString(100, 730, "The sun set over the cybernetic city, casting neon shadows.")
    c.drawString(100, 710, "Alice adjusted her trenchcoat and looked at the data pad.")
    c.showPage()
    c.save()

if __name__ == "__main__":
    create_pdf("test_book.pdf")
    print("Created test_book.pdf")
