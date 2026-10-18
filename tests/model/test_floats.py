"""Tests for guffin.model.floats (numbered figures, tables, and listings, and references to them)."""

from typing import Final

from conftest import article3_node_tree, asset_storage

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.floats import (
    Float,
    FloatNumber,
    FloatReference,
    float_content,
    float_numbers,
    float_of_wrapper,
    float_references,
    floats_in,
    kind_word,
    kind_word_references,
    placed_floats,
)
from guffin.model.publishing_semantics import FloatKind
from guffin.model.publishing_validation import validate_semantics
from guffin.model.vertex import (
    BlockEmbedVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree, standalone_link_target
from guffin.transcribe.roam_tree_to_guffin import transcribe

_LINK: Final[VertexLink] = VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1")
_IMAGE_URL: Final[str] = "https://firebasestorage.googleapis.com/v0/b/t/o/imgs%2Fdiagram.png?alt=media&token=d1"


def _float_tag(kind: str) -> AttributeAssignment:
    """A ``float:: <kind>`` assignment."""
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name="float", domain=AttributeDomain.GUFFIN), link=_LINK),
        values=(LiteralValue(value=kind),),
    )


def _reference(display: str, uid: str) -> str:
    """The Pandoc-Markdown form of a reference to *uid* displaying *display*."""
    return f"[{display}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"


def _image(uid: str) -> ImageVertex:
    return ImageVertex(
        uid=uid, storage=asset_storage(_IMAGE_URL), media_type=MediaType.PNG, scaled_image_size=ImageSize()
    )


def _table(uid: str) -> TableVertex:
    return TableVertex(uid=uid, table=Table(rows=(("a", "b"),)), table_style=TableStyle())


def _code(uid: str) -> CodeBlockVertex:
    return CodeBlockVertex(uid=uid, code="print(1)", language="python")


def _wrapper(uid: str, kind: str, caption: str, content_uid: str) -> TextVertex:
    """A float wrapper: a text block tagged ``float:: kind`` whose one child is *content_uid*."""
    return TextVertex(uid=uid, text=caption, children=[content_uid], attribute_assignments=[_float_tag(kind)])


def _tree(*vertices: Vertex, refs: tuple[Vertex, ...] = ()) -> VertexTree:
    return VertexTree(tree_vertices=list(vertices), ref_vertices=list(refs))


class TestKindWord:
    """kind_word recognizes exactly the three kind words, in any case."""

    def test_each_kind_word(self) -> None:
        """Each kind's word names that kind."""
        assert kind_word("figure") is FloatKind.FIGURE
        assert kind_word("table") is FloatKind.TABLE
        assert kind_word("listing") is FloatKind.LISTING

    def test_case_and_surrounding_whitespace_are_ignored(self) -> None:
        """A capitalized or padded word is still the kind word."""
        assert kind_word("Figure") is FloatKind.FIGURE
        assert kind_word(" TABLE ") is FloatKind.TABLE

    def test_anything_else_is_not(self) -> None:
        """A plural, an abbreviation, or a phrase holding the word is the author's alias."""
        assert kind_word("figures") is None
        assert kind_word("fig.") is None
        assert kind_word("the figure above") is None
        assert kind_word("") is None


class TestFloatKind:
    """FloatKind carries each kind's label and content type."""

    def test_labels(self) -> None:
        """The label is the capitalized word."""
        assert [kind.label for kind in FloatKind] == ["Figure", "Table", "Listing"]

    def test_content_types(self) -> None:
        """A figure wraps an image, a table a table, a listing a code block."""
        assert FloatKind.FIGURE.content_type.value == "guffin/image"
        assert FloatKind.TABLE.content_type.value == "guffin/table"
        assert FloatKind.LISTING.content_type.value == "guffin/code-block"


class TestFloatContent:
    """float_content resolves a wrapper's one child to the vertex it displays."""

    def test_direct_child(self) -> None:
        """A child that is the content displays itself."""
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["wrap00001"]),
            _wrapper("wrap00001", "figure", "Cap", "imag00001"),
            _image("imag00001"),
        )
        content = float_content(tree.uid_map["wrap00001"], tree)
        assert content is not None
        assert content.uid == "imag00001"

    def test_standalone_reference_child(self) -> None:
        """A child that is a standalone reference displays the referenced vertex."""
        referencing = TextVertex(uid="refr00001", text=_reference("", "imag00001"))
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["wrap00001"]),
            _wrapper("wrap00001", "figure", "Cap", "refr00001"),
            referencing,
            refs=(_image("imag00001"),),
        )
        content = float_content(tree.uid_map["wrap00001"], tree)
        assert content is not None
        assert content.uid == "imag00001"

    def test_no_child_or_two_children_is_none(self) -> None:
        """A wrapper needs exactly one child."""
        none = TextVertex(uid="wrap00001", text="Cap", attribute_assignments=[_float_tag("figure")])
        two = TextVertex(
            uid="wrap00002",
            text="Cap",
            children=["imag00001", "imag00002"],
            attribute_assignments=[_float_tag("figure")],
        )
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["wrap00001", "wrap00002"]),
            none,
            two,
            _image("imag00001"),
            _image("imag00002"),
        )
        assert float_content(none, tree) is None
        assert float_content(two, tree) is None


class TestFloatOfWrapper:
    """float_of_wrapper recognizes a well-formed wrapper and nothing else."""

    def test_well_formed_wrapper(self) -> None:
        """A tagged text block wrapping content of its kind is a float."""
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["wrap00001"]),
            _wrapper("wrap00001", "listing", "Hello", "code00001"),
            _code("code00001"),
        )
        assert float_of_wrapper(tree.uid_map["wrap00001"], tree) == Float(
            wrapper_uid="wrap00001", kind=FloatKind.LISTING, caption="Hello", content_uid="code00001"
        )

    def test_untagged_text_is_not_a_float(self) -> None:
        """A lead-in with a listing nested under it is the commonest structure in a graph, and no float."""
        lead_in = TextVertex(uid="lead00001", text="Here is the code:", children=["code00001"])
        tree = _tree(PageVertex(uid="page00001", title="Doc", children=["lead00001"]), lead_in, _code("code00001"))
        assert float_of_wrapper(lead_in, tree) is None

    def test_wrong_content_kind_is_not_a_float(self) -> None:
        """A table tag over an image is not a float (validation reports it)."""
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["wrap00001"]),
            _wrapper("wrap00001", "table", "Cap", "imag00001"),
            _image("imag00001"),
        )
        assert float_of_wrapper(tree.uid_map["wrap00001"], tree) is None

    def test_bare_content_is_not_a_float(self) -> None:
        """An image on its own, however captioned by its children, is not a float."""
        tree = _tree(PageVertex(uid="page00001", title="Doc", children=["imag00001"]), _image("imag00001"))
        assert float_of_wrapper(tree.uid_map["imag00001"], tree) is None


def _chaptered_tree() -> VertexTree:
    """Two chapters at level 1 after a preface; floats in each, one shown by embed from a collection page.

    Reading order: preface (front matter) with a figure; chapter 1 with a figure, a table, and an
    embedded figure kept on a collection page; chapter 2 with a listing and a second embed of the
    same collection figure.
    """
    page = PageVertex(uid="page00001", title="Doc", children=["pref00001", "chap00001", "chap00002"])
    preface = HeadingVertex(
        uid="pref00001",
        text="Preface",
        heading_level=1,
        children=["wrapp0001"],
        attribute_assignments=[
            AttributeAssignment(
                attribute=AttributeInstance(
                    definition=Attribute(name="element-type", domain=AttributeDomain.GUFFIN), link=_LINK
                ),
                values=(LiteralValue(value="preface"),),
            )
        ],
    )
    chapter_1 = HeadingVertex(
        uid="chap00001", text="One", heading_level=1, children=["wrapf0001", "wrapt0001", "embd00001", "textr0001"]
    )
    chapter_2 = HeadingVertex(uid="chap00002", text="Two", heading_level=1, children=["wrapl0001", "embd00002"])
    embed_1 = BlockEmbedVertex(uid="embd00001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="wrapc0001"))
    embed_2 = BlockEmbedVertex(uid="embd00002", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="wrapc0001"))
    referencing = TextVertex(
        uid="textr0001",
        text=f"See {_reference('figure', 'wrapf0001')} and {_reference('the table', 'wrapt0001')} and "
        f"{_reference('Listing', 'wrapl0001')}.",
    )
    return _tree(
        page,
        preface,
        _wrapper("wrapp0001", "figure", "Preface figure", "imagp0001"),
        _image("imagp0001"),
        chapter_1,
        _wrapper("wrapf0001", "figure", "First figure", "imagf0001"),
        _image("imagf0001"),
        _wrapper("wrapt0001", "table", "First table", "tablt0001"),
        _table("tablt0001"),
        embed_1,
        referencing,
        chapter_2,
        _wrapper("wrapl0001", "listing", "First listing", "codel0001"),
        _code("codel0001"),
        embed_2,
        refs=(_wrapper("wrapc0001", "figure", "Collection figure", "imagc0001"), _image("imagc0001")),
    )


class TestFloatsIn:
    """floats_in lists every well-formed float in the render-visible document."""

    def test_lists_tree_and_embedded_floats(self) -> None:
        """Floats in the tree and floats reached through an embed are both listed, once each."""
        assert set(floats_in(_chaptered_tree())) == {"wrapp0001", "wrapf0001", "wrapt0001", "wrapc0001", "wrapl0001"}


class TestPlacedFloats:
    """placed_floats lists each display in reading order with its governing headings."""

    def test_reading_order_with_embeds_at_their_site(self) -> None:
        """Displays come in reading order; the collection figure appears at each of its two embeds."""
        placed = placed_floats(_chaptered_tree())
        assert [item.float.wrapper_uid for item in placed] == [
            "wrapp0001",
            "wrapf0001",
            "wrapt0001",
            "wrapc0001",
            "wrapl0001",
            "wrapc0001",
        ]

    def test_governing_headings(self) -> None:
        """Each display carries the heading it sits under."""
        placed = placed_floats(_chaptered_tree())
        assert [[heading.uid for heading in item.headings] for item in placed] == [
            ["pref00001"],
            ["chap00001"],
            ["chap00001"],
            ["chap00001"],
            ["chap00002"],
            ["chap00002"],
        ]

    def test_standalone_reference_displays_the_float(self) -> None:
        """A block that is nothing but a reference to a wrapper displays the float there."""
        showing = TextVertex(uid="show00001", text=_reference("", "wrapc0001"))
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["show00001"]),
            showing,
            refs=(_wrapper("wrapc0001", "figure", "Collection figure", "imagc0001"), _image("imagc0001")),
        )
        assert [item.float.wrapper_uid for item in placed_floats(tree)] == ["wrapc0001"]

    def test_content_under_a_wrapper_is_not_walked(self) -> None:
        """A float's content is part of the float; nothing inside it is a separate display."""
        inner = _wrapper("wrapi0001", "figure", "Inner", "imagi0001")
        outer = TextVertex(
            uid="wrapo0001", text="Outer", children=["wrapi0001"], attribute_assignments=[_float_tag("figure")]
        )
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["wrapo0001"]), outer, inner, _image("imagi0001")
        )
        # The outer wrapper's content is a text vertex, not an image, so it is not a float; the walk
        # descends into it and finds the inner one.
        assert [item.float.wrapper_uid for item in placed_floats(tree)] == ["wrapi0001"]


class TestFloatNumbers:
    """float_numbers assigns each kind its own series, by chapter or straight through."""

    def test_by_chapter(self) -> None:
        """Body-matter chapters number their floats 1.1, 1.2, 2.1; the preface's figure has no chapter."""
        numbering = float_numbers(_chaptered_tree(), chapter_level=1)
        assert numbering.numbers == {
            "wrapp0001": FloatNumber(kind=FloatKind.FIGURE, chapter=None, ordinal=1),
            "wrapf0001": FloatNumber(kind=FloatKind.FIGURE, chapter=1, ordinal=1),
            "wrapt0001": FloatNumber(kind=FloatKind.TABLE, chapter=1, ordinal=1),
            "wrapc0001": FloatNumber(kind=FloatKind.FIGURE, chapter=1, ordinal=2),
            "wrapl0001": FloatNumber(kind=FloatKind.LISTING, chapter=2, ordinal=1),
        }
        assert numbering.repeated == ("wrapc0001",)

    def test_straight_through(self) -> None:
        """Without a chapter level every series runs through the document."""
        numbering = float_numbers(_chaptered_tree(), chapter_level=None)
        assert [(uid, number.text) for uid, number in numbering.numbers.items()] == [
            ("wrapp0001", "1"),
            ("wrapf0001", "2"),
            ("wrapt0001", "1"),
            ("wrapc0001", "3"),
            ("wrapl0001", "1"),
        ]

    def test_number_text(self) -> None:
        """A chaptered number reads chapter.ordinal; an unchaptered one is the ordinal alone."""
        assert FloatNumber(kind=FloatKind.FIGURE, chapter=2, ordinal=3).text == "2.3"
        assert FloatNumber(kind=FloatKind.FIGURE, chapter=None, ordinal=3).text == "3"


class TestFloatReferences:
    """float_references and kind_word_references find inline references by what they point at and say."""

    def test_references_to_wrappers(self) -> None:
        """Every inline reference to a wrapper is listed with its display and whether it is a kind word."""
        tree = _chaptered_tree()
        assert float_references(tree, floats_in(tree)) == [
            FloatReference(
                citing_uid="textr0001", display="figure", wrapper_uid="wrapf0001", kind_word=FloatKind.FIGURE
            ),
            FloatReference(citing_uid="textr0001", display="the table", wrapper_uid="wrapt0001", kind_word=None),
            FloatReference(
                citing_uid="textr0001", display="Listing", wrapper_uid="wrapl0001", kind_word=FloatKind.LISTING
            ),
        ]

    def test_kind_word_references_include_non_wrapper_targets(self) -> None:
        """A kind word pointing at a bare image is listed too, so validation can reject it."""
        text = TextVertex(uid="textr0001", text=f"See {_reference('figure', 'imag00001')}.")
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["textr0001", "imag00001"]), text, _image("imag00001")
        )
        assert kind_word_references(tree) == [
            FloatReference(
                citing_uid="textr0001", display="figure", wrapper_uid="imag00001", kind_word=FloatKind.FIGURE
            )
        ]

    def test_standalone_reference_is_a_display_not_a_reference(self) -> None:
        """A block that is nothing but the reference displays the float and is not listed."""
        showing = TextVertex(uid="show00001", text=_reference("figure", "wrapf0001"))
        tree = _tree(
            PageVertex(uid="page00001", title="Doc", children=["show00001", "wrapf0001"]),
            showing,
            _wrapper("wrapf0001", "figure", "Cap", "imagf0001"),
            _image("imagf0001"),
        )
        assert float_references(tree, floats_in(tree)) == []
        assert kind_word_references(tree) == []


class TestArticle3FloatsByReference:
    """Test Article 3's three floats, each displaying an in-page block through a standalone reference.

    The figure, listing, and table wrappers in its internal-links section each have one content
    child that is a standalone reference to the page's own image, fenced code block, or native
    table.  Each float is referred to twice with its kind-word alias: from an inline reference
    line earlier in the section, and from the explainer block directly before the float.  The
    inline lines open with a coloured label span, ``[label]{color=...} see [figure](...)``, which
    once parsed as a standalone reference and displayed every float a second time.
    """

    _WRAPPERS: Final[dict[str, tuple[FloatKind, str]]] = {
        "NlwSKgjdJ": (FloatKind.FIGURE, "J_Vt5_C6p"),
        "VQjeoP4r_": (FloatKind.LISTING, "yECzsUNPC"),
        "iuXlWiUAL": (FloatKind.TABLE, "yvlvNZwPC"),
    }
    _CITERS: Final[dict[str, str]] = {
        "xvjVDltB4": "NlwSKgjdJ",
        "ukIa7RHql": "VQjeoP4r_",
        "ltHJLOxly": "iuXlWiUAL",
        "87qCPx_8y": "NlwSKgjdJ",
        "0p_x3-HZO": "VQjeoP4r_",
        "3WVy07vZR": "iuXlWiUAL",
    }

    @staticmethod
    def _tree() -> VertexTree:
        return transcribe(article3_node_tree())

    def test_each_wrapper_floats_its_referenced_target(self) -> None:
        """Each wrapper is a float of its kind whose content is the referenced block, not the reference."""
        found: Final[dict[str, Float]] = floats_in(self._tree())
        for wrapper_uid, (kind, content_uid) in self._WRAPPERS.items():
            assert found[wrapper_uid].kind is kind
            assert found[wrapper_uid].content_uid == content_uid

    def test_each_float_is_displayed_once_in_reading_order(self) -> None:
        """The walk meets each wrapper once: the inline references do not display their floats."""
        assert [placed.float.wrapper_uid for placed in placed_floats(self._tree())] == list(self._WRAPPERS)

    def test_inline_reference_lines_are_not_standalone(self) -> None:
        """A reference line, label span first or explainer prose, leaves its kind-word reference inline."""
        tree: Final[VertexTree] = self._tree()
        for citing_uid in self._CITERS:
            assert standalone_link_target(tree.uid_map[citing_uid], tree) is None

    def test_each_series_numbers_its_float_one(self) -> None:
        """An article numbers each kind straight through, so each of the three floats is number 1."""
        numbering = float_numbers(self._tree(), None)
        assert {uid: number.text for uid, number in numbering.numbers.items()} == dict.fromkeys(self._WRAPPERS, "1")
        assert numbering.repeated == ()

    def test_kind_word_references_point_at_their_wrappers(self) -> None:
        """Each kind-word alias, inline line and explainer alike, names its target's kind and cites it."""
        references: Final[list[FloatReference]] = kind_word_references(self._tree())
        assert {reference.citing_uid: reference.wrapper_uid for reference in references} == self._CITERS
        assert all(reference.kind_word is self._WRAPPERS[reference.wrapper_uid][0] for reference in references)

    def test_article_validates(self) -> None:
        """The article passes every vocabulary rule, the float rules included."""
        assert validate_semantics(self._tree()).errors == ()
