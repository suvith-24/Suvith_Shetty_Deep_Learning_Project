"""Minimal client for a locally running Ollama server (stdlib ``urllib`` only)."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lexisync.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_TIMEOUT_SECONDS,
    RANDOM_SEED,
)
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class OllamaClient:
    """
    Client for communicating with a locally running Ollama model.

    Uses Python's built-in urllib library, so no additional
    HTTP dependency is required.

    Every call records token counts and durations in ``self.usage`` so the
    application can report latency and cost per question.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: int = OLLAMA_TIMEOUT_SECONDS,
        num_ctx: int = OLLAMA_NUM_CTX,
        seed: int | None = RANDOM_SEED,
    ) -> None:

        if not base_url or not base_url.strip():
            raise ValueError("Ollama base URL cannot be empty.")

        if not model or not model.strip():
            raise ValueError("Ollama model name cannot be empty.")

        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.seed = seed
        self.usage: list[dict] = []

    def reset_usage(self) -> None:
        """Clear the per-call usage log (call before answering a question)."""

        self.usage = []

    def usage_summary(self) -> dict:
        """Aggregate token counts and model time over the recorded calls."""

        return {
            "llm_calls": len(self.usage),
            "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in self.usage),
            "completion_tokens": sum(u.get("completion_tokens") or 0 for u in self.usage),
            "llm_seconds": round(sum(u.get("seconds") or 0.0 for u in self.usage), 3),
            "calls": [dict(u) for u in self.usage],
        }

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        response_format: str | None = None,
        purpose: str = "generate",
    ) -> str:
        """
        Generate a response using the configured Ollama model.

        Args:
            prompt: User prompt containing the task and context.
            system_prompt: Optional system-level instructions.
            temperature: Sampling temperature.
            response_format: ``"json"`` to constrain output to valid JSON.
            purpose: Label stored with the usage record (diagnostics only).

        Returns:
            Generated response text.
        """

        return self.generate_with_metadata(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format=response_format,
            purpose=purpose,
        )["text"]

    def generate_with_metadata(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        response_format: str | None = None,
        purpose: str = "generate",
    ) -> dict:
        """Generate text and return it with token counts and timings."""

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if not 0.0 <= temperature <= 2.0:
            raise ValueError(
                "Temperature must be between 0.0 and 2.0."
            )

        options: dict = {"temperature": temperature}
        if self.num_ctx:
            options["num_ctx"] = self.num_ctx
        if self.seed is not None:
            options["seed"] = self.seed

        payload = {
            "model": self.model,
            "prompt": prompt.strip(),
            "stream": False,
            "options": options,
        }

        if system_prompt:
            payload["system"] = system_prompt.strip()

        if response_format:
            payload["format"] = response_format

        request = Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        started = time.perf_counter()

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                response_data = json.loads(
                    response.read().decode("utf-8")
                )

        except HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace",
            )

            logger.error(
                "Ollama HTTP error %d: %s",
                error.code,
                error_body,
            )

            raise RuntimeError(
                f"Ollama returned HTTP {error.code}: {error_body}"
            ) from error

        except URLError as error:
            logger.error(
                "Unable to connect to Ollama: %s",
                error.reason,
            )

            raise ConnectionError(
                "Could not connect to Ollama. "
                "Ensure the Ollama server is running."
            ) from error

        except TimeoutError as error:
            logger.error("Ollama request timed out.")

            raise TimeoutError(
                f"Ollama did not respond within {self.timeout} seconds."
            ) from error

        except json.JSONDecodeError as error:
            logger.error("Invalid JSON response received from Ollama.")

            raise RuntimeError(
                "Ollama returned an invalid JSON response."
            ) from error

        elapsed = time.perf_counter() - started
        generated_text = response_data.get("response")

        if not isinstance(generated_text, str):
            raise RuntimeError(
                "Ollama response does not contain valid generated text."
            )

        generated_text = generated_text.strip()

        if not generated_text:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        record = {
            "purpose": purpose,
            "prompt_tokens": response_data.get("prompt_eval_count"),
            "completion_tokens": response_data.get("eval_count"),
            "seconds": round(elapsed, 3),
        }
        self.usage.append(record)

        logger.info(
            "Ollama generation completed using model: %s (%s, %.1fs, %s+%s tokens).",
            self.model,
            purpose,
            elapsed,
            record["prompt_tokens"],
            record["completion_tokens"],
        )

        return {"text": generated_text, **record}

    def list_models(self) -> list[str]:
        """Return the names of locally available models (raises on failure)."""

        request = Request(url=f"{self.base_url}/api/tags", method="GET")
        with urlopen(request, timeout=5) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        return [
            item.get("name")
            for item in response_data.get("models", [])
            if item.get("name")
        ]

    def status(self) -> dict:
        """Connection and model availability, safe to show in the UI."""

        try:
            models = self.list_models()
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
            return {
                "connected": False,
                "model": self.model,
                "model_available": False,
                "available_models": [],
                "base_url": self.base_url,
                "error": f"{type(error).__name__}: {error}",
            }

        return {
            "connected": True,
            "model": self.model,
            "model_available": self.model in models,
            "available_models": models,
            "base_url": self.base_url,
            "error": None,
        }

    def check_connection(self) -> bool:
        """
        Check whether the configured Ollama model is available.
        """

        status = self.status()
        if not status["connected"]:
            logger.error("Ollama connection check failed: %s", status["error"])
        return status["model_available"]
