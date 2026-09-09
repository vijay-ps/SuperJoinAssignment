from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class DocumentModel(BaseModel):
    id: Optional[int] = None
    filename: str
    filepath: str
    category: str = "uploaded"
    page_count: int = 0
    created_at: Optional[str] = None

class FactModel(BaseModel):
    id: Optional[int] = None
    doc_id: int
    doc_filename: str = ""
    subject: str
    metric_type: str = "general"
    value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    temporal_context: str = "N/A"
    scope_context: str = "N/A"
    confidence: float = 1.0
    page_number: int = 1
    exact_quote: str

class FactRelationshipModel(BaseModel):
    id: Optional[int] = None
    fact_a_id: int
    fact_b_id: int
    doc_a_name: str
    doc_b_name: str
    subject_group: str = ""
    fact_a_summary: str
    fact_b_summary: str
    relationship_type: str  # 'corroborated', 'contradiction', 'reconciled_by_context', 'extraction_failure'
    confidence: float = 1.0
    reasoning: str
    context_explanation: Optional[str] = None

class CaseStudyModel(BaseModel):
    id: Optional[int] = None
    case_number: int  # 1, 2, 3, 4
    case_name: str
    relationship_type: str
    title: str
    description: str
    doc_a_name: str
    fact_a_quote: str
    fact_a_page: int
    doc_b_name: str
    fact_b_quote: str
    fact_b_page: int
    reasoning: str
    key_insight: str
