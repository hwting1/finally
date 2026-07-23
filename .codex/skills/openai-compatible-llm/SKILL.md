---
name: openai-compatible-llm
description: Use this to write code that calls an LLM through the OpenAI Python SDK with configurable base_url, api_key, and model for OpenAI-compatible providers
---

# Calling an LLM with the OpenAI SDK

Use the OpenAI Python SDK directly for LLM calls. Configure the client from environment-backed settings so makers can switch OpenAI-compatible providers by changing `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`, without editing application code.

## Setup

The `.env` file should provide:

```bash
LLM_API_KEY=your-llm-provider-api-key-here
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-3-flash
```

`LLM_BASE_URL` defaults to the Google Gemini OpenAI-compatible endpoint. If it is empty or unset, pass `None` so the OpenAI SDK uses its default base URL.

The uv project must include `openai` and `pydantic`.

```bash
uv add openai pydantic
```

## Client configuration

Keep provider settings centralized in the backend configuration module. Application services should receive the configured client and model rather than hard-coding provider details.

```python
from openai import OpenAI

client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url or None,
)
model = settings.llm_model
```

## Text response

```python
response = client.responses.create(
    model=model,
    input=messages,
)
result = response.output_text
```

## Structured Outputs response

Use a Pydantic model for structured output parsing when the application needs a validated JSON object.

```python
response = client.responses.parse(
    model=model,
    input=messages,
    text_format=MyBaseModelSubclass,
)
result_as_object = response.output_parsed
```

## Provider switching

To switch providers, update `.env` only:

- `LLM_API_KEY`: provider API key
- `LLM_BASE_URL`: OpenAI-compatible endpoint base URL; defaults to `https://generativelanguage.googleapis.com/v1beta/openai/` for Gemini
- `LLM_MODEL`: provider model name; defaults to `gemini-3-flash`

Do not add provider-specific routing, hard-coded model constants, or SDK wrappers unless the project plan explicitly asks for them.
