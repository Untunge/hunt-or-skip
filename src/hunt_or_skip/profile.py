"""Hunter profile: your budget, time and KYC situation, stored locally."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Profile:
    stake_budget_usd: float = 0.0
    hours: float = 8.0
    can_kyc: bool = False
    target: str = "medium"


def profile_path() -> Path:
    return Path.home() / ".hunt-or-skip" / "profile.json"


def load_profile() -> Profile:
    path = profile_path()
    if not path.exists():
        return Profile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Profile()
    known = {k: v for k, v in data.items() if k in Profile.__dataclass_fields__}
    return Profile(**known)


def save_profile(profile: Profile) -> Path:
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")
    return path
