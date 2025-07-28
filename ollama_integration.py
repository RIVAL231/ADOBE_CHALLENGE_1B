import requests
import json
import os
from pathlib import Path
from datetime import datetime
import sys
import time
import concurrent.futures

# from sympy import per

def log(msg):
    print(f"[{datetime.now().isoformat()}] {msg}")

# Ensure parent directory is in sys.path for import
sys.path.append(str(Path(__file__).parent.parent))
from process_pdfs import extract_outline_tree, flatten_outline

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = "gemma3:1b"

def call_ollama(prompt, model=OLLAMA_MODEL):
    log(f"Calling Ollama with prompt (truncated): {prompt[:100]}...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": model, "prompt": prompt},
            stream=True,
            timeout=60
        )
        response.raise_for_status()
        result = ""
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    if "response" in chunk:
                        result += chunk["response"]
                except Exception:
                    continue
        log(f"Ollama response received (truncated): {result[:100]}...")
        return result.strip()
    except requests.Timeout:
        log("Ollama call timed out after 60 seconds!")
        return ""
    except Exception as e:
        log(f"Ollama call failed: {e}")
        return ""

def get_refined_text(section_text, persona, job_to_be_done):
    log(f"Refining section for persona '{persona}' and job '{job_to_be_done}'")
    prompt = (
        f"You are an {persona}!!! whose job is: {job_to_be_done}!!!.\n"
        f"Given the following extracted section {section_text} from a PDF, provide a concise, actionable summary tailored to this persona and job.\n\n"
        f"just return the refined text, no other text.\n\n"
    )
    return call_ollama(prompt)

def select_relevant_documents(input_documents, persona, job_to_be_done):
    # Only keep documents whose filename contains a word from the job description
    import re
    job_words = set(re.findall(r'\w+', job_to_be_done.lower()))
    relevant = []
    for doc in input_documents:
        doc_words = set(re.findall(r'\w+', doc.lower()))
        if job_words & doc_words:
            relevant.append(doc)
    return relevant

def select_relevant_sections(flat_outline, persona, job_to_be_done):
    # For robustness, just use all sections (let the LLM decide relevance in the summary step)
    return flat_outline

def process_pdf(pdf_name, pdf_dir, persona, job_to_be_done, delay):
    log(f"Processing PDF: {pdf_name}")
    pdf_path = Path(pdf_dir) / pdf_name
    outline = extract_outline_tree(pdf_path, Path(pdf_dir))
    flat_outline = flatten_outline(outline)
    main_sections = [s for s in flat_outline if s.get("level") in ("H1", "H2", "H3", "H4")]
    if not main_sections:
        log(f"No main sections found in {pdf_name}, skipping.")
        return [], []
    # Extract the full text (or first N pages for context)
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pdf_text = "\n".join(page.get_text() for page in doc)
    except Exception:
        pdf_text = ""
    result = analyze_pdf_with_llm(pdf_name, main_sections, persona, job_to_be_done, pdf_text)
    time.sleep(delay)
    return result.get("extracted_sections", []), result.get("subsection_analysis", [])

def analyze_collection_with_ollama(input_json_path, pdf_dir, output_json_path, delay=2, max_workers=4):
    log(f"Loading input from {input_json_path}")
    with open(input_json_path, encoding="utf-8") as f:
        input_data = json.load(f)

    persona = input_data.get("persona")
    if isinstance(persona, dict):
        persona = persona.get("role", "")
    job_to_be_done = input_data.get("job_to_be_done")
    if isinstance(job_to_be_done, dict):
        job_to_be_done = job_to_be_done.get("task", "")

    input_documents = [doc.get("filename") for doc in input_data.get("documents", [])]

    extracted_sections = []
    subsection_analysis = []

    log("Selecting relevant documents using job keywords...")
    relevant_documents = list(dict.fromkeys(select_relevant_documents(input_documents, persona, job_to_be_done)))
    if not relevant_documents:
        log("No relevant documents found. Exiting.")
        output = {
            "metadata": {
                "input_documents": input_documents,
                "persona": persona,
                "job_to_be_done": job_to_be_done,
                "processing_timestamp": datetime.now().isoformat()
            },
            "extracted_sections": [],
            "subsection_analysis": []
        }
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        return

    import math
    from process_pdfs import extract_outline_tree, flatten_outline
    def process_and_summarize(pdf_name):
        log(f"Processing PDF: {pdf_name}")
        pdf_path = Path(pdf_dir) / pdf_name
        outline = extract_outline_tree(pdf_path, Path(pdf_dir))
        flat_outline = flatten_outline(outline)
        main_sections = [s for s in flat_outline if s.get("level") in ("H1", "H2", "H3", "H4")]
        if not main_sections:
            log(f"No main sections found in {pdf_name}, skipping.")
            return [], []
        # Keep only top 3 sections
        main_sections.sort(key=lambda x: x.get('level', ''))
        main_sections = main_sections[:3]
        # Extract the full text (or first N pages for context)
        try:
            import fitz
            doc = fitz.open(pdf_path)
            pdf_text = "\n".join(page.get_text() for page in doc)
        except Exception:
            pdf_text = ""
        # Now send to LLM for summarization (all sections in one call)
        result = analyze_pdf_with_llm(pdf_name, main_sections, persona, job_to_be_done, pdf_text)
        return result.get("extracted_sections", []), result.get("subsection_analysis", [])

    # Parallelize PDF processing with max_workers=4
    extracted_sections = []
    subsection_analysis = []
    processed = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for pdf_name in relevant_documents:
            if pdf_name in processed:
                continue
            processed.add(pdf_name)
            futures[executor.submit(process_and_summarize, pdf_name)] = pdf_name
        for future in concurrent.futures.as_completed(futures):
            sections, analysis = future.result()
            extracted_sections.extend(sections)
            subsection_analysis.extend(analysis)

    output = {
        "metadata": {
            "input_documents": input_documents,
            "persona": persona,
            "job_to_be_done": job_to_be_done,
            "processing_timestamp": datetime.now().isoformat()
        },
        "extracted_sections": extracted_sections,
        "subsection_analysis": subsection_analysis
    }

    log(f"Writing output to {output_json_path}")
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    log("Done.")

def analyze_pdf_with_llm(pdf_name, flat_outline, persona, job_to_be_done, pdf_text):
    """
    For each section, ask the LLM for a summary and let it decide if it's relevant. Build the output JSON manually.
    """
    # Batch all section summaries in a single LLM call for speed
    import re
    extracted_sections = []
    subsection_analysis = []
    # Prepare a list of section info for the prompt
    section_infos = []
    for idx, section in enumerate(flat_outline, start=1):
        heading = section.get("text", "")
        page = section.get("page", 1)
        # Get a short excerpt for each section (simulate section text)
        excerpt = pdf_text[:400] if pdf_text else ""
        section_infos.append({
            "idx": idx,
            "heading": heading,
            "page": page,
            "excerpt": excerpt
        })



    # Batch all sections at once, use very short excerpts (20 chars)
    import ast
    batch_all = False
    if len(locals()) > 5 and 'batch_all' in locals():
        batch_all = locals()['batch_all']
    if batch_all:
        batch = section_infos
        prompt = (
            f"You are an expert assistant for a {persona} whose job is: {job_to_be_done}.\n"
            f"Given the following sections from '{pdf_name}', summarize each section for the job.\n"
            "Return a JSON array ONLY, where each item is: {'idx': <idx>, 'summary': <summary>}\n"
            "Sections:\n"
        )
        for info in batch:
            prompt += f"- idx: {info['idx']}, heading: {info['heading']}, excerpt: {info['excerpt'][:20]}\n"
        prompt += ("\nExample output:\n[{'idx': 1, 'summary': '...'}, {'idx': 2, 'summary': '...'}]\n"
                   "Output the JSON array only. Do not add any explanation or code block.")

        response = call_ollama(prompt)
        json_str = response.strip()
        if json_str.startswith('```'):
            json_str = re.sub(r'^```[a-zA-Z]*', '', json_str).strip()
            if json_str.endswith('```'):
                json_str = json_str[:-3].strip()
        match = re.search(r'(\[.*?\])', json_str, re.DOTALL)
        if match:
            json_str = match.group(1)
        json_str_fixed = json_str.replace("'", '"')
        results = None
        try:
            results = json.loads(json_str_fixed)
        except Exception:
            try:
                results = ast.literal_eval(json_str)
            except Exception:
                results = []
        for item in results:
            idx = item.get('idx')
            summary = item.get('summary', '')
            section = section_infos[idx-1]
            extracted_sections.append({
                "document": pdf_name,
                "section_title": section["heading"],
                "importance_rank": len(extracted_sections) + 1,
                "page_number": section["page"]
            })
            subsection_analysis.append({
                "document": pdf_name,
                "refined_text": summary,
                "page_number": section["page"]
            })
    else:
        batch_size = 5
        for i in range(0, len(section_infos), batch_size):
            batch = section_infos[i:i+batch_size]
            prompt = (
                f"You are an expert assistant for a {persona} whose job is: {job_to_be_done}.\n"
                f"Given the following sections from '{pdf_name}', summarize each section for the job.\n"
                "Return a JSON array ONLY, where each item is: {'idx': <idx>, 'summary': <summary>}\n"
                "Sections:\n"
            )
            for info in batch:
                prompt += f"- idx: {info['idx']}, heading: {info['heading']}, excerpt: {info['excerpt'][:20]}\n"
            prompt += ("\nExample output:\n[{'idx': 1, 'summary': '...'}, {'idx': 2, 'summary': '...'}]\n"
                       "Output the JSON array only. Do not add any explanation or code block.")

            response = call_ollama(prompt)
            json_str = response.strip()
            if json_str.startswith('```'):
                json_str = re.sub(r'^```[a-zA-Z]*', '', json_str).strip()
                if json_str.endswith('```'):
                    json_str = json_str[:-3].strip()
            match = re.search(r'(\[.*?\])', json_str, re.DOTALL)
            if match:
                json_str = match.group(1)
            json_str_fixed = json_str.replace("'", '"')
            results = None
            try:
                results = json.loads(json_str_fixed)
            except Exception:
                try:
                    results = ast.literal_eval(json_str)
                except Exception:
                    results = []
            for item in results:
                idx = item.get('idx')
                summary = item.get('summary', '')
                section = section_infos[idx-1]
                extracted_sections.append({
                    "document": pdf_name,
                    "section_title": section["heading"],
                    "importance_rank": len(extracted_sections) + 1,
                    "page_number": section["page"]
                })
                subsection_analysis.append({
                    "document": pdf_name,
                    "refined_text": summary,
                    "page_number": section["page"]
                })

    # If still nothing, treat the whole response as a summary for the first section
    if not extracted_sections and flat_outline:
        heading = flat_outline[0].get("text", "")
        page = flat_outline[0].get("page", 1)
        extracted_sections.append({
            "document": pdf_name,
            "section_title": heading,
            "importance_rank": 1,
            "page_number": page
        })
        subsection_analysis.append({
            "document": pdf_name,
            "refined_text": response.strip(),
            "page_number": page
        })
    return {"extracted_sections": extracted_sections, "subsection_analysis": subsection_analysis}


if __name__ == "__main__":
    analyze_collection_with_ollama(
        input_json_path="Collection 1/challenge1b_input.json",
        pdf_dir="Collection 1/PDFs",
        output_json_path="Collection 1/challenge1b_output.json"
    )

# To run on a different collection, change the arguments below as needed.
# Example for Collection 2:
# analyze_collection_with_ollama(
#     input_json_path="Collection 2/challenge1b_input.json",
#     pdf_dir="Collection 2/PDFs",
#     output_json_path="Collection 2/challenge1b_output_general.json"
# )
# Example for Collection 3:
# analyze_collection_with_ollama(
#     input_json_path="Collection 3/challenge1b_input.json",
#     pdf_dir="Collection 3/PDFs",
#     output_json_path="Collection 3/challenge1b_output_general.json"
# )
