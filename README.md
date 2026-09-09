# Fact Knowledge Layer — Superjoin Engineering Intern Assignment

An open-ended system built for the **Superjoin Engineering Intern Hiring Assignment** that extracts numerical and semantic facts from PDF documents, grounds every claim to verbatim source evidence and page numbers, and reconciles cross-document relationships into **Corroborations**, **Contradictions**, **Reconciliations by Context**, and **Extraction Failures**.

---

## Live Demo & Setup Instructions

### 🚀 Live Application (No Local Setup Required)
The application is deployed live and ready for instant evaluation:
* **Live App URL:** 🌐 **[https://super-join-assingnment-3642571d56fb.herokuapp.com/](https://super-join-assingnment-3642571d56fb.herokuapp.com/)**

### 📹 Video Demo & Screenshots (Google Drive)
* **Demo Video & Screenshots Link:** 🎥 **[https://drive.google.com/drive/u/0/folders/1A8fCkEy1ocbkZkvZ0g3cvc6dKflrWg3x](https://drive.google.com/drive/u/0/folders/1A8fCkEy1ocbkZkvZ0g3cvc6dKflrWg3x)**

## Approach

### Architecture & Pipeline Overview
1. **Document Grounding (`backend/pdf_parser.py`)**: Uses PyMuPDF (`fitz`) to parse document text and explicit page boundaries (`[PAGE X]`) to link every fact to exact page numbers. Verifies quote existence against source text to prevent hallucinated citations.
2. **Structured LLM Extraction (`backend/fact_extractor.py`)**: Uses Google Gemini 3.6 Flash (`google.genai` SDK) with automatic retry backoff to extract structured schemas (`subject`, `value`, `numeric_value`, `unit`, `temporal_context`, `scope_context`, `status`, `page_number`, `exact_quote`).
3. **Candidate Matching (`backend/vector_engine.py`)**: Uses local `SentenceTransformers` (`all-MiniLM-L6-v2`) embeddings to filter top candidate fact pairs across documents before LLM comparison, avoiding $O(N^2)$ performance bottlenecks.
4. **Relationship Reasoning (`backend/fact_comparator.py`)**: Evaluates candidate pairs and classifies relationships into `corroborated`, `contradiction`, `reconciled_by_context`, or `extraction_failure` with step-by-step reasoning.
5. **Storage & Web Interface (`backend/main.py`, `frontend/`)**: SQLite database (`data/fact_layer.db`) storing documents, facts, relationships, and case studies, served via FastAPI REST API and vanilla HTML/CSS/JS dark-mode dashboard.

### Important Decisions & Trade-Offs
* **Local Vector Prefiltering vs Pure LLM Pairwise**: Pairwise LLM calls across all facts are slow and costly. Prefiltering candidates via local vector embeddings dramatically reduces latency and API usage.
* **SQLite Relational DB vs Graph DB**: SQLite was chosen for zero-dependency portability, fast query execution, and easy deployment on Heroku.
* **Deterministic Normalization Rules + LLM Fallback**: Added unit scale normalization (`$1B` == `$1,000M`) and fallback parsing so the system continues operating cleanly even if API rate limits occur.

### AI Tools Used
* **Google Gemini 3.6 Flash**: Structured fact extraction, schema normalization, and cross-document comparative reasoning.
* **SentenceTransformers (`all-MiniLM-L6-v2`)**: Local vector similarity for candidate pair generation.
* **PyMuPDF**: PDF text extraction and line page grounding.

### Brownie Points Extensions Covered
* **Large PDF Handling**: `PDFParser.chunk_pdf()` streams document pages into 3–5 page windows with `[PAGE X]` tags to prevent LLM context overflows or latency spikes.
* **Knowledge Layer Scaling**: Local `SentenceTransformers` vector prefiltering filters top candidate fact pairs, eliminating $O(N^2)$ pairwise LLM calls across large document sets.
* **Dynamic Schema Evolution**: `FactExtractor` uses open JSON metadata (`temporal_context`, `scope_context`, `unit`, `metric_type`) allowing any numerical or qualitative fact type to be stored dynamically.
* **Incremental Processing**: Uploading a new PDF processes and matches *only* the new document (`/api/upload`) against stored knowledge without rebuilding or wiping existing document facts.

---

## Demonstration of the 4 Required Cases

### 1. Corroborated Fact Across Documents
* **Doc A:** `01-india-economic-survey-2024-25-excerpt.pdf` (Page 46) — *"India's real GDP grew by 8.2 per cent in FY24..."*
* **Doc B:** `02-rbi-annual-report-2024-25-excerpt.pdf` (Page 27) — *"Real GDP growth for 2023-24 was placed at 8.2 per cent..."*
* **System Reasoning:** Both independent institutional reports confirm India's FY24 Real GDP growth at 8.2%. The engine links both evidence quotes as a Corroboration.

### 2. Genuine Contradiction
* **Doc A:** `02-delhivery-annual-report-fy24-excerpt.pdf` (Page 12) — *"Delhivery express parcel volume reached 740 million shipments in FY24..."*
* **Doc B:** `03-delhivery-q4-fy24-earnings-presentation.pdf` (Page 5) — *"Full year FY24 express parcel volume stood at 717 million shipments..."*
* **System Reasoning:** A direct 23 million shipment numerical discrepancy exists between official disclosures for the exact same entity and fiscal period (FY24) without inline footnote explanation.

### 3. Apparent Contradiction Explained by Context
* **Doc A:** `01-delhivery-prospectus-2022-excerpt.pdf` (Page 216) — *"Revenue from operations for the financial year ended March 31, 2021 was ₹3,646.53 million..."*
* **Doc B:** `02-delhivery-annual-report-fy24-excerpt.pdf` (Page 105) — *"Consolidated revenue from operations increased to ₹8,141 Crore in FY24..."*
* **System Reasoning:** The revenue variance (₹3,646.53 Cr vs ₹8,141 Cr) is reconciled by temporal and scope context: pre-IPO FY21 restated summary financials versus post-IPO FY24 consolidated scale.

### 4. Extraction / Reasoning Failure & Handling
* **Doc A:** `01-india-economic-survey-2024-25-excerpt.pdf` (Page 52) — *"The Reserve Bank of India projected headline inflation at 4.5 per cent for FY25..."*
* **Doc B:** `03-imf-india-2025-article-iv-excerpt.pdf` (Page 14) — *"Consumer Price Index (CPI) inflation averaged 4.9 per cent in FY2024/25..."*
* **System Reasoning & Handling:** Initial matching flagged a 0.4% conflict. The system caught a domain failure: comparing an early MPC baseline forecast (4.5%) against an actual realized period average (4.9%). The engine reclassified the link and enriched the metadata schema to prevent false contradiction alerts.

---

## Limitations and Next Steps

### What Does Not Work Yet / Current Limitations
1. **Scanned Image-Only PDFs**: Non-searchable image PDFs without an OCR layer cannot be parsed by PyMuPDF alone (requires Tesseract / Vision model integration).
2. **Complex Multi-Page Tables**: Rotated table columns and multi-page financial tables can occasionally lead to misaligned header associations.
3. **Heuristic Rate Limit Fallback**: When Gemini API limits occur, the fallback regex parser only captures standard percentage and currency patterns rather than complex qualitative facts.

### What We Would Build Next
1. **OCR Pipeline**: Add Tesseract OCR for scanned PDF image pages.
2. **Persistent HNSW Vector Graph Index**: Scale beyond small document sets to thousands of PDFs with persistent vector indices.
3. **Interactive Graph Visualizer**: Add a visual node canvas (e.g. Cytoscape.js) to explore linked claims interactively.

---

## Additional Notes
- **Live Deployment**: Hosted on Heroku (`https://super-join-assingnment-3642571d56fb.herokuapp.com/`).
- **Security & Credentials**: API keys are passed via server environment variables (`GEMINI_API_KEY`). No credentials or sensitive data are committed to the repository.
- **Starter Datasets**: Full starter datasets (`delhivery` & `india-macroeconomy`) are pre-seeded in the database and included under `starter-datasets/`.
