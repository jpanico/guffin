"""Tests for the roam.better_bullet module."""

import pytest

from guffin.roam.better_bullet import BetterBulletType


class TestBetterBulletType:
    """BetterBulletType members carry id, meaning, marker, and bullet."""

    @pytest.mark.parametrize(
        ("member", "expected_id", "meaning", "marker", "bullet"),
        [
            (BetterBulletType.EQUAL, "equal", "Equal / definition", "=", "="),
            (BetterBulletType.ARROW, "arrow", "Leads to", "->", "→"),
            (BetterBulletType.RESULT, "doubleArrow", "Result", "=>", "⇒"),
            (BetterBulletType.QUESTION, "question", "Question", "?", "?"),
            (BetterBulletType.IMPORTANT, "important", "Important / warning", "!", "!"),
            (BetterBulletType.IDEA, "plus", "Idea / addition", "+", "+"),
            (BetterBulletType.CONTRAST, "contrast", "Contrast / however", "~", "≠"),
            (BetterBulletType.EVIDENCE, "evidence", "Evidence / support", "^", "▸"),
            (BetterBulletType.DECISION, "decision", "Decision / choice", "|", "⎇"),
            (BetterBulletType.REFERENCE, "reference", "Reference / related", "@", "↗"),
            (BetterBulletType.PROCESS, "process", "Process / ongoing", "...", "↻"),
        ],
    )
    def test_member_fields(
        self, member: BetterBulletType, expected_id: str, meaning: str, marker: str, bullet: str
    ) -> None:
        """Every member carries the declared id, meaning, marker, and bullet."""
        assert member.id == expected_id
        assert member.meaning == meaning
        assert member.marker == marker
        assert member.bullet == bullet

    def test_member_count(self) -> None:
        """Exactly the declared kinds exist."""
        assert len(BetterBulletType) == 11

    def test_id_is_the_member_value(self) -> None:
        """The id is the member's string value, so value lookup works by id."""
        assert BetterBulletType("arrow") is BetterBulletType.ARROW
        assert BetterBulletType.ARROW.id == BetterBulletType.ARROW.value

    def test_markers_are_unique(self) -> None:
        """No two kinds claim the same marker token."""
        markers = [member.marker for member in BetterBulletType]
        assert len(markers) == len(set(markers))
