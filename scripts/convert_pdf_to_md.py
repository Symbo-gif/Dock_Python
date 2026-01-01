# Copyright 2024 Michael Maillet, Damien Davison, Sacha Davison
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
