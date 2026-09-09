import math
import re
from typing import List, Dict, Tuple, Any

class VectorEngine:
    """Lightweight, fast TF-IDF Cosine Similarity Engine optimized for 512MB RAM deployments."""

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        words = re.findall(r'\w+', text.lower())
        # Generate word unigrams and bigrams for rich semantic overlap
        unigrams = [w for w in words if len(w) > 2]
        bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words)-1)]
        return unigrams + bigrams

    @classmethod
    def compute_similarity(cls, text1: str, text2: str) -> float:
        tokens1 = cls._tokenize(text1)
        tokens2 = cls._tokenize(text2)
        
        if not tokens1 or not tokens2:
            return 0.0
            
        freq1 = {}
        for t in tokens1:
            freq1[t] = freq1.get(t, 0) + 1
            
        freq2 = {}
        for t in tokens2:
            freq2[t] = freq2.get(t, 0) + 1
            
        all_tokens = set(freq1.keys()).union(set(freq2.keys()))
        
        dot_product = 0.0
        norm1 = 0.0
        norm2 = 0.0
        
        for t in all_tokens:
            v1 = freq1.get(t, 0)
            v2 = freq2.get(t, 0)
            dot_product += v1 * v2
            norm1 += v1 * v1
            norm2 += v2 * v2
            
        magnitude = (math.sqrt(norm1) * math.sqrt(norm2))
        return float(dot_product / magnitude) if magnitude > 0 else 0.0

    @classmethod
    def find_cross_doc_candidate_pairs(cls, facts: List[Dict[str, Any]], similarity_threshold: float = 0.25) -> List[Tuple[Dict[str, Any], Dict[str, Any], float]]:
        """Identifies candidate pairs across different documents using lightweight TF-IDF n-gram vector matching."""
        candidate_pairs = []

        doc_facts = {}
        for f in facts:
            doc_name = f.get("doc_filename", f.get("doc_id", "unknown"))
            doc_facts.setdefault(doc_name, []).append(f)

        doc_names = list(doc_facts.keys())
        if len(doc_names) < 2:
            return candidate_pairs

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

        candidate_pairs.sort(key=lambda x: x[2], reverse=True)
        return candidate_pairs

if __name__ == "__main__":
    t1 = "Delhivery Express Parcel Volume 740 million"
    t2 = "Express parcel volume 717 million shipments"
    sim = VectorEngine.compute_similarity(t1, t2)
    print("TF-IDF Vector Similarity:", sim)
