"""EPUB structural semantics: the ``epub:type`` terms Guffin emits and Pandoc's ``<body>`` division for each.

An EPUB 3 content document declares its structural role through the ``epub:type`` attribute (the
`EPUB Structural Semantics Vocabulary <https://www.w3.org/TR/epub-ssv/>`_): a specific term on a
``<section>`` (e.g. ``colophon``) and one of three top-level divisions on the ``<body>``
(``frontmatter`` / ``bodymatter`` / ``backmatter``).

:class:`EpubType` enumerates the terms Guffin supports for tagging sections, and — for each —
records the ``<body>`` division **Pandoc assigns it out of the box**.  Pandoc derives that division
from its own hardcoded classification of a subset of terms, defaulting everything else to
``bodymatter``; :attr:`EpubType.division` is a faithful record of that observed behaviour (verified
against Pandoc's output), deliberately aligned with Pandoc — *not* a statement of where the part
conventionally belongs.

The conventional (publishing-standard) placement is a separate concern, carried by
:attr:`~guffin.model.guffin_semantics.StructuralElement.matter`, which is aligned with the Chicago
Manual of Style (CMOS).  The two intentionally diverge: their difference is exactly the set of
sections whose Pandoc-assigned ``<body>`` division would need post-processing to restore the CMOS
placement — ``epigraph``, ``introduction``, ``table-of-contents``, ``list-of-illustrations``,
``prologue``, ``afterword``, ``glossary``, and ``endnotes`` (each marked inline below).

Public symbols:

- **Enumerations**: :class:`EpubDivision` — the three top-level EPUB structural divisions;
  :class:`EpubType` — the ``epub:type`` terms Guffin supports, each carrying its :class:`EpubDivision`.
- **Functions**: :func:`epub_type_for` — map a
  :class:`~guffin.model.guffin_semantics.StructuralElement` to its :class:`EpubType`, or ``None`` when
  it has no EPUB counterpart.
"""

import enum
from typing import Final, Self

from pydantic import validate_call

from guffin.model.guffin_semantics import StructuralElement


class EpubDivision(enum.StrEnum):
    """A top-level EPUB structural division — the value of a content document's ``<body epub:type>``.

    Attributes:
        FRONTMATTER: Material preceding the main text (title page, preface, …).
        BODYMATTER: The main text (parts, chapters).
        BACKMATTER: Material following the main text (appendices, glossary, colophon, …).
    """

    FRONTMATTER = "frontmatter"
    BODYMATTER = "bodymatter"
    BACKMATTER = "backmatter"


class EpubType(enum.StrEnum):
    """An ``epub:type`` term Guffin supports for tagging a section, paired with Pandoc's ``<body>`` division.

    Each member's value is the ``epub:type`` string written on the ``<section>``; :attr:`division`
    records the ``<body>`` division Pandoc assigns that term out of the box (see the module
    docstring — this tracks Pandoc, not the conventional placement).  Title page and cover are
    intentionally absent — those come from the document metadata / cover image, not an authored
    content section.

    Attributes:
        division: The :class:`EpubDivision` Pandoc assigns this term's ``<body>`` out of the box.
    """

    def __new__(cls, value: str, division: EpubDivision) -> Self:
        """Create a member whose string value is *value* and that carries *division*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.division = division
        return member

    division: EpubDivision

    # Each division below is Pandoc 3.8.3's out-of-the-box classification (verified via probe), so it
    # tracks Pandoc — not the conventional placement.  Members whose Pandoc division diverges from the
    # CMOS placement on StructuralElement.matter are flagged inline; that divergence set is the
    # worklist for any pass that post-processes the <body> division back to the CMOS placement.
    COPYRIGHT_PAGE = ("copyright-page", EpubDivision.FRONTMATTER)
    EPIGRAPH = ("epigraph", EpubDivision.BODYMATTER)  # CMOS: front matter
    ACKNOWLEDGMENTS = ("acknowledgments", EpubDivision.FRONTMATTER)
    FOREWORD = ("foreword", EpubDivision.FRONTMATTER)
    PREFACE = ("preface", EpubDivision.FRONTMATTER)
    INTRODUCTION = ("introduction", EpubDivision.BODYMATTER)  # CMOS: front matter
    TOC = ("toc", EpubDivision.BODYMATTER)  # CMOS: front matter
    LOI = ("loi", EpubDivision.BODYMATTER)  # CMOS: front matter
    PROLOGUE = ("prologue", EpubDivision.FRONTMATTER)  # CMOS: body matter
    PART = ("part", EpubDivision.BODYMATTER)
    CHAPTER = ("chapter", EpubDivision.BODYMATTER)
    CONCLUSION = ("conclusion", EpubDivision.BODYMATTER)
    EPILOGUE = ("epilogue", EpubDivision.BODYMATTER)
    AFTERWORD = ("afterword", EpubDivision.BODYMATTER)  # CMOS: back matter
    APPENDIX = ("appendix", EpubDivision.BACKMATTER)
    GLOSSARY = ("glossary", EpubDivision.BODYMATTER)  # CMOS: back matter
    ENDNOTES = ("endnotes", EpubDivision.BODYMATTER)  # CMOS: back matter
    BIBLIOGRAPHY = ("bibliography", EpubDivision.BACKMATTER)
    INDEX = ("index", EpubDivision.BACKMATTER)
    COLOPHON = ("colophon", EpubDivision.BACKMATTER)


_EPUB_TYPE_BY_STRUCTURAL_ELEMENT: Final[dict[StructuralElement, EpubType]] = {
    StructuralElement.COPYRIGHT_PAGE: EpubType.COPYRIGHT_PAGE,
    StructuralElement.EPIGRAPH: EpubType.EPIGRAPH,
    StructuralElement.ACKNOWLEDGMENTS: EpubType.ACKNOWLEDGMENTS,
    StructuralElement.FOREWORD: EpubType.FOREWORD,
    StructuralElement.PREFACE: EpubType.PREFACE,
    StructuralElement.INTRODUCTION: EpubType.INTRODUCTION,
    StructuralElement.TABLE_OF_CONTENTS: EpubType.TOC,
    StructuralElement.LIST_OF_ILLUSTRATIONS: EpubType.LOI,
    StructuralElement.PROLOGUE: EpubType.PROLOGUE,
    StructuralElement.PART: EpubType.PART,
    StructuralElement.CHAPTER: EpubType.CHAPTER,
    StructuralElement.CONCLUSION: EpubType.CONCLUSION,
    StructuralElement.EPILOGUE: EpubType.EPILOGUE,
    StructuralElement.AFTERWORD: EpubType.AFTERWORD,
    StructuralElement.APPENDIX: EpubType.APPENDIX,
    StructuralElement.GLOSSARY: EpubType.GLOSSARY,
    StructuralElement.ENDNOTES: EpubType.ENDNOTES,
    StructuralElement.BIBLIOGRAPHY: EpubType.BIBLIOGRAPHY,
    StructuralElement.INDEX: EpubType.INDEX,
    StructuralElement.COLOPHON: EpubType.COLOPHON,
}
"""Maps a :class:`~guffin.model.guffin_semantics.StructuralElement` to its ``epub:type`` term.

Deliberately partial: elements with no EPUB counterpart — ``title-page`` (metadata driven), the
generic ``section``/``sub-section``/``sub-sub-section`` body divisions, and ``about-the-author`` — are
absent, and :func:`epub_type_for` returns ``None`` for them.  Note the
label divergences the explicit map exists to bridge: ``table-of-contents`` → ``toc`` and
``list-of-illustrations`` → ``loi``.
"""


@validate_call
def epub_type_for(element: StructuralElement) -> EpubType | None:
    """Return the :class:`EpubType` for *element*, or ``None`` when it has no EPUB counterpart.

    Args:
        element: The structural element to map.

    Returns:
        The mapped :class:`EpubType`, or ``None`` if *element* is not represented in EPUB.
    """
    return _EPUB_TYPE_BY_STRUCTURAL_ELEMENT.get(element)
