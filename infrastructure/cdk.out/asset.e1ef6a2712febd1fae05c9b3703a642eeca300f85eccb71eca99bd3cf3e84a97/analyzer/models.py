"""
document-analyzer 도메인 모델
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScheduleItem:
    date: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"date": self.date, "description": self.description}


@dataclass
class AnalyzeResult:
    summary: str
    materials: list[str]
    schedule: list[ScheduleItem]
    importance: str  # HIGH | MEDIUM | LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary":    self.summary,
            "materials":  self.materials,
            "schedule":   [s.to_dict() for s in self.schedule],
            "importance": self.importance,
        }


@dataclass
class TranslatedResult:
    translation: str
    culturalTip: str
    checklistItems: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "translation":    self.translation,
            "culturalTip":    self.culturalTip,
            "checklistItems": self.checklistItems,
        }


SUPPORTED_IMAGE_TYPES: dict[str, str] = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
}
SUPPORTED_TYPES = set(SUPPORTED_IMAGE_TYPES.keys()) | {"pdf"}
MAX_FILE_BYTES  = 10 * 1024 * 1024  # 10 MB

LANGUAGE_NAMES: dict[str, str] = {
    "vi":    "Tiếng Việt",
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en":    "English",
    "ja":    "日本語",
    "th":    "ภาษาไทย",
    "mn":    "Монгол",
    "tl":    "Filipino",
}
