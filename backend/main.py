import os
import sys
import shutil
from typing import Optional, List

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from database import get_connection, init_db
from pdf_parser import PDFParser
from fact_extractor import FactExtractor
from vector_engine import VectorEngine
from fact_comparator import FactComparator
from seeder import seed_database

app = FastAPI(
    title="Fact Knowledge Layer API",
    description="API for extracting, grounding, comparing, and reconciling cross-document facts.",
    version="1.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM facts")
    count = cursor.fetchone()[0]
    conn.close()
    if count == 0:
        seed_database()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOADS_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

def rows_to_dicts(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Fact Knowledge Layer Engine"}

@app.get("/api/stats")
def get_stats():
    """Returns database metrics & summary statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents")
    doc_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM facts")
    fact_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM relationships")
    rel_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM case_studies")
    case_count = cursor.fetchone()[0]
    conn.close()
    return {
        "status": "ok",
        "documents_count": doc_count,
        "facts_count": fact_count,
        "relationships_count": rel_count,
        "cases_count": case_count,
        "total_documents": doc_count,
        "total_facts": fact_count,
        "total_relationships": rel_count
    }

@app.get("/api/documents")

def get_documents():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documents ORDER BY id DESC")
    docs = rows_to_dicts(cursor)
    conn.close()
    return {"documents": docs}

@app.get("/api/facts")
def get_facts(
    q: Optional[str] = Query(None, description="Search query for subject or quote"),
    doc_id: Optional[int] = Query(None, description="Filter by Document ID"),
    category: Optional[str] = Query(None, description="Filter by Category")
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM facts WHERE 1=1"
    params = []
    
    if doc_id:
        query += " AND doc_id = ?"
        params.append(doc_id)
        
    if q:
        query += " AND (subject LIKE ? OR exact_quote LIKE ? OR value LIKE ?)"
        pattern = f"%{q}%"
        params.extend([pattern, pattern, pattern])
        
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    facts = rows_to_dicts(cursor)
    conn.close()
    return {"facts": facts, "count": len(facts)}

@app.get("/api/relationships")
def get_relationships(
    type_filter: Optional[str] = Query(None, description="Filter by relationship type")
):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM relationships WHERE 1=1"
    params = []
    
    if type_filter:
        query += " AND relationship_type = ?"
        params.append(type_filter)
        
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rels = rows_to_dicts(cursor)
    conn.close()
    return {"relationships": rels, "count": len(rels)}

@app.get("/api/cases")
def get_cases():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM case_studies ORDER BY case_number ASC")
    cases = rows_to_dicts(cursor)
    conn.close()
    return {"cases": cases}

@app.post("/api/seed")
def trigger_seed():
    try:
        seed_database()
        return {"status": "success", "message": "Database successfully re-seeded."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Robust PDF uploader with file validation, structural extraction, and cross-document reconciliation."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF (.pdf) documents are accepted.")
        
    saved_path = os.path.join(UPLOADS_DIR, file.filename)
    try:
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        page_count = PDFParser.get_page_count(saved_path)
        if page_count == 0:
            raise HTTPException(status_code=400, detail="PDF is empty (0 pages).")
            
        chunks = PDFParser.chunk_pdf(saved_path, pages_per_chunk=5)
        if not chunks:
            raise HTTPException(
                status_code=400, 
                detail="Unable to extract selectable text from PDF. File may be image-only scanned without OCR layer."
            )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Corrupted or unparseable PDF file: {str(e)}")
        
    # Save or update document in DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO documents (filename, filepath, category, page_count) VALUES (?, ?, ?, ?)",
        (file.filename, saved_path, "user_uploaded", page_count)
    )
    doc_id = cursor.lastrowid
    conn.commit()
    
    # Extract Facts
    extractor = FactExtractor()
    new_extracted_facts = []
    
    for chunk in chunks[:4]:  # Process key chunks for fast sub-5s response
        chunk_facts = extractor.extract_facts_from_chunk(
            chunk["text"], file.filename, chunk["start_page"]
        )

        for f in chunk_facts:
            cursor.execute('''
                INSERT INTO facts (doc_id, doc_filename, subject, metric_type, value, numeric_value, unit, temporal_context, scope_context, confidence, page_number, exact_quote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc_id, file.filename, f.get("subject", "Fact"), f.get("metric_type", "general"),
                f.get("value", ""), f.get("numeric_value"), f.get("unit", ""),
                f.get("temporal_context", "N/A"), f.get("scope_context", "N/A"),
                f.get("confidence", 0.9), f.get("page_number", chunk["start_page"]), f.get("exact_quote", "")
            ))
            f_id = cursor.lastrowid
            f["id"] = f_id
            f["doc_id"] = doc_id
            new_extracted_facts.append(f)
            
    conn.commit()
    
    # Fetch existing facts from OTHER documents for comparative matching
    cursor.execute("SELECT * FROM facts WHERE doc_id != ?", (doc_id,))
    existing_facts = rows_to_dicts(cursor)
    
    # Candidate matching via vector engine
    comparator = FactComparator()
    new_relationships = []
    
    if existing_facts and new_extracted_facts:
        all_facts_for_matching = new_extracted_facts + existing_facts
        candidate_pairs = VectorEngine.find_cross_doc_candidate_pairs(all_facts_for_matching, similarity_threshold=0.38)
        
        count = 0
        for fa, fb, sim in candidate_pairs:
            if (fa["doc_filename"] == file.filename or fb["doc_filename"] == file.filename) and count < 6:
                rel = comparator.evaluate_pair(fa, fb)
                cursor.execute('''
                    INSERT INTO relationships (fact_a_id, fact_b_id, doc_a_name, doc_b_name, subject_group, fact_a_summary, fact_b_summary, relationship_type, confidence, reasoning, context_explanation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    rel.get("fact_a_id"), rel.get("fact_b_id"), rel.get("doc_a_name"), rel.get("doc_b_name"),
                    rel.get("subject_group"), rel.get("fact_a_summary"), rel.get("fact_b_summary"),
                    rel.get("relationship_type"), rel.get("confidence", 0.9), rel.get("reasoning", ""), rel.get("context_explanation", "")
                ))
                new_relationships.append(rel)
                count += 1
                
        conn.commit()
        
    conn.close()
    
    return {
        "status": "success",
        "document": {
            "id": doc_id,
            "filename": file.filename,
            "page_count": page_count
        },
        "facts_extracted_count": len(new_extracted_facts),
        "relationships_generated_count": len(new_relationships),
        "extracted_facts": new_extracted_facts,
        "new_relationships": new_relationships
    }

@app.get("/styles.css")
def get_styles():
    index_path = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")

@app.get("/app.js")
def get_app_js():
    index_path = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

# Mount static frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Fact Knowledge Layer API is running. Access /api/cases or /api/facts."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

