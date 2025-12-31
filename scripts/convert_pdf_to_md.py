import fitz  # PyMuPDF
import sys
import os

def convert_pdf_to_md(pdf_path, md_path):
    try:
        # Open the PDF file
        doc = fitz.open(pdf_path)
        md_content = ""

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            # Get text from the page
            text = page.get_text("text")
            md_content += f"## Page {page_num + 1}\n\n"
            md_content += text + "\n\n"

        # Write to markdown file
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        print(f"Successfully converted '{pdf_path}' to '{md_path}'")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    input_pdf = "i want to have a system that converts docker syste.pdf"
    output_md = "docker_syste.md"
    
    if os.path.exists(input_pdf):
        convert_pdf_to_md(input_pdf, output_md)
    else:
        print(f"Input file '{input_pdf}' not found.")
