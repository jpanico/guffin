"""Unit tests for guffin.link."""

import pytest
from pydantic import ValidationError

from guffin.model.vertex_link import (
    GUFFIN_SCHEME,
    VertexLink,
    VertexLinkKind,
    is_vertex_link,
    parse_vertex_link,
    vertex_link_url,
)

# A representative valid 9-character UID.
_UID: str = "abc123xyz"
# A valid UID exercising the dash and underscore characters.
_UID_DASH_UNDERSCORE: str = "ab_cd-ef1"


class TestGuffinScheme:
    """Tests for the GUFFIN_SCHEME constant."""

    def test_value(self) -> None:
        """Test that the scheme literal is x-guffin."""
        assert GUFFIN_SCHEME == "x-guffin"


class TestVertexLinkKind:
    """Tests for the VertexLinkKind enum and its path-stem values."""

    def test_reference_value(self) -> None:
        """Test that REFERENCE encodes the 'vertex' path stem."""
        assert VertexLinkKind.REFERENCE.value == "vertex"

    def test_embed_value(self) -> None:
        """Test that EMBED encodes the 'vertex-embed' path stem."""
        assert VertexLinkKind.EMBED.value == "vertex-embed"


class TestByPathStem:
    """Tests for VertexLinkKind.by_path_stem — path-stem-to-kind lookup."""

    def test_vertex_stem(self) -> None:
        """Test that the 'vertex' stem maps to REFERENCE."""
        assert VertexLinkKind.by_path_stem("vertex") == VertexLinkKind.REFERENCE

    def test_vertex_embed_stem(self) -> None:
        """Test that the 'vertex-embed' stem maps to EMBED."""
        assert VertexLinkKind.by_path_stem("vertex-embed") == VertexLinkKind.EMBED

    def test_unknown_stem_is_none(self) -> None:
        """Test that an unrecognised stem yields None."""
        assert VertexLinkKind.by_path_stem("page") is None

    def test_member_name_is_none(self) -> None:
        """Test that lookup is by value (stem), not by member name."""
        assert VertexLinkKind.by_path_stem("REFERENCE") is None

    def test_empty_stem_is_none(self) -> None:
        """Test that the empty string yields None."""
        assert VertexLinkKind.by_path_stem("") is None


class TestVertexLinkUrl:
    """Tests for vertex_link_url — building x-guffin URLs."""

    def test_reference(self) -> None:
        """Test that a reference link renders as x-guffin:vertex/<uid>."""
        assert vertex_link_url(_UID, VertexLinkKind.REFERENCE) == "x-guffin:vertex/abc123xyz"

    def test_embed(self) -> None:
        """Test that an embed link renders as x-guffin:vertex-embed/<uid>."""
        assert vertex_link_url(_UID, VertexLinkKind.EMBED) == "x-guffin:vertex-embed/abc123xyz"

    def test_dash_underscore_uid(self) -> None:
        """Test that a UID containing a dash and underscore is rendered verbatim."""
        assert vertex_link_url(_UID_DASH_UNDERSCORE, VertexLinkKind.REFERENCE) == "x-guffin:vertex/ab_cd-ef1"

    def test_invalid_uid_too_short_rejected(self) -> None:
        """Test that an under-length UID is rejected by @validate_call."""
        with pytest.raises(ValidationError):
            vertex_link_url("short", VertexLinkKind.REFERENCE)

    def test_invalid_uid_too_long_rejected(self) -> None:
        """Test that an over-length UID is rejected by @validate_call."""
        with pytest.raises(ValidationError):
            vertex_link_url("abc123xyz0", VertexLinkKind.REFERENCE)


class TestParseVertexLink:
    """Tests for parse_vertex_link — parsing x-guffin URLs."""

    def test_reference(self) -> None:
        """Test that a reference URL parses to a REFERENCE VertexLink."""
        assert parse_vertex_link("x-guffin:vertex/abc123xyz") == VertexLink(VertexLinkKind.REFERENCE, _UID)

    def test_embed(self) -> None:
        """Test that an embed URL parses to an EMBED VertexLink."""
        assert parse_vertex_link("x-guffin:vertex-embed/abc123xyz") == VertexLink(VertexLinkKind.EMBED, _UID)

    def test_dash_underscore_uid(self) -> None:
        """Test that a UID containing a dash and underscore parses correctly."""
        assert parse_vertex_link("x-guffin:vertex/ab_cd-ef1") == VertexLink(
            VertexLinkKind.REFERENCE, _UID_DASH_UNDERSCORE
        )

    def test_http_url_is_none(self) -> None:
        """Test that an unrelated HTTP URL is not a vertex link."""
        assert parse_vertex_link("https://example.com/vertex/abc123xyz") is None

    def test_wrong_scheme_is_none(self) -> None:
        """Test that the x-guff scheme (a near-miss) is rejected."""
        assert parse_vertex_link("x-guff:vertex-embed/abc123xyz") is None

    def test_unknown_path_stem_is_none(self) -> None:
        """Test that an unrecognised path stem yields None."""
        assert parse_vertex_link("x-guffin:page/abc123xyz") is None

    def test_uid_too_short_is_none(self) -> None:
        """Test that an under-length UID yields None."""
        assert parse_vertex_link("x-guffin:vertex/abc12") is None

    def test_uid_too_long_is_none(self) -> None:
        """Test that an over-length UID yields None."""
        assert parse_vertex_link("x-guffin:vertex/abc123xyz0") is None

    def test_missing_slash_is_none(self) -> None:
        """Test that a path with no slash separator yields None."""
        assert parse_vertex_link("x-guffin:vertexabc123xyz") is None

    def test_extra_path_segment_is_none(self) -> None:
        """Test that a trailing extra path segment yields None."""
        assert parse_vertex_link("x-guffin:vertex/abc123xyz/extra") is None

    def test_empty_string_is_none(self) -> None:
        """Test that the empty string is not a vertex link."""
        assert parse_vertex_link("") is None


class TestIsVertexLink:
    """Tests for is_vertex_link — the boolean predicate."""

    def test_reference_true(self) -> None:
        """Test that a reference URL is recognised."""
        assert is_vertex_link("x-guffin:vertex/abc123xyz") is True

    def test_embed_true(self) -> None:
        """Test that an embed URL is recognised."""
        assert is_vertex_link("x-guffin:vertex-embed/abc123xyz") is True

    def test_http_url_false(self) -> None:
        """Test that an unrelated HTTP URL is rejected."""
        assert is_vertex_link("https://example.com") is False

    def test_wrong_scheme_false(self) -> None:
        """Test that the x-guff near-miss scheme is rejected."""
        assert is_vertex_link("x-guff:vertex-embed/abc123xyz") is False


class TestRoundTrip:
    """Tests that vertex_link_url and parse_vertex_link round-trip."""

    @pytest.mark.parametrize("kind", list(VertexLinkKind))
    def test_round_trip(self, kind: VertexLinkKind) -> None:
        """Test that parsing a built URL recovers the original kind and UID."""
        assert parse_vertex_link(vertex_link_url(_UID, kind)) == VertexLink(kind, _UID)
