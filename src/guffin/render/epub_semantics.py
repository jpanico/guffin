"""EPUB structural semantics: the ``epub:type`` terms Guffin emits and their matter division.

An EPUB 3 content document declares its structural role through the ``epub:type`` attribute (the
`EPUB Structural Semantics Vocabulary <https://www.w3.org/TR/epub-ssv/>`_): a specific term on a
``<section>`` (e.g. ``colophon``) and one of three top-level divisions on the ``<body>``
(``frontmatter`` / ``bodymatter`` / ``backmatter``).

:class:`EpubType` enumerates the terms Guffin supports for tagging sections, and — crucially —
carries the division Guffin assigns each one.  This is the authoritative term→division mapping:
Pandoc infers the ``<body>`` division only from its own hardcoded subset of terms, so several of
these (``epigraph``, ``introduction``, ``conclusion``, ``epilogue``, ``afterword``, ``glossary``,
``index``) would otherwise be misfiled under ``bodymatter``.

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
    """An ``epub:type`` term Guffin supports for tagging a section, paired with its matter division.

    Each member's value is the ``epub:type`` string written on the ``<section>``; :attr:`division`
    is the ``<body>`` division Guffin assigns it.  Title page and cover are intentionally absent —
    those come from the document metadata / cover image, not an authored content section.

    Attributes:
        division: The :class:`EpubDivision` this term belongs to.
    """

    def __new__(cls, value: str, division: EpubDivision) -> Self:
        """Create a member whose string value is *value* and that carries *division*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.division = division
        return member

    division: EpubDivision

    COPYRIGHT_PAGE = ("copyright-page", EpubDivision.FRONTMATTER)
    EPIGRAPH = ("epigraph", EpubDivision.FRONTMATTER)
    ACKNOWLEDGMENTS = ("acknowledgments", EpubDivision.FRONTMATTER)
    FOREWORD = ("foreword", EpubDivision.FRONTMATTER)
    PREFACE = ("preface", EpubDivision.FRONTMATTER)
    INTRODUCTION = ("introduction", EpubDivision.FRONTMATTER)
    TOC = ("toc", EpubDivision.FRONTMATTER)
    LOI = ("loi", EpubDivision.FRONTMATTER)
    PROLOGUE = ("prologue", EpubDivision.BODYMATTER)
    PART = ("part", EpubDivision.BODYMATTER)
    CHAPTER = ("chapter", EpubDivision.BODYMATTER)
    CONCLUSION = ("conclusion", EpubDivision.BACKMATTER)
    EPILOGUE = ("epilogue", EpubDivision.BACKMATTER)
    AFTERWORD = ("afterword", EpubDivision.BACKMATTER)
    APPENDIX = ("appendix", EpubDivision.BACKMATTER)
    GLOSSARY = ("glossary", EpubDivision.BACKMATTER)
    ENDNOTES = ("endnotes", EpubDivision.BACKMATTER)
    BIBLIOGRAPHY = ("bibliography", EpubDivision.BACKMATTER)
    INDEX = ("index", EpubDivision.BACKMATTER)
    COLOPHON = ("colophon", EpubDivision.BACKMATTER)


_EPUB_TYPE_BY_STRUCTURAL_ELEMENT: Final[dict[StructuralElement, EpubType]] = {
    StructuralElement.COPYRIGHT_PAGE: EpubType.COPYRIGHT_PAGE,
    StructuralElement.EPIGRAPH: EpubType.EPIGRAPH,
    StructuralElement.ACKNOWLEDGEMENTS: EpubType.ACKNOWLEDGMENTS,
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
    StructuralElement.APPENDICES: EpubType.APPENDIX,
    StructuralElement.GLOSSARY: EpubType.GLOSSARY,
    StructuralElement.ENDNOTES: EpubType.ENDNOTES,
    StructuralElement.BIBLIOGRAPHY: EpubType.BIBLIOGRAPHY,
    StructuralElement.INDEX: EpubType.INDEX,
    StructuralElement.COLOPHON: EpubType.COLOPHON,
}
"""Maps a :class:`~guffin.model.guffin_semantics.StructuralElement` to its ``epub:type`` term.

Deliberately partial: elements with no EPUB counterpart — ``cover`` and ``title-page`` (metadata /
cover-image driven), the generic ``section``/``sub-section``/``sub-sub-section`` body divisions, and
``about-the-author`` — are absent, and :func:`epub_type_for` returns ``None`` for them.  Note the
spelling/number divergences the explicit map exists to bridge: ``acknowledgements`` → ``acknowledgments``
and ``appendices`` → ``appendix``.
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
