#!/usr/bin/env python3
"""一鍵啟動 Chairman Desktop（Command Center）。"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import os
import webbrowser
from pathlib import Path


def _get_lan_ip() -> str:
    """偵測本機在區域網路中的 IP（非 loopback）。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # 不實際發送封包，僅取得路由界面
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _python_executable() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    venv_python = repo_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable or "python3"


def _load_dotenv(repo_root: Path) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]
    except Exception:
        return
    for name in (".env.local", ".env"):
        load_dotenv(repo_root / name, override=False)


def _wait_for_server(host: str, port: int, timeout: int = 20) -> bool:
    # 健康檢查一律先用 127.0.0.1（本地 loopback）
    check_host = "127.0.0.1"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((check_host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    _load_dotenv(repo_root)

    parser = argparse.ArgumentParser(description="啟動 Chairman Desktop（Command Center）")
    parser.add_argument("--host", default="127.0.0.1", help="綁定主機（預設：127.0.0.1，跨裝置建議 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8765, help="綁定埠號（預設：8765）")
    args = parser.parse_args()

    host = args.host
    port = args.port
    python = _python_executable()
    cmd = [python, "-m", "hermes_os.command_center.api", "--host", host, "--port", str(port)]

    print(f"啟動 Command Center API：{cmd}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env={**os.environ, "PYTHONPATH": str(repo_root / "src")},
    )
    try:
        if not _wait_for_server(host, port):
            print("後端服務啟動逾時，請手動查看錯誤訊息。")
            return 1

        localhost_url = f"http://127.0.0.1:{port}/"
        print(f"本機存取：{localhost_url}")

        if host != "127.0.0.1":
            lan_ip = _get_lan_ip()
            lan_url = f"http://{lan_ip}:{port}/"
            print(f"同網路存取：{lan_url}")
            print("")
            print("安全提示：")
            print("  - 僅限同一 Wi-Fi / 區域網路內裝置存取")
            print("  - 請勿將本服務暴露到公網或未經授權的網路")
            if host == "0.0.0.0":
                print("  - 目前綁定 0.0.0.0，所有網路介面皆可存取")
        else:
            print("")
            print("提示：如需跨裝置存取，請加上 --host 0.0.0.0（仍需同一 Wi-Fi）")

        print("")
        print("在瀏覽器開啟連結即可使用 Chairman Desktop。")
        print("按 Ctrl+C 可停止服務。")
        webbrowser.open(localhost_url)
        proc.wait()
        return proc.returncode
    except KeyboardInterrupt:
        print("\n收到中斷訊號，正在關閉服務...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


if __name__ == "__main__":
    sys.exit(main())
