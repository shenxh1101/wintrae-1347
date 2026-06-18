from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class Config:
    template: str = "{date}_{class}_{student}_{piece}{comment}{ext}"
    output_dir: Optional[str] = None
    ignore_patterns: list[str] = field(default_factory=lambda: [
        r"^\.", r"__MACOSX", r"Thumbs\.db", r"desktop\.ini",
    ])
    class_names: list[str] = field(default_factory=list)
    min_duration_seconds: float = 10.0
    organize_by_class: bool = True
    organize_by_student: bool = True

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        config = cls()
        if path and Path(path).exists():
            config._apply_file(Path(path))
        return config

    def _apply_file(self, path: Path) -> None:
        if not HAS_YAML:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return

        if "template" in data:
            self.template = str(data["template"])
        if "output_dir" in data:
            self.output_dir = str(data["output_dir"])
        if "ignore_patterns" in data and isinstance(data["ignore_patterns"], list):
            self.ignore_patterns = [str(p) for p in data["ignore_patterns"]]
        if "class_names" in data and isinstance(data["class_names"], list):
            self.class_names = [str(c) for c in data["class_names"]]
        if "min_duration_seconds" in data:
            self.min_duration_seconds = float(data["min_duration_seconds"])
        if "organize_by_class" in data:
            self.organize_by_class = bool(data["organize_by_class"])
        if "organize_by_student" in data:
            self.organize_by_student = bool(data["organize_by_student"])
