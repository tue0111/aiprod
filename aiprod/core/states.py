"""State machine chung cho mỗi (đơn vị, tầng) và luật cổng duyệt."""
from __future__ import annotations

STATES = [
    "todo",
    "spec_ready",
    "generating",
    "candidates",
    "picked",
    "qa_pass",
    "qa_fail",
    "approved",
    "assembled",
]

# chuyển hợp lệ: trạng thái -> các trạng thái kế tiếp được phép
TRANSITIONS: dict[str, set[str]] = {
    "todo": {"spec_ready"},
    "spec_ready": {"generating", "candidates"},
    "generating": {"candidates", "spec_ready"},
    "candidates": {"picked", "spec_ready"},
    "picked": {"qa_pass", "qa_fail"},
    "qa_pass": {"approved", "qa_fail"},
    "qa_fail": {"spec_ready", "picked"},  # phân tích lỗi rồi viết lại spec, hoặc chọn ứng viên khác
    "approved": {"assembled", "spec_ready"},  # mở lại khi phát hiện lỗi muộn
    "assembled": {"spec_ready"},
}

DONE = {"approved", "assembled"}

# việc kế tiếp cho từng trạng thái (dùng cho `aiprod next`)
NEXT_ACTION = {
    "todo": "sinh thẻ việc (đọc spec + template) → aiprod task {id} {stage}",
    "spec_ready": "giao worker → aiprod submit {id} {stage}",
    "generating": "chờ / lấy kết quả → aiprod collect {id} {stage}",
    "candidates": "chọn ứng viên → aiprod approve {id} {stage} --pick n",
    "picked": "QA → aiprod qa {id} {stage}",
    "qa_pass": "duyệt → aiprod approve {id} {stage}",
    "qa_fail": "phân tích lỗi, sửa spec → aiprod task {id} {stage}",
}


class TransitionError(Exception):
    """Chuyển trạng thái không hợp lệ hoặc bị cổng chặn."""


def check_state(state: str) -> str:
    if state not in STATES:
        raise ValueError(f"trạng thái lạ {state!r}; hợp lệ: {', '.join(STATES)}")
    return state


def can_transition(cur: str, new: str) -> bool:
    return new in TRANSITIONS[check_state(cur)]


def transition(cur: str, new: str) -> str:
    check_state(new)
    if not can_transition(cur, new):
        raise TransitionError(f"không thể chuyển {cur} → {new}")
    return new


def is_done(state: str) -> bool:
    return check_state(state) in DONE
