"""
Model Adapter Layer for Sentinel.
Provides a pluggable inference interface supporting:
- GroqAdapter (sub-second inference on open models like Llama-3.2-3B)
- OllamaAdapter (100% offline local inference)
- MockModelAdapter (deterministic scripted execution for unit tests and zero-dependency runs)
"""

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any


class ModelAdapter(ABC):
    """Abstract interface for LLM inference."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate text completion given a prompt and optional system instructions."""
        pass


class MockModelAdapter(ModelAdapter):
    """
    Deterministic scripted model adapter for unit tests and offline demonstrations.
    Returns sequenced responses or contextual rule-based tool outputs.
    """

    def __init__(self, scripted_responses: list[str] | None = None):
        self.scripted_responses = list(scripted_responses or [])
        self.call_count = 0
        self.history: list[dict[str, Any]] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.history.append({"prompt": prompt, "system_prompt": system_prompt})
        if self.scripted_responses and self.call_count < len(self.scripted_responses):
            resp = self.scripted_responses[self.call_count]
            self.call_count += 1
            return resp

        # Context-aware fallback generation
        prompt_lower = prompt.lower()
        if "plan" in prompt_lower:
            return json.dumps([
                "Read the failing module to identify bug",
                "Write the corrected code to the module",
                "Run test suite to verify fix",
            ])
        elif "read_file" in prompt_lower:
            return json.dumps({
                "tool": "read_file",
                "args": {"path": "module.py"},
            })
        elif "write_file" in prompt_lower or "propose" in prompt_lower or "fix" in prompt_lower:
            return json.dumps({
                "tool": "write_file",
                "args": {
                    "path": "module.py",
                    "content": "def fix():\n    return True\n",
                },
            })
        elif "test" in prompt_lower or "verify" in prompt_lower:
            return json.dumps({
                "tool": "run_shell",
                "args": {"cmd": "python3 -c \"assert True\""},
            })

        return json.dumps({"action": "complete", "message": "Task processed"})


class GroqAdapter(ModelAdapter):
    """
    High-speed inference adapter via Groq Cloud API.
    Runs open-weight models (Llama 3.2 1B/3B, Llama 3.1 8B) at 500-800 tok/sec.
    Zero external pip dependencies (uses standard urllib).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "llama-3.2-3b-preview",
        base_url: str = "https://api.groq.com/openai/v1/chat/completions",
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self.api_key:
            raise ValueError("Groq API key not provided and GROQ_API_KEY environment variable is unset.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Sentinel-Harness/0.1.0",
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Groq API error (HTTP {e.code}): {err_body}")
        except Exception as e:
            raise RuntimeError(f"Groq connection failure: {e}")


class OllamaAdapter(ModelAdapter):
    """
    100% offline local inference adapter via Ollama.
    Runs locally served GGUF models on CPU/GPU.
    """

    def __init__(
        self,
        model: str = "qwen2.5-coder:1.5b",
        base_url: str = "http://localhost:11434/api/chat",
    ):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"Local Ollama connection failure: {e}. Ensure 'ollama serve' is running.")


def get_model_adapter(
    provider: str = "mock",
    model: str | None = None,
    api_key: str | None = None,
    scripted_responses: list[str] | None = None,
) -> ModelAdapter:
    """Factory helper to obtain the requested model adapter."""
    prov_lower = provider.lower()
    if prov_lower == "groq":
        return GroqAdapter(api_key=api_key, model=model or "llama-3.2-3b-preview")
    elif prov_lower in ("ollama", "local"):
        return OllamaAdapter(model=model or "qwen2.5-coder:1.5b")
    else:
        return MockModelAdapter(scripted_responses=scripted_responses)
