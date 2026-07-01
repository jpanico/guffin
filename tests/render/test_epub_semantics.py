"""Tests for guffin.render.epub_semantics."""

import zipfile
from pathlib import Path
from typing import Final

import pypandoc  # type: ignore[import-untyped]
import pytest
import regex

from guffin.model.guffin_semantics import StructuralElement
from guffin.render.epub_semantics import EpubType, epub_type_for

_BODY_EPUB_TYPE_RE: Final[regex.Pattern[str]] = regex.compile(r'<body\b[^>]*epub:type="([^"]*)"')
_SECTION_EPUB_TYPE_RE: Final[regex.Pattern[str]] = regex.compile(r'<section\b[^>]*epub:type="([^"]*)"')


def _pandoc_body_division_by_term(work_dir: Path) -> dict[str, str]:
    """Return ``{epub:type term: <body> division}`` as Pandoc classifies each term out of the box.

    Emits one ``--split-level=1`` section per :class:`EpubType` term, converts the document to EPUB
    via Pandoc, and reads back the ``<body epub:type>`` division Pandoc assigned each isolated
    section.

    Args:
        work_dir: A writable directory for the intermediate ``.epub``.

    Returns:
        Mapping from each section's ``epub:type`` term to the ``<body>`` division string Pandoc
        emitted for the content document that holds it.
    """
    sections: Final[str] = "\n\n".join(
        f'# {member.name} {{epub:type="{member.value}"}}\n\nBody text.' for member in EpubType
    )
    markdown: Final[str] = f"---\ntitle: division probe\n---\n\n{sections}\n"
    epub_path: Final[Path] = work_dir / "probe.epub"
    pypandoc.convert_text(
        markdown, "epub3", format="markdown", outputfile=str(epub_path), extra_args=["--split-level=1"]
    )

    divisions: Final[dict[str, str]] = {}
    with zipfile.ZipFile(epub_path) as archive:
        for name in archive.namelist():
            if not (name.endswith(".xhtml") and "/text/" in name):
                continue
            xhtml: str = archive.read(name).decode("utf-8")
            body: regex.Match[str] | None = _BODY_EPUB_TYPE_RE.search(xhtml)
            section: regex.Match[str] | None = _SECTION_EPUB_TYPE_RE.search(xhtml)
            if body is not None and section is not None:
                divisions[section.group(1)] = body.group(1)
    return divisions


class TestEpubTypeDivisionMatchesPandoc:
    """Characterization: each ``EpubType.division`` must equal the ``<body>`` division Pandoc emits.

    ``EpubType.division`` claims to *record* Pandoc's out-of-the-box classification (see the module
    docstring), so this drives a real Pandoc conversion and asserts the recorded values still match.
    A failure means Pandoc changed its behaviour — the cue to revisit the
    ``StructuralElement.matter`` (CMOS) ↔ ``EpubType.division`` (Pandoc) correspondence and any
    ``<body>``-division post-processing built on it.
    """

    @pytest.fixture(scope="class")
    def pandoc_divisions(self, tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
        """Run the Pandoc probe once per class; shared across the parametrized assertions."""
        return _pandoc_body_division_by_term(tmp_path_factory.mktemp("epub_division_probe"))

    @pytest.mark.parametrize("member", list(EpubType), ids=lambda member: member.value)
    def test_division_matches_pandoc(self, member: EpubType, pandoc_divisions: dict[str, str]) -> None:
        """The recorded division for *member* matches the division Pandoc assigns its term."""
        assert member.value in pandoc_divisions, f"Pandoc emitted no <body epub:type> for {member.value!r}"
        assert pandoc_divisions[member.value] == member.division.value


class TestEpubTypeFor:
    """epub_type_for maps StructuralElements to their EpubType — a deliberately partial map."""

    def test_maps_label_divergences(self) -> None:
        """The label divergences the explicit (non name-equality) map exists to bridge."""
        assert epub_type_for(StructuralElement.TABLE_OF_CONTENTS) is EpubType.TOC
        assert epub_type_for(StructuralElement.LIST_OF_ILLUSTRATIONS) is EpubType.LOI

    def test_maps_a_same_named_element(self) -> None:
        """A directly-named element maps to the same-named EpubType."""
        assert epub_type_for(StructuralElement.COLOPHON) is EpubType.COLOPHON

    def test_maps_the_extended_epub_terms(self) -> None:
        """The four elements that drove the EpubType extension (toc/loi/endnotes/prologue) map."""
        assert epub_type_for(StructuralElement.TABLE_OF_CONTENTS) is EpubType.TOC
        assert epub_type_for(StructuralElement.LIST_OF_ILLUSTRATIONS) is EpubType.LOI
        assert epub_type_for(StructuralElement.ENDNOTES) is EpubType.ENDNOTES
        assert epub_type_for(StructuralElement.PROLOGUE) is EpubType.PROLOGUE

    def test_unmapped_elements_return_none(self) -> None:
        """Exactly the elements with no EPUB counterpart are unmapped."""
        unmapped = {element for element in StructuralElement if epub_type_for(element) is None}
        assert unmapped == {
            StructuralElement.TITLE_PAGE,
            StructuralElement.SECTION,
            StructuralElement.SUB_SECTION,
            StructuralElement.SUB_SUB_SECTION,
            StructuralElement.ABOUT_THE_AUTHOR,
        }
