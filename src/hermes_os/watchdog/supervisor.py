"""Hermes OS Watchdog — GPTDecisionCore：呼叫 LLM 取得停滯任務決策。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from hermes_os.watchdog.schemas import (
    AuditRecord,
    TaskState,
    WatchdogDecision,
    WatchdogDecisionType,
)
from hermes_os.watchdog.storage import WatchdogStorage

# GPT Supervisor system prompt（鐵則版）
SYSTEM_PROMPT = """\
你是一個軟體開發任務監控主管。你只會接收到單一開發任務的結構化狀態摘要。
你的職責是：判斷該任務是否停滯，並輸出具體、可執行的下一步指令。

鐵則：
- 只在任務真正停滯時建議推進動作
- 禁止要求刪除資料、重建狀態、或跳過測試
- 所有建議必須是單一最小動作
- 若判斷不清，選擇 escalate
"""

USER_PROMPT_TEMPLATE = """\
任務 ID：{task_id}
專案：{project}
目前狀態：{status}
最後活動：{last_activity_ts}
最後使用者回覆：{last_user_reply_ts}
連續閒置檢查次數：{consecutive_idle_checks}
目前執行中動作：{current_action}
錯誤摘要：{error_summary}
阻塞事項：{blockers}

請輸出 JSON，不要輸出 Markdown：
{{
  "decision": "proceed | escalate | pause | terminate | reassign_context",
  "reason": "一行中文結論",
  "action_plan": ["步驟 1", "步驟 2", "步驟 3"],
  "risk": "潛在風險描述",
  "next_check": "ISO8601 時間或 null",
  "requires_human": true | false
}}
"""

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": [
                "proceed",
                "escalate",
                "pause",
                "terminate",
                "reassign_context",
            ],
        },
        "reason": {"type": "string"},
        "action_plan": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "risk": {"type": "string"},
        "next_check": {"type": "string"},
        "requires_human": {"type": "boolean"},
    },
    "required": ["decision", "reason", "action_plan", "risk", "requires_human"],
}


class GPTDecisionError(Exception):
    """LLM 決策階段 persistent failure。"""


class GPTDecisionCore:
    """封裝 OpenAI-compatible client 呼叫串接。"""

    def __init__(
        self,
        storage: WatchdogStorage,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_retries: int = 3,
    ) -> None:
        self._storage = storage
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        # 第一版：import-light，若無 client 則在 decide 時再嘗試_config

    def _client(self):  # type: ignore[return]
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise GPTDecisionError("openai package not installed") from exc
        return OpenAI()

    def _build_messages(
        self, state: TaskState
    ) -> tuple[dict[str, str], dict[str, str]]:
        last_reply = (
            state.last_user_reply_ts.isoformat()
            if state.last_user_reply_ts
            else "無"
        )
        user_prompt = USER_PROMPT_TEMPLATE.format(
            task_id=state.task_id,
            project=state.project,
            status=state.status,
            last_activity_ts=state.last_activity_ts.isoformat(),
            last_user_reply_ts=last_reply,
            consecutive_idle_checks=state.consecutive_idle_checks,
            current_action=state.current_action or "無",
            error_summary=state.error_summary or "無",
            blockers="、".join(state.blockers) if state.blockers else "無",
        )
        return {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }, {
            "role": "user",
            "content": user_prompt,
        }

    def decide(self, state: TaskState, now: datetime | None = None) -> WatchdogDecision:
        """對單一 stagnant state 呼叫 LLM 並回傳 WatchdogDecision。"""
        system_msg, user_msg = self._build_messages(state)
        client = self._client()
        last_err: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                completion = client.chat.completions.create(  # type: ignore[arg-type]
                    model=self._model,
                    temperature=self._temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "watchdog_decision",
                            "schema": DECISION_SCHEMA,
                            "strict": True,
                        },
                    },
                    messages=[system_msg, user_msg],  # type: ignore[arg-type]
                )
                content = completion.choices[0].message.content or "{}"
                parsed = json.loads(content)
                return WatchdogDecision(
                    task_id=state.task_id,
                    decision=WatchdogDecisionType(parsed["decision"]),
                    reason=str(parsed["reason"]),
                    action_plan=list(parsed["action_plan"])[:3],
                    risk=str(parsed["risk"]),
                    next_check=(
                        datetime.fromisoformat(parsed["next_check"])
                        if parsed.get("next_check")
                        else None
                    ),
                    requires_human=bool(parsed.get("requires_human", False)),
                )
            except (json.JSONDecodeError, KeyError, ValueError, Exception) as exc:  # noqa: BLE001
                last_err = exc
                continue

        raise GPTDecisionError(
            f"LLM decision failed after {self._max_retries} retries for "
            f"task {state.task_id}: {last_err}"
        )

    def decide_and_audit(self, state: TaskState) -> tuple[WatchdogDecision, AuditRecord]:
        now = datetime.utcnow()
        decision = self.decide(state, now)
        record = AuditRecord(
            ts=now,
            task_id=state.task_id,
            trigger="gpt_decision",
            state_snapshot=state,
            decision=decision,
            result="success",
        )
        return decision, record
