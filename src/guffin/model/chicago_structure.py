"""A book's structural anatomy, aligned with the Chicago Manual of Style (CMOS).

The format-independent taxonomy of how a book is organized: the front/body/back **matter**
divisions and the named **structural elements** (title page, foreword, chapters, appendices, …)
that populate them.  The alignment follows CMOS, the de facto US book-publishing standard: each
element's conventional division is Chicago's ruling, independent of any output format and of any
attribute vocabulary declared over these constructs.

Public symbols:

- **Enumerations**: :class:`Matter` — a book's top-level division (front / body / back);
  :class:`StructuralElement` — a book's organizational parts, each carrying the :class:`Matter`
  division it conventionally belongs to.

A pure taxonomy at the bottom of the ``model/`` conceptual stack: it depends on nothing else in
``guffin``, and anything in ``model/`` may depend on it.
"""

import enum
from typing import Self


class Matter(enum.StrEnum):
    """A top-level division of a book — the publishing-standard grouping its parts belong to.

    Attributes:
        FRONT: Front matter — material preceding the main text (title page, foreword, preface, …).
        BODY: Body matter — the main text (parts, chapters).
        BACK: Back matter — material following the main text (appendices, glossary, colophon, …).
    """

    FRONT = "front-matter"
    BODY = "body-matter"
    BACK = "back-matter"


class StructuralElement(enum.StrEnum):
    """The structural elements of a book — its organizational parts, each in a :class:`Matter` division.

    The reusable section types a book is assembled from, from :attr:`TITLE_PAGE` through
    :attr:`COLOPHON` — title page, foreword, preface, parts and chapters, appendices, glossary, index,
    colophon, and so on.  Member names follow publishing conventions; each member's value is that name,
    and :attr:`matter` is the front/body/back-matter division it conventionally belongs to.

    :attr:`matter` is aligned with the Chicago Manual of Style (CMOS), the de facto US book-publishing
    standard — this is the *conventional* placement, independent of any output format.  How a specific
    format's toolchain happens to divide these parts is a separate, format-specific concern resolved
    where that format is rendered.

    Only the book's **interior** is classified by matter, so there is no ``cover`` member: per CMOS the
    cover (and jacket) is the exterior, outside the front/body/back-matter division.  In practice a
    cover is supplied as document metadata / a cover image, not authored as a tagged content section.

    Attributes:
        matter: The :class:`Matter` division this element conventionally belongs to, per CMOS.
    """

    def __new__(cls, value: str, matter: Matter) -> Self:
        """Create a member whose string value is *value* and that carries *matter*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.matter = matter
        return member

    matter: Matter

    TITLE_PAGE = ("title-page", Matter.FRONT)
    COPYRIGHT_PAGE = ("copyright-page", Matter.FRONT)
    EPIGRAPH = ("epigraph", Matter.FRONT)
    ACKNOWLEDGMENTS = ("acknowledgments", Matter.FRONT)
    FOREWORD = ("foreword", Matter.FRONT)
    PREFACE = ("preface", Matter.FRONT)
    INTRODUCTION = ("introduction", Matter.FRONT)
    TABLE_OF_CONTENTS = ("table-of-contents", Matter.FRONT)
    LIST_OF_ILLUSTRATIONS = ("list-of-illustrations", Matter.FRONT)
    PROLOGUE = ("prologue", Matter.BODY)
    PART = ("part", Matter.BODY)
    CHAPTER = ("chapter", Matter.BODY)
    SECTION = ("section", Matter.BODY)
    SUB_SECTION = ("sub-section", Matter.BODY)
    SUB_SUB_SECTION = ("sub-sub-section", Matter.BODY)
    # Conclusion and epilogue close the text proper (per CMOS): end of the body matter, not back
    # matter.  An afterword, being commentary *about* the text, opens the back matter instead.
    CONCLUSION = ("conclusion", Matter.BODY)
    EPILOGUE = ("epilogue", Matter.BODY)
    AFTERWORD = ("afterword", Matter.BACK)
    APPENDIX = ("appendix", Matter.BACK)
    GLOSSARY = ("glossary", Matter.BACK)
    ENDNOTES = ("endnotes", Matter.BACK)
    BIBLIOGRAPHY = ("bibliography", Matter.BACK)
    INDEX = ("index", Matter.BACK)
    ABOUT_THE_AUTHOR = ("about-the-author", Matter.BACK)
    COLOPHON = ("colophon", Matter.BACK)
