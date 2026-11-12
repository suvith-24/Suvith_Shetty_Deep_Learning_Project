
from lexisync.generation.ollama_client import OllamaClient


def main() -> None:
    client = OllamaClient()

    print("\nLEXISYNCAI — OLLAMA CLIENT TEST")
    print("=" * 60)

    print("\nChecking Ollama connection...")

    if not client.check_connection():
        raise RuntimeError(
            "Ollama is unavailable or the configured model is missing."
        )

    print("Ollama connection successful.")
    print(f"Model: {client.model}")

    print("\nTesting text generation...")

    response = client.generate(
        prompt=(
            "Explain GDPR in simple language in exactly "
            "three bullet points."
        ),
        system_prompt=(
            "You are a concise legal information assistant. "
            "Do not invent legal provisions."
        ),
    )

    print("\nGenerated response:")
    print("-" * 60)
    print(response)
    print("-" * 60)

    print("\nOllama client test completed successfully.")


if __name__ == "__main__":
    main()
