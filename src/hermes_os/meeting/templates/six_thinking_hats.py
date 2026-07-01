"""Six Thinking Hats meeting template."""

from __future__ import annotations

from hermes_os.meeting.models import HatTask, HatRole, MeetingTemplate


def build_topic_prompt(topic: str) -> str:
    return f"本次會議主題：{topic}。"


def six_thinking_hats(topic: str) -> MeetingTemplate:
    base = build_topic_prompt(topic)
    return MeetingTemplate(
        name="six_thinking_hats",
        allow_parallel=False,
        hats=[
            HatTask(
                role=HatRole.WHITE,
                prompt=f"{base}請只陳述與「{topic}」相關的客觀事實、數據與已知資訊。",
            ),
            HatTask(
                role=HatRole.YELLOW,
                prompt=f"{base}請只列出與「{topic}」相關的機會、價值與樂觀判斷。",
            ),
            HatTask(
                role=HatRole.RED,
                prompt=f"{base}請只表達與「{topic}」相關的直覺感受與風險預感。",
            ),
            HatTask(
                role=HatRole.BLACK,
                prompt=f"{base}請只列出與「{topic}」相關的風險、障礙與代價。",
            ),
            HatTask(
                role=HatRole.GREEN,
                prompt=f"{base}請只提出與「{topic}」相關的新點子、替代方案與突破方向。",
            ),
        ],
        chairman_prompt=(
            f"{base}請根據白帽、黃帽、紅帽、黑帽、綠帽的意見，"
            "整理出一段可執行的最終結論，並標註優先順序與必要條件。"
        ),
    )
