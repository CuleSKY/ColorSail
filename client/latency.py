from __future__ import annotations

import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from statistics import median
from typing import Optional, Tuple


A2S_INFO_PAYLOAD = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"


@dataclass
class ProbeResult:
    ok: bool
    rtt_ms: Optional[float]
    error: Optional[str] = None


@dataclass
class A2SInfoResult(ProbeResult):
    players: Optional[int] = None
    max_players: Optional[int] = None


@dataclass
class DisplayChoice:
    source: str
    rtt_ms: Optional[float]


PING_TIME_REGEX = re.compile(r"(?:time|时间)[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
PING_AVG_REGEX = re.compile(r"(?:Average|平均)\s*=\s*(\d+)ms", re.IGNORECASE)


def _parse_ping_output(output: str) -> Optional[float]:
    match = PING_TIME_REGEX.search(output)
    if match:
        return float(match.group(1))
    match = PING_AVG_REGEX.search(output)
    if match:
        return float(match.group(1))
    return None


def ping_icmp(host: str, timeout: float = 1.0) -> ProbeResult:
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(int(timeout)), host]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout + 1)
        rtt = _parse_ping_output(output)
        if rtt is None:
            return ProbeResult(ok=False, rtt_ms=None, error="parse_failed")
        return ProbeResult(ok=True, rtt_ms=rtt)
    except subprocess.TimeoutExpired:
        return ProbeResult(ok=False, rtt_ms=None, error="timeout")
    except subprocess.CalledProcessError as exc:
        rtt = _parse_ping_output(exc.output or "")
        if rtt is not None:
            return ProbeResult(ok=True, rtt_ms=rtt)
        return ProbeResult(ok=False, rtt_ms=None, error="unreachable")
    except FileNotFoundError:
        return ProbeResult(ok=False, rtt_ms=None, error="ping_unavailable")


def _read_null_terminated(data: bytes, offset: int) -> Tuple[str, int]:
    end = data.find(b"\x00", offset)
    if end == -1:
        raise ValueError("missing terminator")
    return data[offset:end].decode("utf-8", errors="replace"), end + 1


def a2s_info(ip: str, port: int, timeout: float = 1.0) -> A2SInfoResult:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        start = time.monotonic()
        server_addr = (ip, port)

        def _send_and_recv(payload: bytes) -> bytes:
            for attempt in range(2):
                sock.sendto(payload, server_addr)
                try:
                    data, _ = sock.recvfrom(4096)
                    return data
                except socket.timeout:
                    if attempt == 1:
                        raise
            raise socket.timeout

        data = _send_and_recv(A2S_INFO_PAYLOAD)
        if len(data) < 5:
            return A2SInfoResult(ok=False, rtt_ms=None, error="invalid_response")
        if data[4] == 0x41:
            if len(data) < 9:
                return A2SInfoResult(ok=False, rtt_ms=None, error="invalid_response")
            challenge_token = data[5:9]
            data = _send_and_recv(A2S_INFO_PAYLOAD + challenge_token)
        if len(data) < 5 or data[4] != 0x49:
            return A2SInfoResult(ok=False, rtt_ms=None, error="invalid_response")
        rtt_ms = (time.monotonic() - start) * 1000
        offset = 5
        _, offset = _read_null_terminated(data, offset)  # server name
        _, offset = _read_null_terminated(data, offset)  # map
        _, offset = _read_null_terminated(data, offset)  # folder
        _, offset = _read_null_terminated(data, offset)  # game
        if offset + 2 > len(data):
            return A2SInfoResult(ok=False, rtt_ms=None, error="short_response")
        offset += 2  # app id
        if offset + 2 > len(data):
            return A2SInfoResult(ok=False, rtt_ms=None, error="short_response")
        players = data[offset]
        max_players = data[offset + 1]
        return A2SInfoResult(ok=True, rtt_ms=rtt_ms, players=players, max_players=max_players)
    except socket.timeout:
        return A2SInfoResult(ok=False, rtt_ms=None, error="timeout")
    except Exception as exc:
        return A2SInfoResult(ok=False, rtt_ms=None, error=str(exc))
    finally:
        sock.close()


def choose_display(icmp: ProbeResult, a2s: ProbeResult, last_choice: DisplayChoice | None, last_change_at: float | None) -> DisplayChoice:
    now = time.monotonic()
    if last_choice and last_change_at and now - last_change_at < 10:
        if last_choice.source == "icmp" and icmp.ok:
            return DisplayChoice(source="icmp", rtt_ms=icmp.rtt_ms)
        if last_choice.source == "a2s" and a2s.ok:
            return DisplayChoice(source="a2s", rtt_ms=a2s.rtt_ms)
    if icmp.ok:
        return DisplayChoice(source="icmp", rtt_ms=icmp.rtt_ms)
    if a2s.ok:
        return DisplayChoice(source="a2s", rtt_ms=a2s.rtt_ms)
    return DisplayChoice(source="timeout", rtt_ms=None)


def median_rtt(samples: list[float]) -> Optional[float]:
    if not samples:
        return None
    return float(median(samples))
