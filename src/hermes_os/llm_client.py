"""Minimal LLM client for Hermes OS executor.

Env:
- HERMES_LLM_PROVIDER: openai | openai_compatible (default: openai_compatible)
- HERMES_LLM_BASE_URL: base URL (default: https://api.openai.com/v1)
- HERMES_LLM_API_KEY: API key
- HERMES_LLM_MODEL: model name (default: gpt-4o-mini)
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.getenv("HERMES_LLM_PROVIDER", "openai_compatible")
        self.base_url = os.getenv("HERMES_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("HERMES_LLM_API_KEY", "")
        self.model = os.getenv("HERMES_LLM_MODEL", "gpt-4o-mini")
        self.enabled = bool(self.api_key)

    def complete(self, prompt: str, *, model: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.provider,
                "model": model or self.model,
                "enabled": False,
                "text": "",
                "error": "LLM 未設定：請設定 HERMES_LLM_API_KEY",
            }
        try:
            import urllib.request
            import urllib.error
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.provider, "model": model or self.model, "enabled": True, "text": "", "error": str(exc)}

        url = f"{self.base_url}/chat/completions"
        payload = json.dumps({
            "model": model or self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 1024),
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
            return {
                "provider": self.provider,
                "model": model or self.model,
                "enabled": True,
                "text": "",
                "error": f"HTTP {exc.code}: {body or exc.reason}",
            }
        except Exception as exc:  # noqa: BLE001
            return {"provider": self.provider, "model": model or self.model, "enabled": True, "text": "", "error": str(exc)}

        text = ""
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except Exception:  # noqa: BLE001
            text = json.dumps(data, ensure_ascii=False)
        return {
            "provider": self.provider,
            "model": model or self.model,
            "enabled": True,
            "text": text,
            "raw": data,
        }
