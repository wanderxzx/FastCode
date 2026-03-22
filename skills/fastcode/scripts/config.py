"""
Skill Configuration
"""

import os


class SkillConfig:
    """FastCode Commit Review Skill configuration"""
    
    def __init__(self):
        # Default model cache location: skill/data/model/
        _skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _default_cache = os.path.join(_skill_dir, "data", "model")
        
        # Only use env var if it's an absolute path
        _env_cache = os.getenv("EMBEDDING_CACHE", "")
        if _env_cache and os.path.isabs(_env_cache):
            self.model_cache = _env_cache
        else:
            self.model_cache = _default_cache
            
        self.index_dir = None  # Set during load
        
        # Create cache directory
        os.makedirs(self.model_cache, exist_ok=True)
    
    def to_dict(self) -> dict:
        return {
            "embedding": {
                "model": os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
                "device": "auto",
                "batch_size": 32,
                "max_seq_length": 512,
                "normalize_embeddings": True,
                "cache_folder": self.model_cache,
            },
            "vector_store": {
                # persist_directory is set by reviewer.py during load_and_index()
                "distance_metric": "cosine",
                "index_type": "HNSW",
                "m": 16,
                "ef_construction": 200,
                "ef_search": 50,
            },
            "retrieval": {
                "semantic_weight": 0.6,
                "keyword_weight": 0.4,
                "min_similarity": 0.3,
                "max_results": 10,
            },
            "indexing": {
                "index_files": True,
                "index_classes": True,
                "index_functions": True,
                "index_documentation": False,
            },
            "generation": {
                "provider": os.getenv("LLM_PROVIDER", "openai"),
                "model": os.getenv("LLM_MODEL", "gpt-4"),
                "temperature": float(os.getenv("LLM_TEMPERATURE", "0.4")),
                "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "20000")),
                "max_context_tokens": 200000,
                "reserve_tokens_for_response": 10000,
            },
        }
    
    @staticmethod
    def set_env(api_key: str = None, base_url: str = None, model: str = None, 
                provider: str = None, temperature: float = None):
        """Set environment variables for LLM"""
        if api_key:
            os.environ["LLM_API_KEY"] = api_key
        if base_url:
            os.environ["LLM_BASE_URL"] = base_url
        if model:
            os.environ["LLM_MODEL"] = model
        if provider:
            os.environ["LLM_PROVIDER"] = provider
        if temperature is not None:
            os.environ["LLM_TEMPERATURE"] = str(temperature)
