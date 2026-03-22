"""
Vector Store - Store and retrieve code embeddings using FAISS
Simplified for commit review skill
"""

import os
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


def ensure_dir(directory: str):
    """Ensure directory exists"""
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


class VectorStore:
    """Vector database for code embeddings using FAISS"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.vector_config = self.config.get("vector_store", {})
        self.logger = logging.getLogger(__name__)
        
        self.dimension = None
        self.index = None
        self.metadata = []
        
        self.persist_dir = self.vector_config.get("persist_directory", "./data/vector_store")
        self.distance_metric = self.vector_config.get("distance_metric", "cosine")
        self.index_type = self.vector_config.get("index_type", "HNSW")
        
        # HNSW parameters
        self.m = self.vector_config.get("m", 16)
        self.ef_construction = self.vector_config.get("ef_construction", 200)
        self.ef_search = self.vector_config.get("ef_search", 50)
        
        if not HAS_FAISS:
            self.logger.warning("FAISS not installed, vector store disabled")
            return
            
        ensure_dir(self.persist_dir)
    
    def initialize(self, dimension: int):
        """
        Initialize the vector store
        
        Args:
            dimension: Dimension of embedding vectors
        """
        if not HAS_FAISS:
            return
            
        self.dimension = dimension
        self.logger.info(f"Initializing vector store with dimension {dimension}")
        
        if self.index_type == "HNSW":
            # HNSW index for fast approximate search
            if self.distance_metric == "cosine":
                index = faiss.IndexHNSWFlat(dimension, self.m, faiss.METRIC_INNER_PRODUCT)
            else:
                index = faiss.IndexHNSWFlat(dimension, self.m, faiss.METRIC_L2)
            
            index.hnsw.efConstruction = self.ef_construction
            index.hnsw.efSearch = self.ef_search
            self.index = index
        else:
            # Flat index for exact search
            if self.distance_metric == "cosine":
                self.index = faiss.IndexFlatIP(dimension)
            else:
                self.index = faiss.IndexFlatL2(dimension)
        
        self.metadata = []
        self.logger.info(f"Initialized {self.index_type} index with {self.distance_metric} distance")
    
    def add_vectors(self, vectors: np.ndarray, metadata: List[Dict[str, Any]]):
        """
        Add vectors to the store
        
        Args:
            vectors: Array of embedding vectors (N x dimension)
            metadata: List of metadata dictionaries for each vector
        """
        if not HAS_FAISS or self.index is None:
            return
            
        if len(vectors) != len(metadata):
            raise ValueError("Number of vectors must match number of metadata entries")
        
        vectors = vectors.astype(np.float32)
        
        if self.distance_metric == "cosine":
            faiss.normalize_L2(vectors)
        
        self.index.add(vectors)
        self.metadata.extend(metadata)
        
        self.logger.info(f"Added {len(vectors)} vectors to store (total: {len(self.metadata)})")
    
    def search(self, query_vector: np.ndarray, k: int = 10, 
               min_score: Optional[float] = None, 
               repo_filter: Optional[List[str]] = None,
               element_type_filter: Optional[str] = None) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for similar vectors
        
        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            min_score: Minimum similarity score
            repo_filter: Optional list of repository names to filter by
            element_type_filter: Optional element type to filter by
        
        Returns:
            List of (metadata, score) tuples
        """
        if not HAS_FAISS or self.index is None or len(self.metadata) == 0:
            return []
        
        query_vector = query_vector.astype(np.float32).reshape(1, -1)
        
        if self.distance_metric == "cosine":
            faiss.normalize_L2(query_vector)
        
        search_k = k * 5 if element_type_filter else k
        search_k = min(search_k, len(self.metadata))
        distances, indices = self.index.search(query_vector, search_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            
            # Apply repository filter
            if repo_filter:
                repo_name = self.metadata[idx].get("repo_name")
                if repo_name not in repo_filter:
                    continue
            
            # Apply element type filter
            if element_type_filter:
                elem_type = self.metadata[idx].get("type")
                if elem_type != element_type_filter:
                    continue
            
            # Convert distance to similarity score
            if self.distance_metric == "cosine":
                score = float(dist)
            else:
                score = 1.0 / (1.0 + float(dist))
            
            if min_score is not None and score < min_score:
                continue
            
            results.append((self.metadata[idx], score))
            
            if len(results) >= k:
                break
        
        return results
    
    def get_count(self) -> int:
        """Get number of vectors in store"""
        return len(self.metadata)
    
    def save(self, name: str = "index"):
        """Save index and metadata to disk"""
        if not HAS_FAISS or self.index is None:
            return
        
        try:
            index_path = os.path.join(self.persist_dir, f"{name}.index")
            meta_path = os.path.join(self.persist_dir, f"{name}_meta.pkl")
            
            faiss.write_index(self.index, index_path)
            
            # Save metadata without embeddings
            clean_metadata = []
            for m in self.metadata:
                clean_m = {k: v for k, v in m.items() if k != "embedding"}
                clean_metadata.append(clean_m)
            
            with open(meta_path, 'wb') as f:
                pickle.dump(clean_metadata, f)
            
            self.logger.info(f"Saved index to {self.persist_dir}")
            
        except Exception as e:
            self.logger.error(f"Failed to save index: {e}")
    
    def load(self, name: str = "index") -> bool:
        """Load index and metadata from disk"""
        if not HAS_FAISS:
            return False
        
        index_path = os.path.join(self.persist_dir, f"{name}.index")
        meta_path = os.path.join(self.persist_dir, f"{name}_meta.pkl")
        
        if not os.path.exists(index_path) or not os.path.exists(meta_path):
            self.logger.warning(f"Index files not found at {self.persist_dir}")
            return False
        
        try:
            self.index = faiss.read_index(index_path)
            
            with open(meta_path, 'rb') as f:
                self.metadata = pickle.load(f)
            
            self.dimension = self.index.d
            self.logger.info(f"Loaded index with {len(self.metadata)} vectors")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load index: {e}")
            return False
