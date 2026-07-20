"""Shared tree-loading pipeline for Roam Research CLI commands.

Public symbols:

- :class:`SemanticsValidationError` — raised when strict semantics validation rejects the
  transcribed content.
- :class:`CodeSourceVerificationError` — raised when strict code-source verification rejects
  the transcribed content.
- :func:`fetch_roam_trees` — fetch nodes for a :class:`~guffin.roam.node_fetch_result.NodeFetchSpec`
  and return a :class:`~guffin.roam.node_fetch_result.NodeFetchResult` paired with an optional
  :class:`~guffin.vertex_tree.VertexTree`, gated by semantics validation and optional
  code-source verification, ready for rendering or further processing.
- :func:`deduce_out_file_stem` — derive a shell-safe output filename stem (suffixed with the
  project type) from a :class:`~guffin.model.vertex_tree.VertexTree`'s root vertex.
- :func:`resolve_profile` — build the :class:`~guffin.render.project.ProjectProfile` for a project
  type, refined by the content (a book with part-tagged level-1 headings becomes a parts book).
"""

import logging
import textwrap
from typing import Final

from pydantic import validate_call

from guffin.cli import code_source_verification
from guffin.common.filenames import shell_safe_filename
from guffin.common.markdown import unwrap_links
from guffin.common.validation import ValidationResult
from guffin.model.code_source_diagnosis import CodeSourceFinding
from guffin.model.publishing_semantics import (
    effective_title,
    has_parts,
    revision_of_vertex,
)
from guffin.model.publishing_validation import validate_semantics
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree, root_vertex
from guffin.render.project import BookProfile, ProjectProfile, ProjectType, profile_for
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import FetchRoamNodes
from guffin.roam.node_fetch_result import NodeFetchResult, NodeFetchSpec
from guffin.roam.node_tree import NodeTree
from guffin.roam.revision import gather_revision
from guffin.transcribe.roam_tree_to_guffin import to_render_bundle

logger = logging.getLogger(__name__)


class SemanticsValidationError(Exception):
    """Raised when strict semantics validation rejects the transcribed content.

    Attributes:
        result: The :class:`~guffin.common.validation.ValidationResult` whose errors caused the
            rejection.
    """

    def __init__(self, result: ValidationResult) -> None:
        """Store the full validation result for inspection by callers."""
        super().__init__("guffin semantics validation failed: " + "; ".join(str(e) for e in result.errors))
        self.result: ValidationResult = result


class CodeSourceVerificationError(Exception):
    """Raised when strict code-source verification rejects the transcribed content.

    Attributes:
        findings: Every :class:`~guffin.model.code_source_diagnosis.CodeSourceFinding`
            accumulated across the verified content.
    """

    def __init__(self, findings: tuple[CodeSourceFinding, ...]) -> None:
        """Store the accumulated findings for inspection by callers."""
        super().__init__(f"code-source verification failed: {len(findings)} code block(s) with findings")
        self.findings: Final[tuple[CodeSourceFinding, ...]] = findings


def _gate_code_sources(content: VertexTree, strict: bool, verify_code_sources: bool) -> None:
    """Run the code-source gate over *content* at the caller's *strict* posture.

    A no-op when *verify_code_sources* is unset (the gate stands open — the offline path).
    Otherwise verifies every sourced, render-visible code block against GitHub
    (:func:`guffin.cli.code_source_verification.verify_code_sources`).  Under the strict
    posture any findings raise; otherwise each finding is logged as a warning and the gate
    passes.

    Args:
        content: The transcribed :class:`~guffin.model.vertex_tree.VertexTree` to verify.
        strict: The caller's strictness posture.
        verify_code_sources: Whether to run the gate at all.

    Raises:
        CodeSourceVerificationError: If *strict* and *verify_code_sources* are set and any
            sourced code block fails verification.
    """
    if not verify_code_sources:
        return
    findings: Final[tuple[CodeSourceFinding, ...]] = code_source_verification.verify_code_sources(content)
    if strict and findings:
        raise CodeSourceVerificationError(findings)
    for finding in findings:
        logger.warning(
            "code-source verification [%s] vertex uid=%r (%s): %s",
            finding.diagnosis.value,
            finding.uid,
            finding.url,
            finding.detail,
        )


@validate_call
def fetch_roam_trees(
    fetch_spec: NodeFetchSpec,
    include_vertex_tree: bool,
    api_endpoint: ApiEndpoint,
    strict: bool = False,
    verify_code_sources: bool = False,
) -> tuple[NodeFetchResult, RenderBundle | None]:
    """Fetch Roam nodes for *fetch_spec* and build a gated node tree and render bundle.

    Fetches :class:`~guffin.roam.node.RoamNode` records for *fetch_spec* via
    *api_endpoint*, constructs a :class:`~guffin.roam.node_tree.NodeTree`, and optionally
    transcribes it into a :class:`~guffin.model.render_bundle.RenderBundle` (its
    :class:`~guffin.model.vertex_tree.VertexTree` content paired with the presentation
    :data:`~guffin.model.vertex_view.ViewMap`) via :func:`~guffin.transcribe.roam_tree_to_guffin.to_render_bundle`.

    The transcribed content then passes through the pipeline's gates.  Semantics validation
    (:func:`~guffin.model.publishing_validation.validate_semantics`) always runs; code-source
    verification (:func:`guffin.cli.code_source_verification.verify_code_sources` — a network
    check against GitHub) runs when *verify_code_sources* is set.  How a gate's findings are
    handled depends on the caller's *strict* posture: logged as warnings (``False``), or
    raised (``True``) as a :class:`SemanticsValidationError` /
    :class:`CodeSourceVerificationError`.

    Propagates any exception raised during fetching or transcription; callers are
    responsible for exit behaviour.

    Args:
        fetch_spec: The fetch specification carrying the anchor, include_refs flag, and
            include_node_tree flag.
        include_vertex_tree: When ``True``, builds the :class:`~guffin.model.render_bundle.RenderBundle`
            (content + view) and returns it as the second element of the pair.  When ``False``,
            skips transcription (and every content gate) and returns ``None`` instead.
        api_endpoint: Configured API endpoint used to fetch nodes.
        strict: The caller's strictness posture, applied to every gate.  When ``True``, a
            gate's findings raise; when ``False`` (default), they are logged as warnings and
            the fetch succeeds.
        verify_code_sources: When ``True``, verify every ``code-source::``-tagged code block
            against GitHub; when ``False`` (default), skip the network check entirely.

    Returns:
        A ``(fetch_result, render_bundle)`` pair ready for rendering or further processing.
        ``render_bundle`` is ``None`` when *include_vertex_tree* is ``False``.

    Raises:
        SemanticsValidationError: If *strict* is set and the transcribed content violates
            any guffin vocabulary invariant.
        CodeSourceVerificationError: If *strict* and *verify_code_sources* are set and any
            sourced code block fails verification.
    """
    result: Final[NodeFetchResult] = FetchRoamNodes.fetch_roam_nodes(
        anchor=fetch_spec.anchor,
        api_endpoint=api_endpoint,
        include_refs=fetch_spec.include_refs,
        include_node_tree=fetch_spec.include_node_tree or include_vertex_tree,
    )

    if not include_vertex_tree:
        logger.debug("result=%r", result)
        return result, None

    assert (
        result.anchor_tree is not None
    ), "anchor_tree is None; fetch_spec has include_node_tree=False, which is unsupported here"
    anchor_tree: Final[NodeTree] = result.anchor_tree
    transcribed: Final[RenderBundle] = to_render_bundle(anchor_tree)
    validation_result: Final[ValidationResult] = validate_semantics(transcribed.content)
    if strict and not validation_result.is_valid:
        raise SemanticsValidationError(validation_result)
    # Without the strict posture, vocabulary violations are advisory: surfaced loudly but never
    # failing the fetch — a misplaced tag simply has no effect.
    for validation_error in validation_result.errors:
        logger.warning("guffin semantics validation: %s", validation_error)
    _gate_code_sources(transcribed.content, strict, verify_code_sources)
    # The content revision is captured on every fetch: the snapshot hash and edit bookkeeping
    # come from the raw wire response, the optional revision name from the root vertex's
    # authored revision:: attribute.  Emission stays a renderer decision (the colophon).
    revision_name: Final[str | None] = revision_of_vertex(root_vertex(transcribed.content))
    render_bundle: Final[RenderBundle] = transcribed.with_revision(gather_revision(result.raw_result, revision_name))
    logger.debug("node_tree=%r\n\nrender_bundle=%r", anchor_tree, render_bundle)
    return result, render_bundle


@validate_call
def deduce_out_file_stem(vertex_tree: VertexTree, project_type: ProjectType) -> str:
    """Derive a filename stem for the export output from *vertex_tree*'s effective title.

    The stem basis is *vertex_tree*'s
    :func:`~guffin.model.publishing_semantics.effective_title` — a root ``title`` assignment,
    else a page root's title, else a basis from the root's own content (block text, image
    alt-text/filename/source, callout title-or-body, code, the first table row's cells joined
    by ``_``, or, for a block embed, the transcluded target's title).  Markdown links in the
    basis are unwrapped to their text (so a rendered page reference contributes only its text,
    not the URL), then the basis is shortened to 40 characters and normalised to a POSIX-safe
    filename.  Finally, ``.<project_type>`` is appended so that exports of the same target under
    different project types land in distinct files (e.g. ``Foo.book``, ``Foo.manuscript``).

    Args:
        vertex_tree: The transcribed tree whose effective title supplies the stem basis.
        project_type: The project type whose value is appended as a ``.<type>`` segment.

    Returns:
        A shell-safe filename stem of the form ``<basis>.<project_type>`` (no format
        extension or directory component); the renderer appends the format extension.
    """
    basis: Final[str] = effective_title(vertex_tree)
    unwrapped_basis: Final[str] = unwrap_links(basis)
    # The clip marker deliberately ends in "_" (retained by shell_safe_filename, which strips
    # only leading underscores) so that an appended extension reads "..._.pdf" — a distinctive,
    # non-dot ending — rather than a run of dots "....pdf".
    clipped_basis: Final[str] = textwrap.shorten(unwrapped_basis, width=40, placeholder="..._")
    return f"{shell_safe_filename(clipped_basis)}.{project_type.value}"


@validate_call
def resolve_profile(project_type: ProjectType, content: VertexTree) -> ProjectProfile:
    """Build the :class:`~guffin.render.project.ProjectProfile` for *project_type* and *content*.

    Starts from :func:`~guffin.render.project.profile_for`'s default-valued profile, then lets the
    content refine it: a book whose *content* declares parts (any level-1 heading tagged
    ``element-type:: part`` — see :func:`~guffin.model.publishing_semantics.has_parts`) becomes a parts book
    (:attr:`~guffin.render.project.BookProfile.with_parts`), so its level-2 headings are treated as
    the chapters.  Other project types pass through unchanged.

    Args:
        project_type: The kind of work to build a profile for.
        content: The transcribed content the profile will describe.

    Returns:
        The resolved :class:`~guffin.render.project.ProjectProfile`.
    """
    base_profile: Final[ProjectProfile] = profile_for(project_type)
    if isinstance(base_profile, BookProfile) and has_parts(content):
        logger.info("level-1 part heading detected; using the parts book layout (chapters at level 2)")
        return base_profile.model_copy(update={"with_parts": True})
    return base_profile
