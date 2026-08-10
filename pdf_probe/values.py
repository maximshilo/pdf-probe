"""Turning raw pypdf/PDF-object-shaped values into safe, displayable data.

Grouped as one class because every stage that touches document metadata,
XMP data, or low-level PDF objects needs the same handful of coercions, and
having a single named dependency (rather than a handful of loose module
functions) makes that dependency explicit and easy to substitute in tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

UTC = timezone.utc


class PdfValueFormatter:
    @classmethod
    def humanize(cls, value: Any) -> Optional[str]:
        """Coerce an arbitrary scalar/collection into a short display string."""
        if value is None:
            return None
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            normalized = " ".join(value.split())
            return normalized or None
        if isinstance(value, dict):
            return cls._humanize_dict(value)
        if isinstance(value, (list, tuple, set)):
            return cls._humanize_sequence(value)
        normalized = " ".join(str(value).split())
        return normalized or None

    @classmethod
    def _humanize_dict(cls, value: dict) -> Optional[str]:
        if not value:
            return None
        if "x-default" in value and len(value) == 1:
            return cls.humanize(value["x-default"])
        parts = []
        for key, item in value.items():
            item_text = cls.humanize(item)
            if item_text:
                parts.append(f"{key}: {item_text}")
        return "; ".join(parts) or None

    @classmethod
    def _humanize_sequence(cls, value: Any) -> Optional[str]:
        parts = [text for text in (cls.humanize(item) for item in value) if text]
        return ", ".join(parts) or None

    @classmethod
    def pick_first(cls, *values: Any) -> Optional[str]:
        """Return the first value that humanizes to something non-empty."""
        for value in values:
            text = cls.humanize(value)
            if text:
                return text
        return None

    @classmethod
    def format_date(cls, value: Any) -> Optional[str]:
        """Parse a PDF date string (``D:YYYYMMDDHHmmSS+HH'mm``) to ISO 8601."""
        text = cls.humanize(value)
        if not text or not text.startswith("D:"):
            return text

        body = text[2:]
        main_digits = "".join(char for char in body[:14] if char.isdigit()).ljust(14, "0")
        try:
            parsed = datetime.strptime(main_digits, "%Y%m%d%H%M%S")
        except ValueError:
            return text

        tz_part = body[14:]
        if not tz_part:
            return parsed.isoformat()
        if tz_part.startswith("Z"):
            return parsed.replace(tzinfo=UTC).isoformat()
        if tz_part[0] in "+-":
            sign = 1 if tz_part[0] == "+" else -1
            digits = "".join(char for char in tz_part[1:] if char.isdigit())
            hours = int(digits[:2]) if len(digits) >= 2 else 0
            minutes = int(digits[2:4]) if len(digits) >= 4 else 0
            offset = timedelta(hours=hours, minutes=minutes) * sign
            return parsed.replace(tzinfo=timezone(offset)).isoformat()
        return parsed.isoformat()

    @staticmethod
    def get_mapping_value(mapping: Optional[dict], *keys: str) -> Any:
        if not isinstance(mapping, dict):
            return None
        for key in keys:
            if key in mapping:
                return mapping[key]
        return None

    @staticmethod
    def count_entries(value: Any) -> int:
        if value is None:
            return 0
        try:
            return len(value)
        except Exception:
            return 1

    @classmethod
    def decode_bytes(cls, value: bytes) -> dict:
        text = None
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                text = value.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        return {
            "type": "bytes",
            "length": len(value),
            "hex": value.hex(),
            "text": text,
        }

    @classmethod
    def normalize(
        cls,
        value: Any,
        depth: int = 0,
        seen: Optional[set] = None,
        _skip_wrap: bool = False,
    ) -> Any:
        """Recursively turn a pypdf object graph into plain JSON-able data."""
        if seen is None:
            seen = set()
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, bytes):
            return cls.decode_bytes(value)
        if depth > 12:
            return "<max-depth-reached>"

        value_id = id(value)
        if value_id in seen:
            return "<already-shown-elsewhere>"

        # Indirect references are unwrapped to show what they point to, not a
        # step deeper into the document, so unwrapping is depth-neutral -
        # only actually descending into a container's children below counts
        # against `depth`. Otherwise every reference (nearly every object in
        # a real PDF) would burn budget for one real level of nesting.
        # `_skip_wrap` stops the object we just resolved from being wrapped a
        # second time for the same back-reference it was just unwrapped from.
        if not _skip_wrap:
            if value.__class__.__name__ == "IndirectObject":
                try:
                    resolved = value.get_object()
                except Exception as exc:  # pragma: no cover - defensive path
                    return {"reference": repr(value), "error": str(exc)}
                return {
                    "reference": repr(value),
                    "value": cls.normalize(resolved, depth, seen, _skip_wrap=True),
                }

            reference = getattr(value, "indirect_reference", None)
            if reference is not None:
                return {
                    "reference": str(reference),
                    "value": cls.normalize(value, depth, seen, _skip_wrap=True),
                }

        # Marked in place (not copied) so that once an object has been fully
        # expanded anywhere in the traversal, every other path that reaches
        # it - not just a path back through its own ancestors - short-
        # circuits instead of re-expanding it. PDFs share structure heavily
        # (a font or resource dict is typically referenced by every page
        # that uses it), and per-path tracking alone lets that sharing blow
        # traversal up combinatorially across a large page tree.
        seen.add(value_id)

        if hasattr(value, "keys"):
            return {str(key): cls.normalize(item, depth + 1, seen) for key, item in value.items()}

        if isinstance(value, (list, tuple, set)):
            return [cls.normalize(item, depth + 1, seen) for item in value]

        if hasattr(value, "items"):
            return {str(key): cls.normalize(item, depth + 1, seen) for key, item in value.items()}

        if hasattr(value, "__iter__") and value.__class__.__name__ not in {"str", "bytes"}:
            try:
                return [cls.normalize(item, depth + 1, seen) for item in value]
            except TypeError:
                pass

        return repr(value)
