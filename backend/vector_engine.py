import numpy as np
from typing import List, Dict, Tuple, Any

class VectorEngine:
    """Vector similarity engine using SentenceTransformers for fast candidate pair matching."""

    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                print(f"[VectorEngine] Notice: Could not load SentenceTransformer: {e}")
                cls._model = False
        return cls._model

    @classmethod
    def compute_similarity(cls, text1: str, text2: str) -> float:
        model = cls.get_model()
        if model:
            emb1 = model.encode(text1, convert_to_numpy=True)
            emb2 = model.encode(text2, convert_to_numpy=True)
            dot = np.dot(emb1, emb2)
            norm = (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            return float(dot / norm) if norm > 0 else 0.0
        else:
            # Fallback Jaccard string similarity
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            union = words1.union(words2)
            return len(words1.intersection(words2)) / len(union) if union else 0.0

    @classmethod
    def find_cross_doc_candidate_pairs(cls, facts: List[Dict[str, Any]], similarity_threshold: float = 0.45) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
        """Identifies candidate pairs across different documents using vector similarity."""
        candidate_pairs = []
        model = cls.get_model()

        # Separate facts by document
        doc_facts = {}
        for f in facts:
            doc_name = f.get("doc_filename", f.get("doc_id", "unknown"))
            doc_facts.setdefault(doc_name, []).append(f)

        doc_names = list(doc_facts.keys())
        if len(doc_names) < 2:
            return candidate_pairs

        # Pairwise comparison across documents
        for i in range(len(doc_names)):
            for j in range(i + 1, len(doc_names)):
                facts_a = doc_facts[doc_names[i]]
                facts_b = doc_facts[doc_names[j]]

                for fa in facts_a:
                    text_a = f"{fa['subject']} {fa.get('metric_type', '')} {fa.get('unit', '')} {fa.get('scope_context', '')}"
                    for fb in facts_b:
                        text_b = f"{fb['subject']} {fb.get('metric_type', '')} {fb.get('unit', '')} {fb.get('scope_context', '')}"
                        
                        sim = cls.compute_similarity(text_a, text_b)
                        if sim >= similarity_threshold:
                            candidate_pairs.append((fa, fb, sim))

        # Sort candidate pairs by similarity score descending
        candidate_pairs.sort(key=lambda x: x[2], reverse=True)
        return candidate_pairs

if __name__ == "__main__":
    print("VectorEngine module initialized.")
