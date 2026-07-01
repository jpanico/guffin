"""Tests for guffin.render.epub_semantics."""

from guffin.model.guffin_semantics import StructuralElement
from guffin.render.epub_semantics import EpubType, epub_type_for


class TestEpubTypeFor:
    """epub_type_for maps StructuralElements to their EpubType — a deliberately partial map."""

    def test_maps_divergent_spellings(self) -> None:
        """The spelling/number divergences the explicit (non name-equality) map exists to bridge."""
        assert epub_type_for(StructuralElement.ACKNOWLEDGEMENTS) is EpubType.ACKNOWLEDGMENTS
        assert epub_type_for(StructuralElement.APPENDICES) is EpubType.APPENDIX

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
            StructuralElement.COVER,
            StructuralElement.TITLE_PAGE,
            StructuralElement.SECTION,
            StructuralElement.SUB_SECTION,
            StructuralElement.SUB_SUB_SECTION,
            StructuralElement.ABOUT_THE_AUTHOR,
        }
