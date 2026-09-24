"""
Thin LLM wrapper. Every agent calls chat() or chat_json(); nothing else in
the project knows which provider is behind it. Swapping Grok for Ollama later
(as in the PPT architecture) only means changing this file / .env, because
Ollama also serves an OpenAI-compatible API at http://localhost:11434/v1.
"""
import json
import os
import re

from openai import OpenAI

import config

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        provider = config.PROVIDERS.get(config.LLM_PROVIDER)
        if provider is None:
            raise ValueError(f"Unknown LLM_PROVIDER '{config.LLM_PROVIDER}'. "
                             f"Use one of {list(config.PROVIDERS)}")
        api_key = os.getenv(provider["key_env"])
        if not api_key:
            raise RuntimeError(f"Set {provider['key_env']} in your .env file")
        _client = OpenAI(api_key=api_key, base_url=provider["base_url"],
                         timeout=config.LLM_TIMEOUT)
    return _client


def chat(system: str, user: str, *, json_mode: bool = False,
         temperature: float | None = None) -> str:
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = get_client().chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=config.LLM_TEMPERATURE if temperature is None else temperature,
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in ```json fences or added prose."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def chat_json(system: str, user: str) -> dict:
    """Ask for a JSON object. Falls back to plain mode if the model/provider
    rejects response_format, and retries once on unparseable output."""
    last_err = None
    for use_json_mode in (True, False):
        try:
            return extract_json(chat(system, user, json_mode=use_json_mode))
        except Exception as e:  # noqa: BLE001 - provider errors vary
            last_err = e
    raise RuntimeError(f"LLM did not return valid JSON: {last_err}")
