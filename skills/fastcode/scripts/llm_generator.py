"""
LLM Generator - Generate text using LLM APIs
Simplified from FastCode's answer_generator.py
"""

import logging
import os
import sys
from typing import Dict, Any, Optional, Iterator

try:
    from .utils import count_tokens, truncate_to_tokens
except ImportError:
    from utils import count_tokens, truncate_to_tokens

logger = logging.getLogger(__name__)


def openai_chat_completion(client, *, max_tokens, **kwargs):
    """Call OpenAI-compatible chat completions with max_tokens fallback."""
    try:
        return client.chat.completions.create(max_tokens=max_tokens, **kwargs)
    except Exception as e:
        if "max_tokens" in str(e) and "max_completion_tokens" in str(e):
            return client.chat.completions.create(
                max_completion_tokens=max_tokens, **kwargs
            )
        raise


class LLMGenerator:
    """Generate text using LLM APIs (OpenAI, Anthropic, OpenAI-compatible)"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.gen_config = self.config.get("generation", {})
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables
        self._load_env()
        
        # Configuration
        self.provider = self.gen_config.get("provider", "openai")
        self.temperature = self.gen_config.get("temperature", 0.4)
        self.max_tokens = self.gen_config.get("max_tokens", 20000)
        self.max_context_tokens = self.gen_config.get("max_context_tokens", 200000)
        self.reserve_tokens = self.gen_config.get("reserve_tokens_for_response", 10000)
        
        # API keys and endpoints from environment (unified LLM_API_KEY)
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL") or self.gen_config.get("model", "gpt-4")
        
        # Initialize client
        self.client = self._initialize_client()
    
    def _load_env(self):
        """Load environment variables from .env file if present"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
    
    def _initialize_client(self):
        """Initialize LLM client based on provider"""
        if self.provider in ("openai", "openai-compatible", "minimax"):
            api_key = self.api_key
            if not api_key:
                self.logger.warning("LLM_API_KEY not set, LLM generation disabled")
            else:
                try:
                    from openai import OpenAI
                    return OpenAI(api_key=api_key, base_url=self.base_url)
                except ImportError:
                    self.logger.error("openai package not installed")
                    return None
        
        elif self.provider == "anthropic":
            api_key = self.api_key
            if not api_key:
                self.logger.warning("LLM_API_KEY not set")
            try:
                from anthropic import Anthropic
                return Anthropic(api_key=api_key, base_url=self.base_url)
            except ImportError:
                self.logger.error("anthropic package not installed")
                return None
        
        else:
            self.logger.warning(f"Unknown provider: {self.provider}")
            return None
    
    def generate(self, prompt: str) -> str:
        """
        Generate text from prompt
        
        Args:
            prompt: Input prompt
        
        Returns:
            Generated text
        """
        if not self.client:
            return "Error: LLM client not initialized"
        
        # Truncate prompt if too long
        max_input_tokens = self.max_context_tokens - self.reserve_tokens
        if count_tokens(prompt) > max_input_tokens:
            prompt = truncate_to_tokens(prompt, max_input_tokens)
        
        try:
            if self.provider in ("openai", "openai-compatible", "minimax"):
                return self._generate_openai(prompt)
            elif self.provider == "anthropic":
                return self._generate_anthropic(prompt)
            else:
                return f"Error: Unknown provider {self.provider}"
        except Exception as e:
            self.logger.error(f"Generation error: {e}")
            return f"Error: {str(e)}"
    
    def generate_stream(self, prompt: str) -> Iterator[str]:
        """
        Generate text from prompt with streaming
        
        Args:
            prompt: Input prompt
        
        Yields:
            Text chunks
        """
        if not self.client:
            yield "Error: LLM client not initialized"
            return
        
        # Truncate prompt if too long
        max_input_tokens = self.max_context_tokens - self.reserve_tokens
        if count_tokens(prompt) > max_input_tokens:
            prompt = truncate_to_tokens(prompt, max_input_tokens)
        
        try:
            if self.provider in ("openai", "openai-compatible", "minimax"):
                for chunk in self._generate_openai_stream(prompt):
                    yield chunk
            elif self.provider == "anthropic":
                for chunk in self._generate_anthropic_stream(prompt):
                    yield chunk
            else:
                yield f"Error: Unknown provider {self.provider}"
        except Exception as e:
            self.logger.error(f"Stream generation error: {e}")
            yield f"Error: {str(e)}"
    
    def _generate_openai(self, prompt: str) -> str:
        """Generate answer using OpenAI"""
        if self.client is None:
            return "Error: OpenAI client not initialized"
        
        try:
            response = openai_chat_completion(
                self.client,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )
            
            if response and response.choices:
                return response.choices[0].message.content or ""
            return ""
            
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise
    
    def _generate_openai_stream(self, prompt: str) -> Iterator[str]:
        """Generate answer using OpenAI with streaming"""
        if self.client is None:
            yield "Error: OpenAI client not initialized"
            return
        
        try:
            response = openai_chat_completion(
                self.client,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield delta.content
                        
        except Exception as e:
            self.logger.error(f"OpenAI streaming API error: {e}")
            yield f"\n\nError: {str(e)}"
    
    def _generate_anthropic(self, prompt: str) -> str:
        """Generate answer using Anthropic Claude"""
        if self.client is None:
            return "Error: Anthropic client not initialized"
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            if not response or not getattr(response, "content", None):
                raise ValueError(f"Empty response from Anthropic")
            
            first_block = response.content[0] if response.content else None
            text = getattr(first_block, "text", None) if first_block else None
            if text is None:
                raise ValueError(f"Anthropic response has no text")
            
            return text
            
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise
    
    def _generate_anthropic_stream(self, prompt: str) -> Iterator[str]:
        """Generate answer using Anthropic Claude with streaming"""
        if self.client is None:
            yield "Error: Anthropic client not initialized"
            return
        
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            self.logger.error(f"Anthropic streaming API error: {e}")
            yield f"\n\nError: {str(e)}"
    
    def is_available(self) -> bool:
        """Check if LLM is available"""
        return self.client is not None
