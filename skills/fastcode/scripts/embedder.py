"""
Code Embedder - Generate embeddings for code snippets
Extracted from FastCode's embedder.py
"""

import logging
import platform
from typing import List, Dict, Any, Optional
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    import torch
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    SentenceTransformer = None


class CodeEmbedder:
    """Generate embeddings for code using sentence transformers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.embedding_config = config.get("embedding", {})
        self.logger = logging.getLogger(__name__)
        
        self.model_name = self.embedding_config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
        self.device = self.embedding_config.get("device", "auto")
        self.batch_size = self.embedding_config.get("batch_size", 32)
        self.max_seq_length = self.embedding_config.get("max_seq_length", 512)
        self.normalize = self.embedding_config.get("normalize_embeddings", True)
        self.cache_folder = self.embedding_config.get("cache_folder", "./data/models")
        
        # Auto-detect best available device: CUDA > MPS > CPU
        if self.device != "cpu" and HAS_SENTENCE_TRANSFORMERS:
            self.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        
        self.model = None
        self.embedding_dim = None
        
        if HAS_SENTENCE_TRANSFORMERS:
            self.logger.info(f"Loading embedding model: {self.model_name}")
            self.logger.info(f"Model cache folder: {self.cache_folder}")
            self.model = self._load_model()
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            self.logger.info(f"Embedding dimension: {self.embedding_dim}")
        else:
            self.logger.warning("sentence-transformers not installed, embeddings disabled")
    
    def _load_model(self):
        """Load sentence transformer model"""
        if not HAS_SENTENCE_TRANSFORMERS:
            return None
            
        import os
        import re

        # 用户指定的是模型名称，使用缓存, 不存在则先下载
        name_splits = self.model_name.split("/")
        model_path = self.cache_folder + "/" + f"models--{name_splits[0]}--{name_splits[1]}"

        if not os.path.exists(model_path):
            os.makedirs(self.cache_folder, exist_ok=True)
            
            # Set environment variable to force huggingface to use our cache
            os.environ['TRANSFORMERS_CACHE'] = self.cache_folder
            os.environ['HF_HOME'] = self.cache_folder
            os.environ['HF_DATASETS_CACHE'] = os.path.join(self.cache_folder, 'datasets')
            
            self.logger.info(f"Loading model from cache: {self.cache_folder}")
            model = SentenceTransformer(
                self.model_name, 
                device=self.device,
                cache_folder=self.cache_folder
            )
        else:
            snapshots_dir = os.path.join(model_path, "snapshots")
            if os.path.exists(snapshots_dir):
                # 找到 snapshots 下的实际模型目录
                for item in os.listdir(snapshots_dir):
                    item_path = os.path.join(snapshots_dir, item)
                    if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "config.json")):
                        model_path = item_path
                        self.logger.info(f"Found model snapshot at: {model_path}")
                        break
            
            self.logger.info(f"Loading model from direct path: {model_path}")
            model = SentenceTransformer(
                model_path,
                device=self.device
            )

        model.max_seq_length = self.max_seq_length
        return model
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text
        
        Args:
            text: Input text
        
        Returns:
            Embedding vector
        """
        return self.embed_batch([text])[0]
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a batch of texts
        
        Args:
            texts: List of input texts
        
        Returns:
            Array of embedding vectors
        """
        if not texts or not self.model:
            return np.array([])
        
        encode_kwargs = {
            'batch_size': self.batch_size,
            'show_progress_bar': len(texts) > 100,
            'normalize_embeddings': self.normalize,
            'convert_to_numpy': True,
            'device': self.device,
            'convert_to_tensor': False,
        }
        
        if platform.system() == 'Darwin':
            encode_kwargs['pool'] = None
        
        embeddings = self.model.encode(texts, **encode_kwargs)
        
        return embeddings
    
    def embed_code_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for code elements (functions, classes, etc.)
        
        Args:
            elements: List of code element dictionaries
        
        Returns:
            List of elements with embeddings added
        """
        if not elements or not self.model:
            return elements
        
        # Prepare texts for embedding
        texts = [self._prepare_code_text(elem) for elem in elements]
        
        # Generate embeddings
        self.logger.info(f"Generating embeddings for {len(texts)} code elements")
        embeddings = self.embed_batch(texts)
        self.logger.info(f"✓ Successfully generated embeddings for {len(embeddings)} code elements")
        
        # Add embeddings to elements
        for i, elem in enumerate(elements):
            elem["embedding"] = embeddings[i]
            elem["embedding_text"] = texts[i]
        
        return elements
    
    def _prepare_code_text(self, element: Dict[str, Any]) -> str:
        """
        Prepare code element for embedding
        """
        parts = []
        
        if "type" in element:
            parts.append(f"Type: {element['type']}")
        if "name" in element:
            parts.append(f"Name: {element['name']}")
        if "signature" in element:
            parts.append(f"Signature: {element['signature']}")
        if "docstring" in element and element["docstring"]:
            parts.append(f"Documentation: {element['docstring']}")
        if "summary" in element and element["summary"]:
            parts.append(element["summary"])
        if "code" in element:
            code = element["code"]
            if len(code) > 10000:
                code = code[:10000] + "..."
            parts.append(f"Code:\n{code}")
        
        return "\n".join(parts)
    
    def compute_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings
        """
        if self.normalize:
            return float(np.dot(embedding1, embedding2))
        else:
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(np.dot(embedding1, embedding2) / (norm1 * norm2))
    
    def compute_similarities(self, query_embedding: np.ndarray, 
                            embeddings: np.ndarray) -> np.ndarray:
        """
        Compute similarities between query and multiple embeddings
        """
        if self.normalize:
            return np.dot(embeddings, query_embedding)
        else:
            norms = np.linalg.norm(embeddings, axis=1)
            query_norm = np.linalg.norm(query_embedding)
            if query_norm == 0:
                return np.zeros(len(embeddings))
            return np.dot(embeddings, query_embedding) / (norms * query_norm)
