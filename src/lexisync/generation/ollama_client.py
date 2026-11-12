
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lexisync.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from lexisync.utils.logger import get_logger


logger = get_logger(__name__)


class OllamaClient:
    """
    Client for communicating with a locally running Ollama model.

    Uses Python's built-in urllib library, so no additional
    HTTP dependency is required.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: int = 180,
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

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> str:
        """
        Generate a response using the configured Ollama model.

        Args:
            prompt: User prompt containing the task and context.
            system_prompt: Optional system-level instructions.
            temperature: Sampling temperature.

        Returns:
            Generated response text.
        """

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if not 0.0 <= temperature <= 2.0:
            raise ValueError(
                "Temperature must be between 0.0 and 2.0."
            )

        payload = {
            "model": self.model,
            "prompt": prompt.strip(),
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt.strip()

        request = Request(
            url=f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

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

        logger.info(
            "Ollama generation completed using model: %s.",
            self.model,
        )

        return generated_text

    def check_connection(self) -> bool:
        """
        Check whether the configured Ollama model is available.
        """

        request = Request(
            url=f"{self.base_url}/api/tags",
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=10,
            ) as response:

                response_data = json.loads(
                    response.read().decode("utf-8")
                )

            available_models = [
                item.get("name")
                for item in response_data.get("models", [])
            ]

            return self.model in available_models

        except (
            HTTPError,
            URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:

            logger.error(
                "Ollama connection check failed: %s",
                error,
            )

            return False
