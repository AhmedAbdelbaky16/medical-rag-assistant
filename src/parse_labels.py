"""
Phase 1b — Parse & clean raw SPL XML into structured sections.

SPL (Structured Product Labeling) XML already tags content by section
(INDICATIONS & USAGE, WARNINGS, DOSAGE & ADMINISTRATION, etc.) — we don't
need to guess section boundaries from raw text. Our job here is to:

  1. Walk the XML tree and pull out each <section>
  2. Get its section title (e.g. "WARNINGS")
  3. Extract and clean the text inside it (strip tags, normalize whitespace)
  4. Save the result as one clean JSON file per drug in data/processed/

This JSON is what Phase 3 (SQL) and Phase 4 (chunking/embeddings) will
build on top of — so getting clean, well-structured output here saves
pain later.
"""

import json
import logging
import re
from pathlib import Path
import xml.etree.ElementTree as ET

from config import RAW_DIR, PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# SPL XML uses the HL7 v3 namespace on every element.
# xml.etree.ElementTree (stdlib) uses the same {prefix: uri} + "v3:tag"
# syntax as lxml for namespaced searches, so the rest of the parsing
# logic below barely changes.
SPL_NS = {"v3": "urn:hl7-org:v3"}


def clean_text(text: str) -> str:
    """Normalize whitespace produced by stripping XML tags."""
    text = re.sub(r"\s+", " ", text)  # collapse newlines/tabs/multi-spaces
    return text.strip()


def extract_section_text(section_elem) -> str:
    """
    Pull all human-readable text out of a <section>'s <text> block,
    joining paragraphs/list items with spaces, stripped of markup.
    """
    text_elem = section_elem.find("v3:text", namespaces=SPL_NS)
    if text_elem is None:
        return ""

    # itertext() walks all nested text nodes regardless of markup
    # (paragraphs, lists, tables, sub-elements) — this is what keeps
    # us from writing a fragile tag-by-tag extractor.
    raw = " ".join(text_elem.itertext())
    return clean_text(raw)


def get_section_title(section_elem) -> str:
    """
    Section title comes from either an explicit <title> element or,
    if missing, the human-readable LOINC 'displayName' on <code>.
    """
    title_elem = section_elem.find("v3:title", namespaces=SPL_NS)
    if title_elem is not None and title_elem.text:
        return clean_text("".join(title_elem.itertext()))

    code_elem = section_elem.find("v3:code", namespaces=SPL_NS)
    if code_elem is not None:
        display_name = code_elem.get("displayName")
        if display_name:
            return display_name.strip()

    return "UNTITLED SECTION"


def get_drug_name(root) -> str:
    """Pull the manufactured product name from the header."""
    name_elem = root.find(
        ".//v3:manufacturedProduct/v3:manufacturedProduct/v3:name",
        namespaces=SPL_NS,
    )
    if name_elem is not None and name_elem.text:
        return clean_text(name_elem.text)
    return "UNKNOWN"


def parse_label(xml_path: Path) -> dict:
    """Parse a single SPL XML file into a clean dict of sections."""
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    drug_name = get_drug_name(root)
    setid_elem = root.find("v3:setId", namespaces=SPL_NS)
    setid = setid_elem.get("root") if setid_elem is not None else None

    sections = []
    for section_elem in root.findall(".//v3:section", namespaces=SPL_NS):
        title = get_section_title(section_elem)
        text = extract_section_text(section_elem)

        if not text:  # skip empty sections rather than storing junk
            continue

        sections.append({"section_title": title, "text": text})

    return {
        "source_file": xml_path.name,
        "drug_name": drug_name,
        "setid": setid,
        "sections": sections,
    }


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(RAW_DIR.glob("*.xml"))
    if not xml_files:
        log.warning(f"No XML files found in {RAW_DIR}. Run download_labels.py first.")
        return

    parsed_count = 0
    for xml_path in xml_files:
        try:
            parsed = parse_label(xml_path)
        except Exception as e:
            log.error(f"Failed to parse {xml_path.name}: {e}")
            continue

        out_path = PROCESSED_DIR / (xml_path.stem + ".json")
        out_path.write_text(json.dumps(parsed, indent=2))
        log.info(
            f"Parsed {xml_path.name} -> {out_path.name} "
            f"({len(parsed['sections'])} sections)"
        )
        parsed_count += 1

    log.info(f"Done. Parsed {parsed_count}/{len(xml_files)} files.")


if __name__ == "__main__":
    main()
