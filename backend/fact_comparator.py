import os
import json
import time
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

class FactComparator:
    """Evaluates fact pairs across documents to classify relationships and generate AI reasoning."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[FactComparator] Warning: {e}")

    MODEL_FALLBACKS = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]

    def evaluate_pair(self, fact_a: Dict[str, Any], fact_b: Dict[str, Any]) -> Dict[str, Any]:
        """Compares two facts from different documents and classifies their relationship."""
        
        # Check rule-based normalization & edge cases first
        rule_res = self._rule_based_check(fact_a, fact_b)
        if rule_res:
            return rule_res

        if not self.client:
            return self._fallback_compare(fact_a, fact_b)

        prompt = f"""
You are an expert Fact Knowledge Layer Engine.
Analyze the following two facts extracted from two different PDF documents:

FACT A (Document: "{fact_a.get('doc_filename', 'Doc A')}", Page {fact_a.get('page_number', 1)}):
- Subject: {fact_a.get('subject')}
- Metric/Type: {fact_a.get('metric_type')}
- Value: {fact_a.get('value')} (Numeric: {fact_a.get('numeric_value')}, Unit: {fact_a.get('unit')})
- Temporal Context: {fact_a.get('temporal_context')}
- Scope Context: {fact_a.get('scope_context')}
- Status/Modality: {fact_a.get('status', 'actual')}
- Evidence Quote: "{fact_a.get('exact_quote')}"

FACT B (Document: "{fact_b.get('doc_filename', 'Doc B')}", Page {fact_b.get('page_number', 1)}):
- Subject: {fact_b.get('subject')}
- Metric/Type: {fact_b.get('metric_type')}
- Value: {fact_b.get('value')} (Numeric: {fact_b.get('numeric_value')}, Unit: {fact_b.get('unit')})
- Temporal Context: {fact_b.get('temporal_context')}
- Scope Context: {fact_b.get('scope_context')}
- Status/Modality: {fact_b.get('status', 'actual')}
- Evidence Quote: "{fact_b.get('exact_quote')}"

Evaluate the relationship between Fact A and Fact B carefully.
CRITICAL EVALUATION RULES:
1. "corroborated":
   - Metrics, scope, and time match AND values match or are unit-equivalent (e.g. $1B vs $1,000M, 8.2% vs 8.2 per cent, "fifty million" vs "$50M").
2. "reconciled_by_context":
   - Differing values explained by context:
     a) Time context mismatch (e.g. FY21 vs FY24, Jan 2025 vs Dec 2025, Q1 vs Q4).
     b) Scope context mismatch (e.g. Global vs US region, Company vs Subsidiary, Real GDP vs Nominal GDP).
     c) Status/Modality mismatch (e.g. Forecast/Projection baseline vs Realized Actual).
     d) Missing context (e.g. one fact lacks a reporting year; cannot declare contradiction without period alignment).
     e) "Increased by 15%" vs "Increased to 15%" (delta vs absolute ceiling).
3. "contradiction":
   - EXACT same entity, EXACT same scope, EXACT same period, EXACT same metric definition, but values directly clash without any contextual explanation.
4. "extraction_failure":
   - Flagged when evidence quote is ambiguous, table headers shifted, or parser misread text.

Return ONLY a JSON object with:
- "relationship_type": One of ["corroborated", "contradiction", "reconciled_by_context", "extraction_failure"]
- "confidence": Float (0.0 to 1.0)
- "subject_group": General category name
- "reasoning": Clear step-by-step reasoning (3-4 sentences) citing exact evidence.
- "context_explanation": Detailed explanation of temporal, unit, scale, or scope factors.
"""
        for model_name in self.MODEL_FALLBACKS:
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.1)
                    )
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]

                    res = json.loads(raw_text.strip())
                    res["fact_a_id"] = fact_a.get("id")
                    res["fact_b_id"] = fact_b.get("id")
                    res["doc_a_name"] = fact_a.get("doc_filename")
                    res["doc_b_name"] = fact_b.get("doc_filename")
                    res["fact_a_summary"] = f"{fact_a.get('subject')}: {fact_a.get('value')} ({fact_a.get('temporal_context')})"
                    res["fact_b_summary"] = f"{fact_b.get('subject')}: {fact_b.get('value')} ({fact_b.get('temporal_context')})"
                    return res
                except Exception as e:
                    err_str = str(e)
                    print(f"[{model_name} Attempt {attempt+1}] Gemini comparison notice: {err_str[:120]}")
                    if "503" in err_str or "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        time.sleep(1.5 * (attempt + 1))
                    else:
                        break

        return self._fallback_compare(fact_a, fact_b)


    def _rule_based_check(self, fact_a: Dict[str, Any], fact_b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Deterministic rule check for unit normalization, scale equivalence, and context scope."""
        
        # 1. Scale Normalization (e.g. $1B vs $1000M)
        scale_a = self._normalize_scale(fact_a.get("value", ""), fact_a.get("numeric_value"), fact_a.get("unit", ""))
        scale_b = self._normalize_scale(fact_b.get("value", ""), fact_b.get("numeric_value"), fact_b.get("unit", ""))
        
        temp_a = str(fact_a.get("temporal_context", "")).lower()
        temp_b = str(fact_b.get("temporal_context", "")).lower()
        scope_a = str(fact_a.get("scope_context", "")).lower()
        scope_b = str(fact_b.get("scope_context", "")).lower()
        status_a = str(fact_a.get("status", "actual")).lower()
        status_b = str(fact_b.get("status", "actual")).lower()

        # Check Unit Scale Equivalence Corroboration
        if scale_a and scale_b and abs(scale_a - scale_b) < (0.01 * scale_a) and (not temp_a or not temp_b or temp_a == temp_b):
            return {
                "fact_a_id": fact_a.get("id"),
                "fact_b_id": fact_b.get("id"),
                "doc_a_name": fact_a.get("doc_filename"),
                "doc_b_name": fact_b.get("doc_filename"),
                "subject_group": fact_a.get("subject"),
                "fact_a_summary": f"{fact_a.get('subject')}: {fact_a.get('value')}",
                "fact_b_summary": f"{fact_b.get('subject')}: {fact_b.get('value')}",
                "relationship_type": "corroborated",
                "confidence": 0.98,
                "reasoning": f"Unit scale equivalence confirmed. Fact A ({fact_a.get('value')}) and Fact B ({fact_b.get('value')}) represent equivalent quantitative amounts after normalizing unit scale.",
                "context_explanation": f"Normalized numerical equivalence: {scale_a} == {scale_b}"
            }

        # 2. Status / Modality Mismatch (Forecast vs Actual)
        if ("project" in status_a or "forecast" in status_a) != ("project" in status_b or "forecast" in status_b):
            return {
                "fact_a_id": fact_a.get("id"),
                "fact_b_id": fact_b.get("id"),
                "doc_a_name": fact_a.get("doc_filename"),
                "doc_b_name": fact_b.get("doc_filename"),
                "subject_group": fact_a.get("subject"),
                "fact_a_summary": f"{fact_a.get('subject')}: {fact_a.get('value')} ({status_a})",
                "fact_b_summary": f"{fact_b.get('subject')}: {fact_b.get('value')} ({status_b})",
                "relationship_type": "reconciled_by_context",
                "confidence": 0.96,
                "reasoning": f"Reconciled by modality context. Fact A represents a {status_a}, whereas Fact B represents an {status_b}. Forecast projections naturally differ from realized outcomes.",
                "context_explanation": f"Modality distinction: {status_a} vs {status_b}."
            }

        # 3. Scope Difference (Global vs Regional / Segment vs Total)
        if (scope_a and scope_b and scope_a != scope_b) and ("global" in scope_a or "india" in scope_a or "us" in scope_a or "parcel" in scope_a):
            return {
                "fact_a_id": fact_a.get("id"),
                "fact_b_id": fact_b.get("id"),
                "doc_a_name": fact_a.get("doc_filename"),
                "doc_b_name": fact_b.get("doc_filename"),
                "subject_group": fact_a.get("subject"),
                "fact_a_summary": f"{fact_a.get('subject')}: {fact_a.get('value')} ({fact_a.get('scope_context')})",
                "fact_b_summary": f"{fact_b.get('subject')}: {fact_b.get('value')} ({fact_b.get('scope_context')})",
                "relationship_type": "reconciled_by_context",
                "confidence": 0.95,
                "reasoning": f"Reconciled by organizational/geographic scope. Fact A covers scope '{fact_a.get('scope_context')}', while Fact B covers scope '{fact_b.get('scope_context')}'. Metrics for different scopes are not contradictory.",
                "context_explanation": f"Scope mismatch: {fact_a.get('scope_context')} vs {fact_b.get('scope_context')}."
            }

        # 4. Temporal Mismatch (FY21 vs FY24, different dates)
        if temp_a and temp_b and temp_a != temp_b and ("fy" in temp_a or "fy" in temp_b or "20" in temp_a):
            return {
                "fact_a_id": fact_a.get("id"),
                "fact_b_id": fact_b.get("id"),
                "doc_a_name": fact_a.get("doc_filename"),
                "doc_b_name": fact_b.get("doc_filename"),
                "subject_group": fact_a.get("subject"),
                "fact_a_summary": f"{fact_a.get('subject')}: {fact_a.get('value')} ({fact_a.get('temporal_context')})",
                "fact_b_summary": f"{fact_b.get('subject')}: {fact_b.get('value')} ({fact_b.get('temporal_context')})",
                "relationship_type": "reconciled_by_context",
                "confidence": 0.95,
                "reasoning": f"Reconciled by reporting period. Fact A reports for {fact_a.get('temporal_context')}, whereas Fact B reports for {fact_b.get('temporal_context')}.",
                "context_explanation": f"Temporal mismatch: {fact_a.get('temporal_context')} vs {fact_b.get('temporal_context')}."
            }

        return None

    def _normalize_scale(self, val_str: str, num_val: Optional[float], unit: str) -> Optional[float]:
        """Normalizes numbers across scales (million, billion, Cr, lakh, m, km)."""
        if num_val is None:
            m = re.search(r'(\d+(?:\.\d+)?)', str(val_str).replace(',', ''))
            if m:
                num_val = float(m.group(1))
            else:
                return None

        text = f"{val_str} {unit or ''}".lower()
        multiplier = 1.0

        if re.search(r'\b(?:billion|b)\b', text) or '$1b' in text:
            multiplier = 1_000_000_000.0
        elif re.search(r'\b(?:million|m)\b', text) or '$1m' in text:
            multiplier = 1_000_000.0
        elif re.search(r'\b(?:crore|cr)\b', text):
            multiplier = 10_000_000.0
        elif re.search(r'\b(?:lakh|lac)\b', text):
            multiplier = 100_000.0
        elif re.search(r'\b(?:thousand|k)\b', text):
            multiplier = 1_000.0

        return float(num_val * multiplier)


    def _fallback_compare(self, fact_a: Dict[str, Any], fact_b: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback comparator."""
        return {
            "fact_a_id": fact_a.get("id"),
            "fact_b_id": fact_b.get("id"),
            "doc_a_name": fact_a.get("doc_filename"),
            "doc_b_name": fact_b.get("doc_filename"),
            "subject_group": fact_a.get("subject"),
            "fact_a_summary": f"{fact_a.get('subject')}: {fact_a.get('value')}",
            "fact_b_summary": f"{fact_b.get('subject')}: {fact_b.get('value')}",
            "relationship_type": "corroborated" if fact_a.get("value") == fact_b.get("value") else "reconciled_by_context",
            "confidence": 0.85,
            "reasoning": "Compared using deterministic structural matcher. Facts refer to related metrics across documents.",
            "context_explanation": "Extracted evidence linked across documents."
        }

if __name__ == "__main__":
    comparator = FactComparator()
    print("Enhanced FactComparator loaded.")
