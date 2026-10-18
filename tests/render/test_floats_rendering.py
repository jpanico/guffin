"""Tests for guffin.render.floats_rendering and the float rendering in pandoc_rendering."""

import importlib.resources
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
import pytest
from conftest import asset_storage

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.vertex import (
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, VertexView
from guffin.render.date_format import DateFormat
from guffin.render.floats_rendering import (
    FLOAT_LIST_CLASS,
    float_chapter_level,
    insert_float_lists,
    label_floats,
    prepare_floats,
)
from guffin.render.md_rendering import _unclass_float_links
from guffin.render.pandoc_ast import pandoc_to_json
from guffin.render.pandoc_rendering import (
    FLOAT_CLASS,
    FLOAT_LINK_CLASS,
    float_identifier,
    make_doc_resolver,
    resolve_vertex_links,
    vertex_tree_to_pandoc,
)
from guffin.render.project import ArticleProfile, BookProfile, ManuscriptProfile
from guffin.render.render_options import OutputFormat

_LINK: Final[VertexLink] = VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1")
_IMAGE_URL: Final[str] = "https://firebasestorage.googleapis.com/v0/b/t/o/imgs%2Fdiagram.png?alt=media&token=d1"


def _float_tag(kind: str) -> AttributeAssignment:
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name="float", domain=AttributeDomain.GUFFIN), link=_LINK),
        values=(LiteralValue(value=kind),),
    )


def _reference(display: str, uid: str) -> str:
    return f"[{display}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"


def _image(uid: str) -> ImageVertex:
    return ImageVertex(
        uid=uid, storage=asset_storage(_IMAGE_URL), media_type=MediaType.PNG, scaled_image_size=ImageSize()
    )


def _wrapper(uid: str, kind: str, caption: str, content_uid: str) -> TextVertex:
    return TextVertex(uid=uid, text=caption, children=[content_uid], attribute_assignments=[_float_tag(kind)])


def _figure_tree(*after: Vertex, chapters: bool = False) -> VertexTree:
    """A page with a figure float (under a chapter heading when *chapters*) and *after* blocks."""
    wrapper = _wrapper("wrap00001", "figure", "A diagram of the machine", "imag00001")
    image = _image("imag00001")
    if chapters:
        chapter = HeadingVertex(
            uid="chap00001", text="One", heading_level=1, children=["wrap00001"] + [v.uid for v in after]
        )
        page = PageVertex(uid="page00001", title="Doc", children=["chap00001"])
        return VertexTree(tree_vertices=[page, chapter, wrapper, image, *after])
    page = PageVertex(uid="page00001", title="Doc", children=["wrap00001"] + [v.uid for v in after])
    return VertexTree(tree_vertices=[page, wrapper, image, *after])


def _assets() -> dict[str, Path]:
    return {"imag00001": Path("diagram.png")}


def _figures(doc: pf.Doc) -> list[pf.Figure]:
    found: list[pf.Figure] = []

    def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
        if isinstance(elem, pf.Figure):
            found.append(elem)

    doc.walk(_collect)
    return found


def _tables(doc: pf.Doc) -> list[pf.Table]:
    found: list[pf.Table] = []

    def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
        if isinstance(elem, pf.Table):
            found.append(elem)

    doc.walk(_collect)
    return found


def _links(doc: pf.Doc) -> list[pf.Link]:
    found: list[pf.Link] = []

    def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
        if isinstance(elem, pf.Link):
            found.append(elem)

    doc.walk(_collect)
    return found


class TestFloatChapterLevel:
    """float_chapter_level maps a policy to the heading level floats are numbered by."""

    def test_article_and_manuscript_number_straight_through(self) -> None:
        """A sequential policy has no chapter level."""
        assert float_chapter_level(ArticleProfile().structural_policy) is None
        assert float_chapter_level(ManuscriptProfile().structural_policy) is None

    def test_book_numbers_by_its_chapter_level(self) -> None:
        """A book numbers by its division's chapter level: 1 for chapters, 2 under parts."""
        assert float_chapter_level(BookProfile().structural_policy) == 1
        assert float_chapter_level(BookProfile(with_parts=True).structural_policy) == 2


class TestFloatBlocks:
    """A wrapper renders as a captioned Pandoc element carrying the float's identifier."""

    def test_figure_wrapper_becomes_a_figure(self) -> None:
        """A figure float is a Figure holding the image, its caption the wrapper's text."""
        doc, _ = vertex_tree_to_pandoc(_figure_tree(), _assets(), {})
        figures = _figures(doc)
        assert len(figures) == 1
        figure = figures[0]
        assert figure.identifier == float_identifier("wrap00001")
        assert figure.classes == [FLOAT_CLASS, "float-figure"]
        assert pf.stringify(figure.caption) == "A diagram of the machine"
        assert any(isinstance(inline, pf.Image) for block in figure.content for inline in getattr(block, "content", []))

    def test_listing_wrapper_becomes_a_figure_holding_the_code(self) -> None:
        """A listing float is a Figure holding the CodeBlock."""
        wrapper = _wrapper("wrap00002", "listing", "The whole program", "code00001")
        code = CodeBlockVertex(uid="code00001", code="print(1)", language="python")
        page = PageVertex(uid="page00001", title="Doc", children=["wrap00002"])
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, wrapper, code]), {}, {})
        figure = _figures(doc)[0]
        assert figure.classes == [FLOAT_CLASS, "float-listing"]
        assert isinstance(figure.content[0], pf.CodeBlock)

    def test_table_wrapper_captions_the_table_itself(self) -> None:
        """A table float is the Table with its own caption and the float's identifier, not a Figure."""
        wrapper = _wrapper("wrap00003", "table", "Monthly totals", "tabl00001")
        table = TableVertex(uid="tabl00001", table=Table(rows=(("a", "b"),)), table_style=TableStyle())
        page = PageVertex(uid="page00001", title="Doc", children=["wrap00003"])
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, wrapper, table]), {}, {})
        assert _figures(doc) == []
        rendered = _tables(doc)[0]
        assert rendered.identifier == float_identifier("wrap00003")
        assert rendered.classes == [FLOAT_CLASS, "float-table"]
        assert pf.stringify(rendered.caption) == "Monthly totals"

    def test_wrapper_in_a_bullet_outline_breaks_out_of_the_list(self) -> None:
        """A float never lists: under a bullet layout it stands between the lists as a block."""
        before = TextVertex(uid="text00001", text="before")
        after = TextVertex(uid="text00002", text="after")
        wrapper = _wrapper("wrap00001", "figure", "Cap", "imag00001")
        page = PageVertex(uid="page00001", title="Doc", children=["text00001", "wrap00001", "text00002"])
        tree = VertexTree(tree_vertices=[page, before, wrapper, _image("imag00001"), after])
        doc, _ = vertex_tree_to_pandoc(
            tree, _assets(), {"page00001": VertexView(children_layout=ChildrenLayout.BULLET)}
        )
        kinds = [type(block).__name__ for block in doc.content]
        assert kinds == ["BulletList", "Figure", "BulletList"]

    def test_standalone_reference_displays_the_float(self) -> None:
        """A block that is nothing but a reference to a wrapper renders the whole float there."""
        showing = TextVertex(uid="show00001", text=_reference("", "wrap00001"))
        page = PageVertex(uid="page00001", title="Doc", children=["show00001"])
        tree = VertexTree(
            tree_vertices=[page, showing],
            ref_vertices=[_wrapper("wrap00001", "figure", "Kept elsewhere", "imag00001"), _image("imag00001")],
        )
        doc, _ = vertex_tree_to_pandoc(tree, _assets(), {})
        figure = _figures(doc)[0]
        assert pf.stringify(figure.caption) == "Kept elsewhere"


class TestLabelFloats:
    """prepare_floats numbers the floats and writes the label into each caption."""

    def test_sequential_label(self) -> None:
        """An article's figure is Figure 1."""
        doc, _ = vertex_tree_to_pandoc(_figure_tree(), _assets(), {})
        prepared = prepare_floats(doc, _figure_tree(), ArticleProfile().structural_policy)
        assert prepared.numbers["wrap00001"].text == "1"
        caption = _figures(doc)[0].caption
        assert isinstance(caption.content[0].content[0], pf.Strong)
        assert pf.stringify(caption) == "Figure 1. A diagram of the machine"

    def test_by_chapter_label(self) -> None:
        """A book's figure in chapter 1 is Figure 1.1."""
        tree = _figure_tree(chapters=True)
        doc, _ = vertex_tree_to_pandoc(tree, _assets(), {})
        prepare_floats(doc, tree, BookProfile().structural_policy)
        assert pf.stringify(_figures(doc)[0].caption) == "Figure 1.1. A diagram of the machine"

    def test_unnumbered_float_keeps_its_bare_caption(self) -> None:
        """label_floats leaves a float with no number alone."""
        doc, _ = vertex_tree_to_pandoc(_figure_tree(), _assets(), {})
        label_floats(doc, {})
        assert pf.stringify(_figures(doc)[0].caption) == "A diagram of the machine"


class TestFloatReferences:
    """An inline reference to a wrapper resolves to a link, completed when its alias is a kind word."""

    @staticmethod
    def _resolved(display: str) -> pf.Doc:
        referencing = TextVertex(uid="text00001", text=f"See {_reference(display, 'wrap00001')}.")
        tree = _figure_tree(referencing)
        doc, inline_map = vertex_tree_to_pandoc(tree, _assets(), {})
        prepared = prepare_floats(doc, tree, ArticleProfile().structural_policy)
        resolve_vertex_links(
            doc,
            tree,
            make_doc_resolver(
                doc,
                inline_map,
                DateFormat.ROAM_LONG,
                heading_links=True,
                floats=prepared.floats,
                float_numbers=prepared.numbers,
            ),
        )
        return doc

    def test_kind_word_is_completed_with_the_number(self) -> None:
        """[figure](((uid))) renders figure 1, linked to the float."""
        link = _links(self._resolved("figure"))[0]
        assert pf.stringify(link) == "figure 1"
        assert link.url == f"#{float_identifier('wrap00001')}"
        assert link.classes == [FLOAT_LINK_CLASS]

    def test_kind_word_keeps_the_authors_case(self) -> None:
        """[Figure](((uid))) opening a sentence renders Figure 1."""
        assert pf.stringify(_links(self._resolved("Figure"))[0]) == "Figure 1"

    def test_authors_alias_is_kept_verbatim(self) -> None:
        """[the diagram above](((uid))) renders those words, linked."""
        link = _links(self._resolved("the diagram above"))[0]
        assert pf.stringify(link) == "the diagram above"
        assert link.url == f"#{float_identifier('wrap00001')}"


@pytest.mark.pandoc
class TestWriters:
    """The Typst and GFM writers set a float and a reference the way each format was decided to."""

    @staticmethod
    def _doc_with_reference() -> pf.Doc:
        referencing = TextVertex(uid="text00001", text=f"See {_reference('figure', 'wrap00001')}.")
        tree = _figure_tree(referencing)
        doc, inline_map = vertex_tree_to_pandoc(tree, _assets(), {})
        prepared = prepare_floats(doc, tree, ArticleProfile().structural_policy)
        resolve_vertex_links(
            doc,
            tree,
            make_doc_resolver(
                doc,
                inline_map,
                DateFormat.ROAM_LONG,
                heading_links=True,
                floats=prepared.floats,
                float_numbers=prepared.numbers,
            ),
        )
        return doc

    def test_typst_figure_with_label_and_link(self) -> None:
        """The Typst writer emits #figure with the float's label and a link to it."""
        typst: str = pypandoc.convert_text(pandoc_to_json(self._doc_with_reference()), "typst", format="json")  # type: ignore[no-untyped-call]
        assert "#figure(" in typst
        assert f"<{float_identifier('wrap00001')}>" in typst
        assert "Figure 1." in typst
        assert f"#link(<{float_identifier('wrap00001')}>)[figure 1]" in typst

    def test_gfm_unwraps_the_figure(self) -> None:
        """gfm_float.lua turns the Figure into an anchor, the image, and an emphasized caption line; no <figure>."""
        doc: Final[pf.Doc] = self._doc_with_reference()
        _unclass_float_links(doc)
        with importlib.resources.as_file(
            importlib.resources.files("guffin.render.gfm_resources") / "gfm_float.lua"
        ) as lua:
            gfm: str = pypandoc.convert_text(  # type: ignore[no-untyped-call]
                pandoc_to_json(doc), "gfm", format="json", extra_args=[f"--lua-filter={lua}"]
            )
        assert "<figure" not in gfm
        assert f'<a id="{float_identifier("wrap00001")}"></a>' in gfm
        assert "![](diagram.png" in gfm
        assert "*__Figure 1.__ A diagram of the machine*" in gfm or "***Figure 1.** A diagram of the machine*" in gfm
        assert f"[figure 1](#{float_identifier('wrap00001')})" in gfm

    def test_gfm_sets_a_table_caption_above_the_table(self) -> None:
        """A table float's caption precedes the pipe table, after the anchor."""
        wrapper = _wrapper("wrap00003", "table", "Monthly totals", "tabl00001")
        table = TableVertex(uid="tabl00001", table=Table(rows=(("a", "b"),)), table_style=TableStyle())
        page = PageVertex(uid="page00001", title="Doc", children=["wrap00003"])
        tree = VertexTree(tree_vertices=[page, wrapper, table])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        prepare_floats(doc, tree, ArticleProfile().structural_policy)
        with importlib.resources.as_file(
            importlib.resources.files("guffin.render.gfm_resources") / "gfm_float.lua"
        ) as lua:
            gfm: str = pypandoc.convert_text(  # type: ignore[no-untyped-call]
                pandoc_to_json(doc), "gfm", format="json", extra_args=[f"--lua-filter={lua}"]
            )
        anchor = gfm.index(f'<a id="{float_identifier("wrap00003")}"></a>')
        caption = gfm.index("Table 1.")
        pipe = gfm.index("| a")
        assert anchor < caption < pipe
        assert "{#" not in gfm


def _tagged_heading(uid: str, text: str, element_type: str, children: list[str]) -> HeadingVertex:
    """A level-1 heading tagged ``element-type:: <element_type>``."""
    return HeadingVertex(
        uid=uid,
        text=text,
        heading_level=1,
        children=children,
        attribute_assignments=[
            AttributeAssignment(
                attribute=AttributeInstance(
                    definition=Attribute(name="element-type", domain=AttributeDomain.GUFFIN), link=_LINK
                ),
                values=(LiteralValue(value=element_type),),
            )
        ],
    )


def _listed_doc(output_format: OutputFormat) -> pf.Doc:
    """A book with a list of illustrations (with an intro line), a list of tables, and one figure chapter.

    Built, labelled, and run through :func:`insert_float_lists`; the book has no table float, so
    its list of tables has nothing to list.
    """
    page = PageVertex(uid="page00001", title="Doc", children=["loih00001", "loth00001", "chap00001"])
    tree = VertexTree(
        tree_vertices=[
            page,
            _tagged_heading("loih00001", "Illustrations", "list-of-illustrations", ["intro0001"]),
            TextVertex(uid="intro0001", text="Maps drawn for this edition."),
            _tagged_heading("loth00001", "Tables", "list-of-tables", ["tabint001"]),
            TextVertex(uid="tabint001", text="An intro to an empty list."),
            HeadingVertex(uid="chap00001", text="One", heading_level=1, children=["wrap00001"]),
            _wrapper("wrap00001", "figure", "A diagram of the machine", "imag00001"),
            _image("imag00001"),
        ]
    )
    doc, _ = vertex_tree_to_pandoc(tree, _assets(), {})
    prepared = prepare_floats(doc, tree, BookProfile().structural_policy)
    insert_float_lists(doc, tree, prepared.numbers, output_format)
    return doc


def _blocks_after(doc: pf.Doc, header_text: str) -> list[pf.Block]:
    """The blocks of the section under the top-level Header reading *header_text*."""
    blocks: list[pf.Block] = list(doc.content)
    start = next(
        index
        for index, block in enumerate(blocks)
        if isinstance(block, pf.Header) and pf.stringify(block) == header_text
    )
    end = next((index for index in range(start + 1, len(blocks)) if isinstance(blocks[index], pf.Header)), len(blocks))
    return blocks[start + 1 : end]


class TestInsertFloatLists:
    """insert_float_lists generates each list into its authored heading, or drops a heading with nothing to list."""

    def test_pdf_list_is_an_outline_of_the_float_labels(self) -> None:
        """The PDF list is a Typst outline targeting exactly the listed floats' labels, after the intro."""
        section = _blocks_after(_listed_doc(OutputFormat.PDF), "Illustrations")
        assert pf.stringify(section[0]) == "Maps drawn for this edition."
        outline = section[-1]
        assert isinstance(outline, pf.RawBlock)
        assert outline.format == "typst"
        assert outline.text == f"#outline(title: none, target: selector(<{float_identifier('wrap00001')}>))"

    def test_epub_list_is_a_classed_list_of_links(self) -> None:
        """The EPUB list is a classed block holding one link per float, its labelled caption."""
        section = _blocks_after(_listed_doc(OutputFormat.EPUB), "Illustrations")
        block = section[-1]
        assert isinstance(block, pf.Div)
        assert block.classes == [FLOAT_LIST_CLASS]
        links: list[pf.Link] = []
        block.walk(lambda elem, _doc: links.append(elem) if isinstance(elem, pf.Link) else None)
        assert [(link.url, pf.stringify(link)) for link in links] == [
            (f"#{float_identifier('wrap00001')}", "Figure 1.1. A diagram of the machine")
        ]

    def test_markdown_list_is_a_bare_bullet_list(self) -> None:
        """The Markdown list is a bullet list of links with no wrapping block (GFM would write it as HTML)."""
        section = _blocks_after(_listed_doc(OutputFormat.MARKDOWN), "Illustrations")
        assert isinstance(section[-1], pf.BulletList)

    def test_heading_with_nothing_to_list_is_dropped_with_a_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """The list of tables has no table to list, so its heading and intro leave the document."""
        with caplog.at_level("WARNING"):
            doc = _listed_doc(OutputFormat.EPUB)
        headers = [pf.stringify(block) for block in doc.content if isinstance(block, pf.Header)]
        assert "Tables" not in headers
        assert "An intro to an empty list." not in pf.stringify(doc)
        assert "list-of-tables heading" in caplog.text

    def test_each_list_lands_under_its_own_heading(self) -> None:
        """Generating the first list does not shift where the second heading's section is found."""
        doc = _listed_doc(OutputFormat.EPUB)
        headers = [pf.stringify(block) for block in doc.content if isinstance(block, pf.Header)]
        assert headers == ["Illustrations", "One"]
        assert len(_blocks_after(doc, "One")) == 1

    def test_no_list_heading_no_list(self) -> None:
        """Without an authored list heading, nothing is generated."""
        tree = _figure_tree(chapters=True)
        doc, _ = vertex_tree_to_pandoc(tree, _assets(), {})
        prepared = prepare_floats(doc, tree, BookProfile().structural_policy)
        before = pandoc_to_json(doc)
        insert_float_lists(doc, tree, prepared.numbers, OutputFormat.EPUB)
        assert pandoc_to_json(doc) == before
