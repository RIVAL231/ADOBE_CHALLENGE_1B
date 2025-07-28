#!/usr/bin/env python3
"""
Enhanced PDF Outline Extractor using PyMuPDF (fitz)

Features:
- Infers heading levels by font size
- Semantic filters to discard non-heading text, form labels (text containing ':')
- Skips pure numeric labels ≥4 digits
- Uses first extracted H1 as title (no forced first-page detection)
- Avoids duplicate title in outline
- Leaves outline empty if no headings detected
- Outputs JSON in specified structure
"""

import fitz  # PyMuPDF
import re
import json
from pathlib import Path
from collections import defaultdict


def clean_text(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip())


def is_likely_heading(text: str) -> bool:
    """Determine if a paragraph is a true heading."""
    t = text.strip()
    # Skip any form label containing colon
    
    # Must contain alphabetic characters
    if not re.search(r'[A-Za-z]', t):
        return False
    # Skip overly long or verbose text
    if len(t) > 150 or len(t.split()) > 15:
        return False
    # Skip sentences (ending punctuation)
    if t.endswith(('.', '?', '!')):
        return False
    # Skip pure numeric labels (4+ digits)
    if re.fullmatch(r'\d{3,}', t):
        return False
    # Skip strings that are primarily numeric with more than 3 digits
    if re.search(r'\d{4,}', t) or re.match(r'\d+[^\w]*$', t):
        return False
    return True


def extract_outline_tree(pdf_path: Path, pdf_dir: Path, max_levels: int = 4):
    """
    Extracts a nested heading tree from the PDF based on standard heading sizes.
    Returns list of nodes: {level:int, text:str, page:int, children:list}.
    """
    # Updated standard heading sizes based on typography standards
    standard_heading_sizes = {
        1: (18, 36),  # H1: 18-36 points
        2: (14, 18),  # H2: 14-18 points
        3: (11, 16),  # H3: 12.7-16 points
        # 4: (12, 13),  # H4: 12-13 points
    }
    body_text_range = (10, 12)  # Body text: 10-12 points
    
    spans = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        # Extract bold flag from span flags
                        bold = bool(span.get("flags", 0) & 4)
                        spans.append({
                            "text": span.get("text", ""),
                            "size": round(span.get("size", 0), 1),
                            "page": page_index,
                            "y": round(span.get("bbox", [0,0,0,0])[1], 1),
                            "bold": bold
                        })
    
    # Group spans into lines with additional metadata
    lines = defaultdict(lambda: {"text": [], "size": 0, "bold": False})
    for sp in spans:
        key = (sp["page"], sp["y"])
        lines[key]["text"].append(sp["text"])
        if sp["size"] > lines[key]["size"]:
            lines[key]["size"] = sp["size"]
        if sp.get("bold"):
            lines[key]["bold"] = True

    # Create paragraphs with enhanced metadata
    paragraphs = []
    for (page, y), info in lines.items():
        text = clean_text("".join(info["text"]))
        if text:
            paragraphs.append({
                "text": text, 
                "size": info["size"], 
                "bold": info["bold"],
                "page": page, 
                "y": y
            })

    if not paragraphs:
        return []

    # Universal fragment merging for all PDFs (not just file04)
    # Sort paragraphs by page and position
    sorted_paragraphs = sorted(paragraphs, key=lambda x: (x["page"], x["y"]))
    merged_paragraphs = []
    current_paragraph = None
    
    for p in sorted_paragraphs:
        # Start a new paragraph if:
        # 1. This is the first paragraph
        # 2. Current text ends with a period, colon, or bullet
        # 3. This text starts with a capital letter, number, or bullet
        # 4. This is on a different page
        # 5. Font size or formatting is significantly different
        if (current_paragraph is None or
            current_paragraph["text"].endswith(('.', ':', '•', '-', '?', '!')) or
            (p["text"] and (p["text"][0].isupper() or p["text"][0].isdigit() or p["text"].startswith(('•', '-')))) or
            p["page"] != current_paragraph["page"] or
            abs(p["size"] - current_paragraph["size"]) > 1 or
            p["bold"] != current_paragraph["bold"]):
            
            if current_paragraph:
                merged_paragraphs.append(current_paragraph)
            current_paragraph = p.copy()
        else:
            # Merge with current paragraph
            current_paragraph["text"] += " " + p["text"]
    
    if current_paragraph:
        merged_paragraphs.append(current_paragraph)
    
    paragraphs = merged_paragraphs

    # Classify headings based on standard size ranges and formatting
    candidates = []
    for p in paragraphs:
        if not is_semantic_heading(p["text"]):
            continue
        font_size = p["size"]
        is_bold = p["bold"]
        heading_level = None
        for level, (min_size, max_size) in standard_heading_sizes.items():
            if min_size <= font_size <= max_size:
                heading_level = level
                break
        if heading_level is None and is_bold and font_size > body_text_range[1]:
            heading_level = 4
        if heading_level is not None and 1 <= heading_level <= 4:
            p["level"] = heading_level
            candidates.append(p)
    
    # Sort by page and position
    candidates.sort(key=lambda p: (p["page"], p["y"]))
    
    # Build nested heading tree
    tree = []
    stack = []
    for p in candidates:
        lvl = p["level"]
        node = {"level": lvl, "text": p["text"], "page": p["page"], "children": []}
        while stack and stack[-1]["level"] >= lvl:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            tree.append(node)
        stack.append(node)
    return tree


def is_semantic_heading(text: str) -> bool:
    """Enhanced check to identify true semantic headings vs. non-text elements."""
    t = text.strip()
    # Must have at least 2 words and 8 alphabetic characters
    if len(t.split()) < 2:
        return False
    if sum(c.isalpha() for c in t) < 8:
        return False
    # Skip if too long or too short
    if len(t) > 80 or len(t) < 8:
        return False
    # Must start with uppercase or digit
    if not (t[0].isupper() or t[0].isdigit()):
        return False
    # Skip if ends with comma, semicolon, or is a list item
    if t.endswith((',', ';')) or t.startswith(('•', '-', '*')):
        return False
    # Skip if mostly non-alphanumeric
    if sum(c.isalnum() for c in t) / len(t) < 0.5:
        return False
    # Skip common non-heading phrases
    non_heading_phrases = ['please ', 'thank you', 'copyright', 'all rights', 'phone:', 'email:', 'address:']
    if any(phrase in t.lower() for phrase in non_heading_phrases):
        return False
    return True


def is_valid_title(text: str) -> bool:
    """Check if text is a valid document title, not just formatting or contact info."""
    t = text.strip()
    
    # Must have significant alphanumeric content
    if len(t) == 0 or sum(c.isalnum() for c in t) / len(t) < 0.7:
        return False
        
    # Skip contact info, URLs, etc.
    if re.search(r'^(www\.|http|address:|phone:|email:|rsvp:)', t.lower()):
        return False
        
    # Skip separator lines, decorative elements
    if re.match(r'^[-=*_+#]{3,}$', t):
        return False
        
    # Title should be reasonably short
    if len(t) > 100 or len(t.split()) > 12:
        return False
        
    return True


def flatten_outline(tree, title_text=None):
    """Flatten nested tree into list, skipping duplicate title."""
    flat = []
    for n in tree:
        if not (title_text and n["text"] == title_text and n["level"] == 1):
            flat.append({"level": f"H{n['level']}", "text": n["text"], "page": n["page"]})
        if n.get("children"):
            flat.extend(flatten_outline(n["children"], title_text))
    return flat


def flatten_outline_to_sections(outline, min_level=1, max_level=2):
    """
    Flattens the heading tree to only include sections from H1 and H2.
    """
    sections = []
    def recurse(nodes):
        for node in nodes:
            if min_level <= node['level'] <= max_level:
                sections.append({
                    "text": node["text"],
                    "page": node["page"]
                })
            if node.get("children"):
                recurse(node["children"])
    recurse(outline)
    return sections


def generate_outline_json(pdf_path: Path, output_path: Path):
    pdf_dir = pdf_path.parent
    tree = extract_outline_tree(pdf_path, pdf_dir)
    first_h1 = next((n for n in tree if n["level"] == 1), None)
    second_h2 = next((n for n in tree if n["level"] == 2 and n != first_h1), None)
    title = first_h1["text"] if first_h1 else second_h2["text"] if second_h2 else ""
    outline = flatten_outline(tree, title_text=title)
    result = {"title": title, "outline": outline}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)


def main():
    input_dir = Path("input")
    output_dir = Path("output")
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs in {input_dir.resolve()}. Place files there.")
        return
    for pdf in pdf_files:
        out_file = output_dir / f"{pdf.stem}.json"
        print(f"Processing {pdf.name} -> {out_file.name}")
        generate_outline_json(pdf, out_file)
    print("Done.")

if __name__ == "__main__":
    main()