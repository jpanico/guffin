"""Tests for the roam.better_bullet module."""

import pytest

from guffin.roam.better_bullet import BetterBulletProvenance, BetterBulletType


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


class TestBetterBulletProvenance:
    """BetterBulletProvenance members carry id, source, default_marker, and badge."""

    @pytest.mark.parametrize(
        ("member", "expected_id", "source", "default_marker", "badge"),
        [
            (BetterBulletProvenance.CALENDAR_EVENT, "calendar", "Calendar event", "📅", "📅"),
            (BetterBulletProvenance.EMAIL, "email", "Email", "📨", "📨"),
            (BetterBulletProvenance.PHONE_CALL, "phone", "Phone call", "📞", "📞"),
            (BetterBulletProvenance.CHAT_MESSAGE, "chat", "Chat message", "💬", "💬"),
            (BetterBulletProvenance.SCANNED_POST, "mail", "Scanned post", "📪", "📪"),
            (BetterBulletProvenance.SLACK, "slack", "Slack", "%", "＃"),
        ],
    )
    def test_member_fields(
        self, member: BetterBulletProvenance, expected_id: str, source: str, default_marker: str, badge: str
    ) -> None:
        """Every member carries the declared id, source, default marker, and badge."""
        assert member.id == expected_id
        assert member.source == source
        assert member.default_marker == default_marker
        assert member.badge == badge

    def test_member_count(self) -> None:
        """Exactly the declared kinds exist."""
        assert len(BetterBulletProvenance) == 6

    def test_id_is_the_member_value(self) -> None:
        """The id is the member's string value, so value lookup works by id."""
        assert BetterBulletProvenance("phone") is BetterBulletProvenance.PHONE_CALL
        assert BetterBulletProvenance.PHONE_CALL.id == BetterBulletProvenance.PHONE_CALL.value

    def test_default_markers_are_unique(self) -> None:
        """No two kinds claim the same default marker token."""
        markers = [member.default_marker for member in BetterBulletProvenance]
        assert len(markers) == len(set(markers))
