"""
Hybrid Retriever - Combines semantic search and keyword search
Simplified for commit review skill (no agency mode)
"""

import logging
import sys
import os
from typing import List, Dict, Any, Tuple, Optional

try:
    import numpy as np
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

try:
    from .vector_store import VectorStore
    from .elements import CodeElement
except ImportError:
    from vector_store import VectorStore
    from elements import CodeElement


class HybridRetriever:
    """Hybrid retrieval combining semantic search and keyword search"""
    
    def __init__(self, config: Dict[str, Any], vector_store: VectorStore):
        self.config = config
        self.retrieval_config = config.get("retrieval", {})
        self.logger = logging.getLogger(__name__)
        
        self.vector_store = vector_store
        
        # Weights for hybrid search
        self.semantic_weight = self.retrieval_config.get("semantic_weight", 0.6)
        self.keyword_weight = self.retrieval_config.get("keyword_weight", 0.4)
        
        # Retrieval parameters
        self.min_similarity = self.retrieval_config.get("min_similarity", 0.3)
        self.max_results = self.retrieval_config.get("max_results", 10)
        
        # BM25 index
        self.bm25 = None
        self.bm25_corpus = []
        self.bm25_elements = []
    
    def index_for_bm25(self, elements: List[Dict[str, Any]]):
        """
        Build BM25 index for keyword search
        
        Args:
            elements: List of code element dictionaries
        """
        if not HAS_BM25:
            return
            
        self.bm25_elements = elements
        self.bm25_corpus = []
        
        for elem in elements:
            # Combine searchable text
            text_parts = []
            if elem.get("name"):
                text_parts.append(elem["name"])
            if elem.get("signature"):
                text_parts.append(elem["signature"])
            if elem.get("docstring"):
                text_parts.append(elem["docstring"])
            if elem.get("summary"):
                text_parts.append(elem["summary"])
            
            text = " ".join(text_parts).lower()
            self.bm25_corpus.append(text)
        
        if self.bm25_corpus:
            self.bm25 = BM25Okapi(self.bm25_corpus)
            self.logger.info(f"Built BM25 index with {len(self.bm25_corpus)} elements")
    
    def retrieve(self, query: str, elements: List[Dict[str, Any]] = None,
                 top_k: int = None, min_score: float = None) -> List[Tuple[Dict[str, Any], float, str]]:
        """
        Retrieve relevant code elements
        
        Args:
            query: Search query
            elements: Optional list of elements to search (uses indexed if None)
            top_k: Number of results
            min_score: Minimum similarity score
        
        Returns:
            List of (element, score, method) tuples
        """
        if top_k is None:
            top_k = self.max_results
        if min_score is None:
            min_score = self.min_similarity
        
        results = []
        
        # Get vector search results
        if self.vector_store and self.vector_store.index is not None:
            results.extend(self._semantic_search(query, top_k))
        
        # Get BM25 results
        if self.bm25:
            results.extend(self._keyword_search(query, top_k))
        
        # Merge and rerank by hybrid score
        merged = self._merge_results(results)
        
        # Filter and return top k
        filtered = [(elem, score, method) for elem, score, method in merged if score >= min_score]
        return filtered[:top_k]
    
    def _semantic_search(self, query: str, top_k: int) -> List[Tuple[Dict[str, Any], float, str]]:
        """Perform semantic search using vector store"""
        if not self.vector_store or not self.vector_store.embedding_dim:
            return []
        
        # This would need the embedder - simplified version
        # In real usage, embedder should be called before
        return []
    
    def _keyword_search(self, query: str, top_k: int) -> List[Tuple[Dict[str, Any], float, str]]:
        """Perform keyword search using BM25"""
        if not self.bm25 or not self.bm25_elements:
            return []
        
        query_lower = query.lower()
        scores = self.bm25.get_scores(query_lower.split())
        
        # Get top k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append((self.bm25_elements[idx], float(scores[idx]), "bm25"))
        
        return results
    
    def _merge_results(self, results: List[Tuple[Dict[str, Any], float, str]]) -> List[Tuple[Dict[str, Any], float, str]]:
        """
        Merge results from multiple retrieval methods using reciprocal rank fusion
        """
        if not results:
            return []
        
        # Group by element id
        element_scores: Dict[str, Dict[str, float]] = {}
        
        for elem, score, method in results:
            elem_id = elem.get("id", id(elem))
            if elem_id not in element_scores:
                element_scores[elem_id] = {}
            element_scores[elem_id][method] = score
            element_scores[elem_id]["element"] = elem
        
        # Calculate hybrid scores
        merged = []
        for elem_id, scores_dict in element_scores.items():
            elem = scores_dict.pop("element")
            
            # Reciprocal rank fusion
            hybrid_score = 0.0
            if "semantic" in scores_dict:
                hybrid_score += self.semantic_weight * scores_dict["semantic"]
            if "bm25" in scores_dict:
                hybrid_score += self.keyword_weight * scores_dict["bm25"]
            
            # Determine primary method
            method = "hybrid"
            if "semantic" in scores_dict and "bm25" not in scores_dict:
                method = "semantic"
            elif "bm25" in scores_dict and "semantic" not in scores_dict:
                method = "bm25"
            
            merged.append((elem, hybrid_score, method))
        
        # Sort by hybrid score
        merged.sort(key=lambda x: x[1], reverse=True)
        return merged
    
    def set_repo_root(self, repo_root: str):
        """Set repository root path (for reference)"""
        self.repo_root = repo_root
