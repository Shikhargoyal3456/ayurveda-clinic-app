from __future__ import annotations

from typing import Any


async def call_ai_json_with_retry(
    *,
    system_prompt: str,
    user_prompt: str,
    simpler_user_prompt: str | None = None,
    temperature: float = 0.3,
    max_output_tokens: int = 2048,
) -> tuple[dict[str, Any], str]:
    """
    Lazy wrapper around the provider JSON helper.

    Importing ai_provider at module import time can create circular imports
    for features that also depend on pure_ai_core. This wrapper defers the
    import until the function is actually called.
    """
    from services.ai_provider import call_ai_json_with_retry as _provider_call_ai_json_with_retry

    return await _provider_call_ai_json_with_retry(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        simpler_user_prompt=simpler_user_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
