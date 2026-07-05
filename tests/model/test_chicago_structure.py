"""Tests for guffin.model.chicago_structure."""

from guffin.model.chicago_structure import Matter, StructuralElement


class TestMatter:
    """Matter names the three CMOS book divisions."""

    def test_members(self) -> None:
        """Exactly front, body, and back matter, under their publishing-standard values."""
        assert [member.value for member in Matter] == ["front-matter", "body-matter", "back-matter"]


class TestStructuralElement:
    """StructuralElement carries each organizational part's conventional CMOS division."""

    def test_every_element_carries_a_matter(self) -> None:
        """Each member's matter trait is a Matter member."""
        for element in StructuralElement:
            assert isinstance(element.matter, Matter), element

    def test_cmos_rulings(self) -> None:
        """Spot-check the deliberate CMOS placements, including the divergent-looking ones."""
        assert StructuralElement.TITLE_PAGE.matter is Matter.FRONT
        assert StructuralElement.INTRODUCTION.matter is Matter.FRONT
        assert StructuralElement.PROLOGUE.matter is Matter.BODY
        assert StructuralElement.CHAPTER.matter is Matter.BODY
        # Conclusion and epilogue close the text proper: body matter, not back matter.
        assert StructuralElement.CONCLUSION.matter is Matter.BODY
        assert StructuralElement.EPILOGUE.matter is Matter.BODY
        # An afterword is commentary about the text: it opens the back matter.
        assert StructuralElement.AFTERWORD.matter is Matter.BACK
        assert StructuralElement.COLOPHON.matter is Matter.BACK

    def test_values_are_publishing_labels(self) -> None:
        """Member values are the spelled-out publishing names, not format abbreviations."""
        assert StructuralElement.TABLE_OF_CONTENTS.value == "table-of-contents"
        assert StructuralElement.LIST_OF_ILLUSTRATIONS.value == "list-of-illustrations"

    def test_no_cover_member(self) -> None:
        """Per CMOS only the book interior is matter-classified: the exterior cover has no member."""
        assert "cover" not in {member.value for member in StructuralElement}
