import os
import json
import re
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

class FactExtractor:
    """Advanced Fact Extraction Engine with Multi-Model Fallback & Evidence Verification."""

    MODEL_FALLBACKS = ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Warning] Failed to initialize Gemini Client: {e}")

    def extract_facts_from_chunk(self, chunk_text: str, filename: str, start_page: int) -> List[Dict[str, Any]]:
        """Invokes Gemini LLM to extract facts with multi-model fallback & backoff on 503/429 errors."""
        if not self.client:
            return self._heuristic_extract(chunk_text, filename, start_page)

        prompt = f"""
You are an expert Fact Knowledge Layer AI.
Analyze the following text excerpt from PDF document "{filename}" (Page context: {start_page}):

```text
{chunk_text[:3800]}
```

Extract all prominent numerical or semantic facts stated in this text.
Carefully distinguish between:
1. "increased by 15%" vs "increased to 15%"
2. Actual historical metrics vs Future projections / Forecasts / Targets
3. Global / Consolidated vs Regional / Subsidiary scope
4. Negations (e.g. "no debt", "did not acquire") vs Positive assertions
5. Exact values vs Approximations (e.g. "~50M", "more than 100")

For each extracted fact, output a JSON object with:
- "subject": Name of entity/metric (e.g. "Delhivery Express Parcel Volume", "India Real GDP Growth")
- "metric_type": Category ("financial", "economic", "volume", "operational", "governance")
- "value": Value as stated in text (e.g. "6.8%", "₹4,824 Cr", "increased by 15%", "no debt")
- "numeric_value": Extracted float value if numerical, or null if qualitative/non-numeric
- "unit": Metric unit (e.g. "%", "INR Cr", "million packages", "USD", "employees")
- "temporal_context": Time period (e.g. "FY24", "Q4 FY24", "As of Jan 2025", "Undated")
- "scope_context": Specific scope/segment (e.g. "Consolidated", "Express Parcel", "Global", "India Region", "Real GDP")
- "status": Metric modality - EXACTLY ONE of ["actual", "projected", "forecast", "approximate", "negation"]
- "confidence": Float between 0.0 and 1.0 representing extraction confidence
- "page_number": Integer page number where this fact is stated (look for markers like [PAGE X])
- "exact_quote": EXACT VERBATIM quote from the text supporting this fact (MUST exist word-for-word in the text, max 150 chars)

Return ONLY a JSON array of fact objects.
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

                    facts = json.loads(raw_text.strip())
                    if isinstance(facts, list):
                        verified_facts = []
                        for f in facts:
                            f["doc_filename"] = filename
                            quote = f.get("exact_quote", "")
                            if quote and quote in chunk_text:
                                f["verified_grounding"] = True
                            else:
                                val_str = str(f.get("value", ""))
                                matched_sentence = self._find_verbatim_sentence(chunk_text, val_str)
                                if matched_sentence:
                                    f["exact_quote"] = matched_sentence[:150]
                                    f["verified_grounding"] = True
                                else:
                                    f["verified_grounding"] = False
                            verified_facts.append(f)
                        return verified_facts
                except Exception as e:
                    err_str = str(e)
                    print(f"[{model_name} Attempt {attempt+1}] Gemini extraction notice: {err_str[:120]}")
                    if "503" in err_str or "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        time.sleep(1.5 * (attempt + 1))
                    else:
                        break

        # Final resilient fallback
        return self._heuristic_extract(chunk_text, filename, start_page)

    def _find_verbatim_sentence(self, text: str, substring: str) -> Optional[str]:
        """Finds verbatim sentence containing substring to ensure zero quote hallucination."""
        if not substring:
            return None
        lines = text.splitlines()
        for line in lines:
            if substring.lower() in line.lower() and len(line.strip()) > 10:
                return line.strip()
        return None

    def _heuristic_extract(self, chunk_text: str, filename: str, start_page: int) -> List[Dict[str, Any]]:
        """Fallback regex pattern extraction for offline/quota/503 resilience."""
        facts = []
        lines = chunk_text.splitlines()
        current_page = start_page

        for line in lines:
            if "[PAGE " in line:
                m_page = re.search(r'\[PAGE (\d+)\]', line)
                if m_page:
                    current_page = int(m_page.group(1))
                continue

            pct_matches = re.findall(r'([A-Za-z\s]{4,30})\s*(?:was|reached|stood at|grew by|increased to|increased by|is|at)?\s*(\d+(?:\.\d+)?)\s*%', line)
            for subj, val in pct_matches:
                subj_clean = subj.strip()
                if len(subj_clean) > 3:
                    facts.append({
                        "doc_filename": filename,
                        "subject": subj_clean.title(),
                        "metric_type": "economic" if "gdp" in subj_clean.lower() or "growth" in subj_clean.lower() else "general",
                        "value": f"{val}%",
                        "numeric_value": float(val),
                        "unit": "%",
                        "temporal_context": "Period mentioned in text",
                        "scope_context": "General",
                        "status": "actual",
                        "confidence": 0.85,
                        "page_number": current_page,
                        "exact_quote": line[:150],
                        "verified_grounding": True
                    })
        return facts

if __name__ == "__main__":
    extractor = FactExtractor()
    sample = "[PAGE 12] India Real GDP growth reached 6.8% in FY24 according to official reports."
    res = extractor.extract_facts_from_chunk(sample, "test_doc.pdf", 12)
    print("Extracted & verified facts:", res)
