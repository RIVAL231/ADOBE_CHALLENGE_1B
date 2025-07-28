# 🚀 Challenge 1b: Persona-Driven Document Intelligence (with Ollama)

## 🧠 Overview

This project extracts the most relevant sections from PDFs using a local LLM (`gemma3:1b`) via [Ollama](https://ollama.com/). It is fully offline, CPU-only, and designed to work with specific personas and job-to-be-done tasks.

---

## ⚙️ Architecture

This solution runs using **Docker Compose**:

* 🧠 Ollama (runs `gemma3:1b`)
* 🗞️ A PDF parser + section analyzer (our app)

### 🔐 Privacy & Performance

* 100% offline after initial setup
* No internet or GPU required
* Runs fast on modern CPUs

---

## 📅 Input Format

### `challenge1b_input.json`

```json
{
  "challenge_info": {
    "challenge_id": "round_1b_example",
    "test_case_name": "test_case_name"
  },
  "documents": [
    { "filename": "sample.pdf", "title": "Sample Title" }
  ],
  "persona": {
    "role": "Product Manager"
  },
  "job_to_be_done": {
    "task": "Find features relevant to enterprise deployment"
  }
}
```

---

## 📄 Output Format

### `challenge1b_output.json`

```json
{
  "metadata": {
    "input_documents": ["sample.pdf"],
    "persona": "Product Manager",
    "job_to_be_done": "Find features relevant to enterprise deployment"
  },
  "extracted_sections": [
    {
      "document": "sample.pdf",
      "section_title": "Enterprise Features",
      "importance_rank": 1,
      "page_number": 3
    }
  ],
  "subsection_analysis": [
    {
      "document": "sample.pdf",
      "refined_text": "Enterprise features include SSO, RBAC, and custom SLAs.",
      "page_number": 3
    }
  ]
}
```

---

## 🚀 How to Run (3-Step Setup)

> 💡 Use this manual startup flow for full control and reliability.

### 1️⃣ Start Ollama

```bash
docker compose up -d ollama
```

Wait \~30 seconds for it to boot fully.

---

### 2️⃣ Pull the model

```bash
docker exec -it ollama ollama pull gemma3:1b
```

Downloads the 815MB model inside the container.

---

### 3️⃣ Run the app

```bash
docker compose up app --build
```

The app will read input, process PDFs, run LLM extraction, and write final output JSON.

---

## 📂 Output Location

After execution, your result will be saved in the collection directory:

```
Collection X/
├── challenge1b_input.json
├── PDFs/
├── challenge1b_output.json ✅
```

---

## ✏️ Configure Which Collection to Run

Edit `ollama_integration.py`:

```python
if __name__ == "__main__":
    process_collection("Collection 1")  # Change as needed
```

---

## 🧰 Troubleshooting

| ❗ Issue                | ✅ Fix                                              |
| ---------------------- | -------------------------------------------------- |
| `model not found`      | Run step 2 again                                   |
| `connection refused`   | Ensure Ollama is up: `docker compose up -d ollama` |
| LLM errors or timeouts | Run: `docker compose logs ollama`                  |
| Reset all              |                                                    |

```bash
docker compose down
docker compose up -d ollama
# Wait, then repeat steps 2 & 3
```

---

## 📦 Requirements

* Docker Desktop (Windows/Mac) or Docker Engine (Linux)
* At least **8GB RAM**
* Disk space (\~1GB for model)

---

## 📙 Model Info

| Model       | Size  | Description                                                |
| ----------- | ----- | ---------------------------------------------------------- |
| `gemma3:1b` | 815MB | Local language model for summarization & section selection |

---

## 🙌 Why This Approach?

| ✅ Benefit     | ✨ Reason                   |
| ------------- | -------------------------- |
| Offline       | Secure and fast            |
| Step-by-step  | Easy to debug              |
| Local LLM     | No API limits              |
| Persona-aware | Tailored, relevant outputs |

---

> Made for Challenge 1b with ❤️ using PyMuPDF, pdfplumber, and Ollama.
