#!/usr/bin/env python3

"""Generate Markdown reports from a PDF with extracted text and metadata.

Requirements
------------
The Python dependency for this script should be listed in requirements.txt as:

    pypdf>=6.11.0

Optional system tools can enrich the report when they are installed and available
on PATH:

    pdfinfo
    pdftotext
    qpdf

Usage
-----
Run the script with the PDF path as the required positional argument. By default,
it writes a slim, human-readable report beside the PDF using the same base name
and an .md suffix. Use --full to emit the exhaustive raw report.

Examples:

    python3 -m pdf_probe input.pdf
    python3 -m pdf_probe input.pdf --full
    python3 -m pdf_probe input.pdf -o report.md
    python3 -m pdf_probe protected.pdf --password secret
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from pypdf import PdfReader

UTC = timezone.utc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract PDF metadata and text and write either a slim human-readable "
            "report or an exhaustive full report in Markdown."
        )
    )
    parser.add_argument("pdf", help="Path to the source PDF file")
    parser.add_argument(
        "-o",
        "--output",
        help="Path to the output Markdown file (defaults to <pdf>.md)",
    )
    parser.add_argument(
        "--password",
        default="",
        help="Password for encrypted PDFs, if needed",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Write the exhaustive full report instead of the default slim report",
    )
    return parser.parse_args()


def markdown_code_block(content: str | None, language: str = "") -> str:
    if content is None:
        content = ""
    fence = "```"
    while fence in content:
        fence += "`"
    if language:
        return f"{fence}{language}\n{content.rstrip()}\n{fence}"
    return f"{fence}\n{content.rstrip()}\n{fence}"


def markdown_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("`", "\\`")


def humanize_scalar(value: Any) -> str | None:
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
        if not value:
            return None
        if "x-default" in value and len(value) == 1:
            return humanize_scalar(value["x-default"])
        parts = []
        for key, item in value.items():
            item_text = humanize_scalar(item)
            if item_text:
                parts.append(f"{key}: {item_text}")
        return "; ".join(parts) or None
    if isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            item_text = humanize_scalar(item)
            if item_text:
                parts.append(item_text)
        return ", ".join(parts) or None
    normalized = " ".join(str(value).split())
    return normalized or None


def pick_first_value(*values: Any) -> str | None:
    for value in values:
        text = humanize_scalar(value)
        if text:
            return text
    return None


def format_pdf_date(value: Any) -> str | None:
    text = humanize_scalar(value)
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


def isoformat_timestamp(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def get_mapping_value(mapping: dict[str, Any] | None, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def count_entries(value: Any) -> int:
    if value is None:
        return 0
    try:
        return len(value)
    except Exception:
        return 1


def parse_pdfinfo_output(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def build_bullet_section(
    title: str,
    items: Sequence[tuple[str, str | None]],
    empty_message: str,
) -> list[str]:
    lines = [f"## {title}", ""]
    rendered = [f"- {label}: {value}" for label, value in items if value]
    if rendered:
        lines.extend(rendered)
    else:
        lines.append(empty_message)
    lines.append("")
    return lines


def build_list_section(title: str, items: list[str], empty_message: str) -> list[str]:
    lines = [f"## {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append(empty_message)
    lines.append("")
    return lines


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_bytes(value: bytes) -> dict[str, Any]:
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


def normalize_pdf_value(value: Any, depth: int = 0, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()
    if depth > 8:
        return "<max-depth-reached>"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return decode_bytes(value)

    value_id = id(value)
    if value_id in seen:
        return "<recursive-reference>"

    next_seen = set(seen)
    next_seen.add(value_id)

    if hasattr(value, "indirect_reference"):
        reference = getattr(value, "indirect_reference", None)
        if reference is not None:
            return {
                "reference": str(reference),
                "value": (
                    normalize_pdf_value(dict(value), depth + 1, next_seen)
                    if hasattr(value, "keys")
                    else repr(value)
                ),
            }

    if hasattr(value, "get_object") and value.__class__.__name__ == "IndirectObject":
        try:
            resolved = value.get_object()
        except Exception as exc:  # pragma: no cover - defensive path
            return {"reference": repr(value), "error": str(exc)}
        return {
            "reference": repr(value),
            "value": normalize_pdf_value(resolved, depth + 1, next_seen),
        }

    if hasattr(value, "keys"):
        items: dict[str, Any] = {}
        for key, item in value.items():
            items[str(key)] = normalize_pdf_value(item, depth + 1, next_seen)
        return items

    if isinstance(value, (list, tuple, set)):
        return [normalize_pdf_value(item, depth + 1, next_seen) for item in value]

    if hasattr(value, "items"):
        return {
            str(key): normalize_pdf_value(item, depth + 1, next_seen) for key, item in value.items()
        }

    if hasattr(value, "__iter__") and value.__class__.__name__ not in {"str", "bytes"}:
        try:
            return [normalize_pdf_value(item, depth + 1, next_seen) for item in value]
        except TypeError:
            pass

    return repr(value)


def run_command(command: list[str]) -> dict[str, Any]:
    tool = shutil.which(command[0])
    if tool is None:
        return {"available": False, "command": command}
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "available": True,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def split_pdftotext_output(text: str) -> list[str]:
    pages = text.split("\f")
    while pages and not pages[-1].strip():
        pages.pop()
    return pages or [text]


def build_text_content_markdown(page_texts: list[dict[str, Any]]) -> str:
    if not page_texts:
        return "_No text extracted from the PDF._"
    if all(item.get("page_number") is not None for item in page_texts):
        rendered_pages = []
        for item in page_texts:
            page_text = (item.get("text") or "").strip()
            rendered_pages.append(
                f"### Page {item['page_number']}\n\n"
                f"{page_text or '_No text extracted on this page._'}"
            )
        return "\n\n".join(rendered_pages)
    text = "\n\n".join((item.get("text") or "").strip() for item in page_texts).strip()
    return text or "_No text extracted from the PDF._"


def flatten_outline(items: list[Any], depth: int = 0) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, list):
            flattened.extend(flatten_outline(item, depth + 1))
            continue
        entry: dict[str, Any] = {"depth": depth}
        for attribute in ("title", "page", "color", "bold", "italic"):
            if hasattr(item, attribute):
                entry[attribute] = normalize_pdf_value(getattr(item, attribute))
        if not entry.keys() - {"depth"}:
            entry["value"] = repr(item)
        flattened.append(entry)
    return flattened


def extract_xmp_metadata(reader: PdfReader) -> dict[str, Any] | None:
    xmp = reader.xmp_metadata
    if xmp is None:
        return None

    data: dict[str, Any] = {}
    for name in dir(xmp):
        if name.startswith("_"):
            continue
        try:
            value = getattr(xmp, name)
        except Exception as exc:  # pragma: no cover - defensive path
            data[name] = {"error": str(exc)}
            continue
        if callable(value):
            continue
        data[name] = normalize_pdf_value(value)
    return data


def extract_attachments(reader: PdfReader) -> dict[str, Any]:
    attachments: dict[str, Any] = {}
    for name, blobs in reader.attachments.items():
        entries = []
        for blob in blobs:
            entries.append(decode_bytes(blob))
        attachments[name] = entries
    return attachments


def extract_named_destinations(reader: PdfReader) -> dict[str, Any]:
    destinations: dict[str, Any] = {}
    for name, destination in reader.named_destinations.items():
        entry: dict[str, Any] = {}
        for attribute in ("title", "page", "typ", "left", "right", "top", "bottom", "zoom"):
            if hasattr(destination, attribute):
                entry[attribute] = normalize_pdf_value(getattr(destination, attribute))
        if not entry:
            entry = {"value": repr(destination)}
        destinations[name] = entry
    return destinations


def extract_form_fields(reader: PdfReader) -> dict[str, Any] | None:
    fields = reader.get_fields()
    if not fields:
        return None
    return normalize_pdf_value(fields)


def extract_form_field_names(reader: PdfReader) -> list[str]:
    fields = reader.get_fields() or {}
    return sorted(str(name) for name in fields.keys())


def extract_attachment_summary(reader: PdfReader) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for name, blobs in reader.attachments.items():
        sizes = [len(blob) for blob in blobs]
        summary.append(
            {
                "name": name,
                "file_count": len(blobs),
                "total_bytes": sum(sizes),
                "sizes": sizes,
            }
        )
    return summary


def extract_catalog_language(reader: PdfReader) -> Any:
    root = reader.trailer.get("/Root")
    if root is None:
        return None
    if hasattr(root, "get_object"):
        try:
            root = root.get_object()
        except Exception:
            return None
    if hasattr(root, "get"):
        return normalize_pdf_value(root.get("/Lang"))
    return None


def extract_page_overview(reader: PdfReader) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    page_labels = list(getattr(reader, "page_labels", []))
    for index, page in enumerate(reader.pages, start=1):
        image_names: list[str] = []
        image_error = None
        try:
            for image in page.images:
                image_names.append(getattr(image, "name", None) or f"image-{len(image_names) + 1}")
        except Exception as exc:  # pragma: no cover - defensive path
            image_error = str(exc)

        page_info = {
            "page_number": index,
            "label": page_labels[index - 1] if len(page_labels) >= index else None,
            "rotation": getattr(page, "rotation", None),
            "image_count": len(image_names),
            "image_names": image_names,
            "annotation_count": count_entries(getattr(page, "annotations", None)),
        }
        if image_error is not None:
            page_info["image_error"] = image_error
        pages.append(page_info)
    return pages


def collect_core_metadata(
    metadata: dict[str, Any] | None,
    xmp_metadata: dict[str, Any] | None,
    catalog_language: Any,
    pdfinfo_fields: dict[str, str],
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []

    def add(label: str, *candidates: Any, is_date: bool = False) -> None:
        values = (
            [format_pdf_date(candidate) for candidate in candidates]
            if is_date
            else list(candidates)
        )
        value = pick_first_value(*values)
        if value:
            items.append((label, value))

    add(
        "Title",
        get_mapping_value(metadata, "/Title"),
        get_mapping_value(xmp_metadata, "dc_title"),
        pdfinfo_fields.get("Title"),
    )
    add(
        "Author",
        get_mapping_value(metadata, "/Author"),
        get_mapping_value(xmp_metadata, "dc_creator"),
        pdfinfo_fields.get("Author"),
    )
    add(
        "Subject",
        get_mapping_value(metadata, "/Subject"),
        get_mapping_value(xmp_metadata, "dc_description"),
        pdfinfo_fields.get("Subject"),
    )
    add(
        "Keywords",
        get_mapping_value(metadata, "/Keywords"),
        get_mapping_value(xmp_metadata, "pdf_keywords", "dc_subject"),
        pdfinfo_fields.get("Keywords"),
    )
    add(
        "Language",
        catalog_language,
        get_mapping_value(metadata, "/Lang"),
        get_mapping_value(xmp_metadata, "dc_language"),
        pdfinfo_fields.get("Language"),
    )
    add("Publisher", get_mapping_value(xmp_metadata, "dc_publisher"))
    add("Identifier", get_mapping_value(xmp_metadata, "xmp_identifier", "dc_identifier"))
    add(
        "Rights",
        get_mapping_value(xmp_metadata, "dc_rights", "xmp_rights_web_statement"),
    )
    add(
        "Creator",
        get_mapping_value(metadata, "/Creator"),
        get_mapping_value(xmp_metadata, "xmp_creator_tool"),
        pdfinfo_fields.get("Creator"),
    )
    add(
        "Producer",
        get_mapping_value(metadata, "/Producer"),
        get_mapping_value(xmp_metadata, "pdf_producer"),
        pdfinfo_fields.get("Producer"),
    )
    add(
        "Creation Date",
        get_mapping_value(metadata, "/CreationDate"),
        get_mapping_value(xmp_metadata, "xmp_create_date"),
        pdfinfo_fields.get("CreationDate"),
        is_date=True,
    )
    add(
        "Modification Date",
        get_mapping_value(metadata, "/ModDate"),
        get_mapping_value(xmp_metadata, "xmp_modify_date", "xmp_metadata_date"),
        pdfinfo_fields.get("ModDate"),
        is_date=True,
    )
    return items


def collect_additional_metadata(metadata: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not isinstance(metadata, dict):
        return []
    standard_keys = {
        "/Title",
        "/Author",
        "/Subject",
        "/Keywords",
        "/Lang",
        "/Creator",
        "/Producer",
        "/CreationDate",
        "/ModDate",
    }
    items: list[tuple[str, str]] = []
    for key in sorted(metadata):
        if key in standard_keys:
            continue
        value = humanize_scalar(metadata[key])
        if value:
            items.append((key.lstrip("/"), value))
    return items


def collect_text_stats(page_texts: list[dict[str, Any]], page_count: int) -> dict[str, Any]:
    pages_with_text: list[int] = []
    pages_without_text: list[int] = []
    total_characters = 0

    for item in page_texts:
        text = (item.get("text") or "").strip()
        page_number = item.get("page_number")
        total_characters += len(text)
        if page_number is None:
            continue
        if text:
            pages_with_text.append(page_number)
        else:
            pages_without_text.append(page_number)

    coverage_known = len(pages_with_text) + len(pages_without_text) == page_count
    return {
        "pages_with_text": pages_with_text,
        "pages_without_text": pages_without_text,
        "coverage_known": coverage_known,
        "total_characters": total_characters,
    }


def format_page_numbers(page_numbers: list[int]) -> str:
    if not page_numbers:
        return "None"
    return ", ".join(str(number) for number in page_numbers)


def summarize_outline_titles(outline: list[dict[str, Any]], max_entries: int = 15) -> list[str]:
    entries: list[str] = []
    for item in outline:
        title = humanize_scalar(item.get("title")) if isinstance(item, dict) else None
        if not title:
            continue
        depth = item.get("depth", 0) if isinstance(item, dict) else 0
        entries.append(f"Level {depth}: {title}" if depth else title)
    if len(entries) > max_entries:
        omitted = len(entries) - max_entries
        entries = entries[:max_entries] + [f"... {omitted} more bookmark entries omitted"]
    return entries


def summarize_attachments(attachments: list[dict[str, Any]]) -> list[str]:
    summaries: list[str] = []
    for item in attachments:
        plural = "s" if item["file_count"] != 1 else ""
        summaries.append(
            f"{item['name']} ({item['file_count']} file{plural}, " f"{item['total_bytes']} bytes)"
        )
    return summaries


def extract_page_metadata(reader: PdfReader) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        images = []
        try:
            for image in page.images:
                images.append(
                    {
                        "name": getattr(image, "name", None),
                        "data": decode_bytes(image.data),
                    }
                )
        except Exception as exc:  # pragma: no cover - defensive path
            images = [{"error": str(exc)}]

        page_info = {
            "page_number": index,
            "label": reader.page_labels[index - 1] if len(reader.page_labels) >= index else None,
            "rotation": normalize_pdf_value(getattr(page, "rotation", None)),
            "mediabox": normalize_pdf_value(getattr(page, "mediabox", None)),
            "cropbox": normalize_pdf_value(getattr(page, "cropbox", None)),
            "trimbox": normalize_pdf_value(getattr(page, "trimbox", None)),
            "bleedbox": normalize_pdf_value(getattr(page, "bleedbox", None)),
            "artbox": normalize_pdf_value(getattr(page, "artbox", None)),
            "annotations": normalize_pdf_value(getattr(page, "annotations", None)),
            "images": images,
        }
        pages.append(page_info)
    return pages


def extract_text_by_page(
    reader: PdfReader,
    pdf_path: Path,
) -> tuple[str, str, list[dict[str, Any]]]:
    page_texts: list[dict[str, Any]] = []
    extracted_chunks: list[str] = []
    source = "pypdf"

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text(extraction_mode="layout") or ""
        page_texts.append({"page_number": index, "source": "pypdf", "text": text})
        extracted_chunks.append(text.strip())

    if any(chunk for chunk in extracted_chunks):
        return source, build_text_content_markdown(page_texts), page_texts

    pdftotext_result = run_command(["pdftotext", "-layout", str(pdf_path), "-"])
    if pdftotext_result["available"] and pdftotext_result.get("exit_code") == 0:
        source = "pdftotext"
        pages = split_pdftotext_output(pdftotext_result.get("stdout") or "")
        page_texts = [
            {"page_number": index, "source": source, "text": text}
            for index, text in enumerate(pages, start=1)
        ]
        return source, build_text_content_markdown(page_texts), page_texts

    return source, "_No text extracted from the PDF._", page_texts


def extract_report_data(
    pdf_path: Path,
    output_path: Path,
    password: str,
    include_full: bool,
) -> dict[str, Any]:
    reader = PdfReader(str(pdf_path), strict=False)
    if reader.is_encrypted:
        if reader.decrypt(password) == 0:
            raise ValueError(
                "The PDF is encrypted and could not be decrypted with the " "provided password."
            )

    stat = pdf_path.stat()
    text_source, extracted_text, text_pages = extract_text_by_page(reader, pdf_path)

    metadata = normalize_pdf_value(reader.metadata)
    xmp_metadata = extract_xmp_metadata(reader)
    outline = flatten_outline(reader.outline)
    pdfinfo = run_command(["pdfinfo", str(pdf_path)])
    pdfinfo_fields = (
        parse_pdfinfo_output(pdfinfo.get("stdout", "")) if pdfinfo.get("exit_code") == 0 else {}
    )

    report_data = {
        "pdf_path": pdf_path,
        "output_path": output_path,
        "generated_at": datetime.now(UTC).isoformat(),
        "file_size": stat.st_size,
        "last_modified": isoformat_timestamp(stat.st_mtime),
        "sha256": sha256sum(pdf_path),
        "pdf_header": reader.pdf_header,
        "is_encrypted": reader.is_encrypted,
        "page_count": len(reader.pages),
        "text_source": text_source,
        "text_content": extracted_text,
        "text_pages": text_pages,
        "password_used": bool(password),
        "user_access_permissions": normalize_pdf_value(reader.user_access_permissions),
        "metadata": metadata,
        "xmp_metadata": xmp_metadata,
        "catalog_language": extract_catalog_language(reader),
        "outline": outline,
        "named_destinations_count": len(reader.named_destinations),
        "attachment_summary": extract_attachment_summary(reader),
        "form_field_names": extract_form_field_names(reader),
        "page_overview": extract_page_overview(reader),
        "pdfinfo": pdfinfo,
        "pdfinfo_fields": pdfinfo_fields,
    }

    if include_full:
        report_data.update(
            {
                "trailer": normalize_pdf_value(reader.trailer),
                "catalog": normalize_pdf_value(reader.trailer.get("/Root")),
                "attachments": extract_attachments(reader),
                "form_fields": extract_form_fields(reader),
                "named_destinations": extract_named_destinations(reader),
                "page_metadata": extract_page_metadata(reader),
                "pdfinfo_meta": run_command(["pdfinfo", "-meta", str(pdf_path)]),
                "qpdf_json": run_command(["qpdf", "--json", str(pdf_path)]),
            }
        )

    return report_data


def build_slim_report(report_data: dict[str, Any]) -> str:
    pdf_path = report_data["pdf_path"]
    output_path = report_data["output_path"]
    metadata = report_data["metadata"]
    xmp_metadata = report_data["xmp_metadata"]
    pdfinfo_fields = report_data["pdfinfo_fields"]
    text_stats = collect_text_stats(report_data["text_pages"], report_data["page_count"])

    pages_with_images = [
        item["page_number"]
        for item in report_data["page_overview"]
        if item.get("image_count", 0) > 0
    ]
    pages_with_annotations = [
        item["page_number"]
        for item in report_data["page_overview"]
        if item.get("annotation_count", 0) > 0
    ]
    attachment_files = sum(item["file_count"] for item in report_data["attachment_summary"])
    bookmark_highlights = summarize_outline_titles(report_data["outline"])
    pages_with_images_summary = (
        f"`{len(pages_with_images)}/{report_data['page_count']}` "
        f"({format_page_numbers(pages_with_images)})"
    )
    pages_with_annotations_summary = (
        f"`{len(pages_with_annotations)}/{report_data['page_count']}` "
        f"({format_page_numbers(pages_with_annotations)})"
    )

    sections = [
        f"# PDF Report: {markdown_escape(pdf_path.name)}",
        "",
        (
            "This is the default slim report: a human-readable summary of the "
            "document and its metadata, followed by the full extracted text."
        ),
        "",
    ]
    sections.extend(
        build_bullet_section(
            "Source File",
            [
                ("Report mode", "slim"),
                ("Absolute path", f"`{pdf_path}`"),
                ("Output Markdown", f"`{output_path}`"),
                ("Generated at (UTC)", f"`{report_data['generated_at']}`"),
                ("File size (bytes)", f"`{report_data['file_size']}`"),
                ("Last modified (UTC)", f"`{report_data['last_modified']}`"),
                ("SHA256", f"`{report_data['sha256']}`"),
            ],
            "No source file details were available.",
        )
    )
    sections.extend(
        build_bullet_section(
            "Core Metadata",
            collect_core_metadata(
                metadata,
                xmp_metadata,
                report_data["catalog_language"],
                pdfinfo_fields,
            ),
            "No human-meaningful descriptive metadata was found.",
        )
    )

    additional_metadata = collect_additional_metadata(metadata)
    if additional_metadata:
        sections.extend(
            build_bullet_section(
                "Additional Metadata",
                additional_metadata,
                "No additional metadata fields were found.",
            )
        )

    sections.extend(
        build_bullet_section(
            "Technical Summary",
            [
                ("PDF header", f"`{report_data['pdf_header']}`"),
                ("Number of pages", f"`{report_data['page_count']}`"),
                ("Encrypted", humanize_scalar(report_data["is_encrypted"])),
                (
                    "User access permissions",
                    pick_first_value(report_data["user_access_permissions"], "Unavailable"),
                ),
                ("Tagged PDF", pick_first_value(pdfinfo_fields.get("Tagged"))),
                ("Optimized", pick_first_value(pdfinfo_fields.get("Optimized"))),
                ("Page size", pick_first_value(pdfinfo_fields.get("Page size"))),
                ("XMP metadata packet present", humanize_scalar(xmp_metadata is not None)),
            ],
            "No technical summary data was available.",
        )
    )
    sections.extend(
        build_bullet_section(
            "Extraction Notes",
            [
                ("Text extraction source", f"`{report_data['text_source']}`"),
                ("Fallback extractor used", humanize_scalar(report_data["text_source"] != "pypdf")),
                ("Password supplied", humanize_scalar(report_data["password_used"])),
                (
                    "Pages with extracted text",
                    (
                        f"`{len(text_stats['pages_with_text'])}/{report_data['page_count']}`"
                        if text_stats["coverage_known"]
                        else "Unknown"
                    ),
                ),
                (
                    "Pages without extracted text",
                    (
                        format_page_numbers(text_stats["pages_without_text"])
                        if text_stats["coverage_known"]
                        else "Unknown"
                    ),
                ),
                ("Total extracted characters", f"`{text_stats['total_characters']}`"),
            ],
            "No extraction notes were available.",
        )
    )
    sections.extend(
        build_bullet_section(
            "Structure Summary",
            [
                ("Bookmarks", f"`{len(report_data['outline'])}`"),
                ("Named destinations", f"`{report_data['named_destinations_count']}`"),
                ("Embedded attachments", f"`{attachment_files}`"),
                ("Form fields", f"`{len(report_data['form_field_names'])}`"),
                ("Pages with images", pages_with_images_summary),
                ("Pages with annotations", pages_with_annotations_summary),
            ],
            "No structure summary data was available.",
        )
    )

    if bookmark_highlights:
        sections.extend(
            build_list_section(
                "Bookmark Highlights",
                bookmark_highlights,
                "No bookmark titles were available.",
            )
        )

    attachment_lines = summarize_attachments(report_data["attachment_summary"])
    if attachment_lines:
        sections.extend(
            build_list_section(
                "Embedded Attachment Names",
                attachment_lines,
                "No embedded attachments were found.",
            )
        )

    if report_data["form_field_names"]:
        sections.extend(
            build_list_section(
                "Form Field Names",
                report_data["form_field_names"],
                "No form fields were found.",
            )
        )

    sections.extend(
        [
            "## Text Content",
            "",
            report_data["text_content"],
            "",
        ]
    )
    return "\n".join(sections).rstrip() + "\n"


def build_full_report(report_data: dict[str, Any]) -> str:
    pdf_path = report_data["pdf_path"]
    output_path = report_data["output_path"]

    def json_block(value: Any) -> str:
        return markdown_code_block(
            json.dumps(value, ensure_ascii=False, indent=2),
            "json",
        )

    sections = [
        f"# PDF Full Extraction Report: {markdown_escape(pdf_path.name)}",
        "",
        (
            "This report contains everything this environment could extract "
            "directly from the PDF, including structured metadata, low-level "
            "PDF structure dumps, and text content."
        ),
        "",
        "## Source File",
        "",
        "- Report mode: `full`",
        f"- Absolute path: `{pdf_path}`",
        f"- Output Markdown: `{output_path}`",
        f"- Generated at (UTC): `{report_data['generated_at']}`",
        f"- File size (bytes): `{report_data['file_size']}`",
        f"- Last modified (UTC): `{report_data['last_modified']}`",
        f"- SHA256: `{report_data['sha256']}`",
        "",
        "## PDF Summary",
        "",
        f"- PDF header: `{report_data['pdf_header']}`",
        f"- Encrypted: `{report_data['is_encrypted']}`",
        f"- Number of pages: `{report_data['page_count']}`",
        f"- Text extraction source: `{report_data['text_source']}`",
        f"- Password supplied: `{report_data['password_used']}`",
        f"- User access permissions: `{report_data['user_access_permissions']}`",
        "",
        "## Document Information Dictionary",
        "",
        json_block(report_data["metadata"]),
        "",
        "## XMP Metadata",
        "",
        (
            json_block(report_data["xmp_metadata"])
            if report_data["xmp_metadata"] is not None
            else "No XMP metadata packet was found."
        ),
        "",
        "## PDF Catalog",
        "",
        json_block(report_data["catalog"]),
        "",
        "## PDF Trailer",
        "",
        json_block(report_data["trailer"]),
        "",
        "## Bookmarks / Outline",
        "",
        (
            json_block(report_data["outline"])
            if report_data["outline"]
            else "No outline entries were found."
        ),
        "",
        "## Named Destinations",
        "",
        (
            json_block(report_data["named_destinations"])
            if report_data["named_destinations"]
            else "No named destinations were found."
        ),
        "",
        "## Embedded Attachments",
        "",
        (
            json_block(report_data["attachments"])
            if report_data["attachments"]
            else "No embedded attachments were found."
        ),
        "",
        "## Form Fields",
        "",
        (
            json_block(report_data["form_fields"])
            if report_data["form_fields"] is not None
            else "No AcroForm fields were found."
        ),
        "",
        "## Per-Page Metadata",
        "",
        json_block(report_data["page_metadata"]),
        "",
        "## Text Content",
        "",
        report_data["text_content"],
        "",
        "## Text Content Snapshot",
        "",
        json_block(report_data["text_pages"]),
        "",
        "## External Tool: pdfinfo",
        "",
        markdown_code_block(
            report_data["pdfinfo"].get("stdout", "")
            or report_data["pdfinfo"].get("stderr", "")
            or "Tool unavailable.",
            "text",
        ),
        "",
        "## External Tool: pdfinfo -meta",
        "",
        markdown_code_block(
            report_data["pdfinfo_meta"].get("stdout", "")
            or report_data["pdfinfo_meta"].get("stderr", "")
            or "Tool unavailable.",
            "xml",
        ),
        "",
        "## External Tool: qpdf --json",
        "",
        markdown_code_block(
            report_data["qpdf_json"].get("stdout", "")
            or report_data["qpdf_json"].get("stderr", "")
            or "Tool unavailable.",
            "json",
        ),
        "",
    ]
    return "\n".join(sections).rstrip() + "\n"


def build_report(pdf_path: Path, output_path: Path, password: str, full: bool) -> str:
    report_data = extract_report_data(pdf_path, output_path, password, include_full=full)
    if full:
        return build_full_report(report_data)
    return build_slim_report(report_data)


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1
    if not pdf_path.is_file():
        print(f"Not a file: {pdf_path}", file=sys.stderr)
        return 1

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        if args.full:
            output_path = pdf_path.with_suffix(".full.md")
        else:
            output_path = pdf_path.with_suffix(".md")

    try:
        report = build_report(pdf_path, output_path, args.password, args.full)
    except Exception as exc:
        print(f"Failed to extract PDF data: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(report, encoding="utf-8")
    print(output_path)
    return 0
