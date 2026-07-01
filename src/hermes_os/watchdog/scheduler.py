"""Hermes OS Watchdog — WatchdogScheduler：背景排程周期性 scan。"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Callable, Optional

from hermes_os.watchdog.collector import StatusCollector
from hermes_os.watchdog.detector import StagnationDetector, STAGNATION_RULES
from hermes_os.watchdog.schemas import TaskState
from hermes_os.watchdog.storage import WatchdogStorage


class WatchdogScheduler:
    """可配置 interval 的背景 scan 輪詢器。

    第一版不自動啟動，必須由 CLI 顯式 run_once() 或 start() 才啟動。
    """

    def __init__(
        self,
        storage: WatchdogStorage,
        collector: Optional[StatusCollector] = None,
        detector: Optional[StagnationDetector] = None,
        interval_minutes: int = 15,
    ) -> None:
        self._storage = storage
        self._collector = collector or StatusCollector()
        self._detector = detector or StagnationDetector()
        self._interval_seconds = max(1, interval_minutes) * 60
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _tick(self, now: datetime) -> None:
        states = self._collector.collect()
        stagnant = self._detector.scan(states, now)
        for state in stagnant:
            # 持久化更新 consecutive_idle_checks
            self._storage.upsert_task_state(state)

    def run_once(self, now: Optional[datetime] = None) -> int:
        """手動執行單輪 scan，回傳被標記為 stagnant 的任務數。"""
        now = now or datetime.utcnow()
        self._tick(now)
        return len(self._detector.scan(self._collector.collect(), now))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.is_set():
                try:
                    self.run_once()
                except Exception:
                    pass
                # 等待時分段 sleep，以便快速停止
                self._stop_event.wait(self._interval_seconds)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._interval_seconds + 1)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def interval_seconds(self) -> int:
        return self._interval_seconds
