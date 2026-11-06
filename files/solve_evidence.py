"""Summarize HFSS text exports without claiming they belong to a new solve.

Only the English native single-frequency Max Mag. Delta S format is recognized.
Other convergence criteria and localized formats remain inconclusive.  This is
an artifact summary, not a job tracker or a replacement for the original files.
"""
from __future__ import annotations

import math
import re
from typing import Any


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def summarize_hfss_profile(content: str) -> dict[str, Any]:
    statuses = re.findall(r"\bStatus\s*:\s*([^\r\n]+)", content, re.IGNORECASE)
    status = statuses[-1].strip() if statuses else None
    return {
        "format": "hfss_profile_text",
        "last_reported_status": status,
        "normal_completion_reported": (
            status.casefold() == "normal completion" if status is not None else None
        ),
        "latest_submission_linked": False,
    }


def summarize_hfss_convergence(content: str) -> dict[str, Any]:
    def capture(pattern: str) -> str | None:
        values = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
        return values[-1].strip() if values else None

    summary: dict[str, Any] = {
        "format": "hfss_single_frequency_delta_s_text",
        "setup_name": capture(r"^\s*Setup\s*:\s*([^\r\n]+)$"),
        "criterion": capture(r"^\s*Criterion\s*:\s*([^\r\n]+)$"),
        "native_converged": None,
        "target_delta_s": None,
        "required_consecutive_passes": None,
        "reported_consecutive_passes": None,
        "computed_consecutive_passes": None,
        "assessment": "inconclusive",
        "latest_submission_linked": False,
    }
    native = capture(r"^\s*Converged\s*:\s*(Yes|No)\s*$")
    if native is not None:
        summary["native_converged"] = native.casefold() == "yes"
    criterion = summary["criterion"]
    if criterion is None or re.sub(r"\s+", " ", criterion).casefold() != "max mag. delta s":
        return summary
    target = capture(rf"^\s*Target\s*:\s*({_NUMBER})\s*$")
    consecutive = capture(r"^\s*Target Consecutive Passes\s*:\s*(\d+)\s*$")
    completed = capture(r"^\s*Completed\s*:\s*(\d+)\s*$")
    reported = capture(r"^\s*Current Consecutive Passes\s*:\s*(\d+)\s*$")
    if target is None or consecutive is None or completed is None or reported is None:
        return summary
    threshold = float(target)
    required = int(consecutive)
    if not math.isfinite(threshold) or threshold <= 0 or required < 1:
        return summary
    summary.update(target_delta_s=threshold, required_consecutive_passes=required,
                   reported_consecutive_passes=int(reported))
    rows = []
    for line in content.splitlines():
        match = re.fullmatch(rf"\s*(\d+)\s*\|\s*\d+\s*\|\s*(N/A|{_NUMBER})\s*\|\s*", line, re.IGNORECASE)
        if match:
            delta = None if match[2].casefold() == "n/a" else float(match[2])
            rows.append((int(match[1]), delta))
    if (
        not rows
        or len(rows) != int(completed)
        or any(number != expected for expected, (number, _) in enumerate(rows, 1))
        or any(delta is not None and (not math.isfinite(delta) or delta < 0) for _, delta in rows)
    ):
        return summary
    count = 0
    for _, delta in reversed(rows):
        if delta is None or delta > threshold:
            break
        count += 1
    summary["computed_consecutive_passes"] = count
    if summary["native_converged"] is False or count < required or int(reported) < required:
        summary["assessment"] = "not_converged"
    elif summary["native_converged"] is True:
        summary["assessment"] = "converged"
    return summary
