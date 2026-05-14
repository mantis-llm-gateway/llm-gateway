import os

from any_llm import AnyLLM

# we should not import environment variables from .env in production,
# so delete this once it is being used in production.
from dotenv import load_dotenv

load_dotenv()


class ProviderAdaptor:
    def __init__(self):
        self.provider_connections = {}

    def _get_client(self, provider: str) -> None:
        # this key will eventually be pulled from API key management
        # modify this once we are set up to send requests to other providers
        api_key = os.environ.get("OPENAI_API_KEY")

        if self.provider_connections.get(provider):
            pass
        else:
            self.provider_connections[provider] = AnyLLM.create(provider, api_key=api_key)
        return
