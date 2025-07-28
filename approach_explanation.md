# Approach Explanation

## Overview
Our solution is designed to act as an intelligent document analyst, extracting and prioritizing the most relevant sections from a collection of PDFs based on a specific persona and their job-to-be-done. The system is fully generic, supporting diverse document types, personas, and tasks, and is optimized for speed, accuracy, and local execution.

## Methodology

### 1. Document Parsing and Section Extraction
- We use robust PDF parsing libraries (pdfplumber, PyMuPDF) to extract text and structural information from each PDF.
- Headings and sections are detected using a combination of font size, boldness, and semantic cues, ensuring adaptability to various document layouts.
- Only meaningful headings (H1–H4) are retained, and the document outline is flattened for efficient processing.

### 2. Persona and Job-to-be-Done Integration
- The persona and job-to-be-done are extracted from the input JSON and used to guide the relevance analysis.
- Document-level filtering is performed using job keywords to select only the most relevant PDFs for further analysis.

### 3. Section Ranking and Summarization
- For each relevant PDF, the top 3 sections (by heading level and order) are selected to maximize information density and minimize processing time.
- All selected sections are summarized in a single batch call to a local LLM (TinyLlama or Gemma 1B via Ollama), with explicit prompts that reference the persona and job-to-be-done.
- Excerpts are kept very short (20 characters) to ensure the LLM can process all sections efficiently.
- The LLM is instructed to return structured JSON, which is parsed and validated for output.

### 4. Output Construction
- The output JSON strictly follows the required schema, including metadata, extracted sections (with document, section title, importance rank, and page number), and subsection analysis (with refined text and page number).
- Deduplication ensures each PDF and section is processed only once.
- Processing is parallelized (up to 4 threads) for speed, and progress is logged for transparency.

## Efficiency and Constraints
- The solution runs entirely on CPU, using only local models ≤1GB in size.
- No internet access is required at any stage.
- The pipeline is optimized to complete in under 60 seconds for 3–5 documents, as validated in testing.

## Generalization
- The system is robust to a wide variety of document types, personas, and tasks, thanks to flexible heading extraction, prompt engineering, and batching strategies.

## Conclusion
This approach ensures accurate, efficient, and persona-driven document intelligence, fully compliant with the challenge requirements and ready for real-world deployment.
