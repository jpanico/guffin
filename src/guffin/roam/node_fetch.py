"""Roam Research 'Node' fetching via the Local API.

Public symbols:

- :exc:`RoamNodeNotFoundError` — raised when no Roam nodes match the requested
  page title or node UID.
- :class:`FetchRoamNodes` — stateless utility class that fetches all Roam nodes
  by various criteria via the Local API's ``data.q`` action, including
  :meth:`~FetchRoamNodes.fetch_roam_nodes` which auto-detects whether *anchor*
  is a page title or a node UID.
"""

import logging
import textwrap
from typing import Final, final

from pydantic import BaseModel, ConfigDict, ValidationError, validate_call

from guffin.roam.local_api import (
    ApiEndpoint,
    invoke_action,
)
from guffin.roam.local_api import (
    Request as LocalApiRequest,
)
from guffin.roam.local_api import (
    Response as LocalApiResponse,
)
from guffin.roam.node import RoamNode
from guffin.roam.node_fetch_result import (
    NodeFetchAnchor,
    NodeFetchResult,
    NodeFetchSpec,
    QueryAnchorKind,
)
from guffin.roam.node_network import NodeNetwork
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)


class RoamNodeNotFoundError(Exception):
    """Raised when no Roam nodes match the requested page title or node UID."""

    def __init__(self, fetch_spec: NodeFetchSpec) -> None:
        """Store the full fetch specification for inspection by callers."""
        super().__init__(f"no nodes found for fetch_spec={fetch_spec!r}")
        self.fetch_spec: NodeFetchSpec = fetch_spec


@final
class FetchRoamNodes:
    """Stateless utility class for fetching Roam nodes by various criteria from the Roam Research Local API.

    Executes a Datalog query via the Local API's ``data.q`` action, which proxies
    ``roamAlphaAPI.data.q`` through the Roam Desktop app's local HTTP server.
    """

    def __init__(self) -> None:
        """Prevent instantiation of this stateless utility class."""
        raise TypeError("FetchRoamNodes is a stateless utility class and cannot be instantiated")

    class Request:
        """Namespace for the ``data.q`` request.

        All queries in this namespace use ``(pull ?node [*])`` in their ``:find`` clause.
        The ``pull [*]`` wildcard fetches every DataScript attribute present on each matched
        entity, including ``:block/props`` — the block property key-value map populated by
        Roam extensions such as Augmented Headings (e.g. ``ah-level: h4``).  Block
        properties only appear in the result when they have actually been set on a given
        block; absent block properties are silently omitted, and
        :attr:`~guffin.roam.node.RoamNode.props` will be ``None`` for those nodes.

        **Anchor node**: each query opens with a single data pattern clause that binds a
        variable named ``?anchor`` to the node whose attribute matches the caller-supplied
        input variable (``?title`` for page-title queries, ``?uid`` for node-UID queries).
        All subsequent traversal — descendants via ``(descendant ?anchor ?node)`` and page
        references via ``(page-ref ?anchor ?node)`` — radiates outward from ``?anchor``.
        The ``or-join`` join-variable list always includes ``?anchor`` to ensure Datomic
        treats it as the outer binding rather than a fresh free variable.
        """

        _DESCENDANT_CLAUSES: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                [(descendant ?parent ?child)
                    [?parent :block/children ?child]]
                [(descendant ?parent ?child)
                    [?parent :block/children ?mid]
                    (descendant ?mid ?child)]"""),
            "    ",
        )
        _PAGE_REF_CLAUSES: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                [(page-ref ?root ?node)
                    [?root :block/refs ?node]]
                [(page-ref ?root ?node)
                    (descendant ?root ?member)
                    [?member :block/refs ?node]]"""),
            "    ",
        )
        DESCENDANT_RULE: Final[str] = f"[\n{_DESCENDANT_CLAUSES}\n]"
        """Datalog rules vector defining a recursive transitive closure over ``:block/children``.

        Query constants that reference ``(descendant ?parent ?child)`` pass this vector as
        the ``%`` rules binding to resolve the rule at query time.
        """

        PAGE_REF_RULE: Final[str] = f"[\n{_PAGE_REF_CLAUSES}\n]"
        """Datalog rules vector defining the ``page-ref`` rule for ``:block/refs`` traversal.

        ``(page-ref ?root ?node)`` is satisfied when ``?node`` is referenced directly by
        ``?root`` via ``:block/refs`` (clause 1), or when ``?node`` is referenced via
        ``:block/refs`` by any descendant of ``?root`` (clause 2).

        **Dependency**: the second clause calls ``(descendant ?root ?member)``, so
        ``PAGE_REF_RULE`` cannot be used as a standalone rules vector.  Always combine it
        with :attr:`DESCENDANT_RULE` by passing :attr:`DESCENDANT_AND_PAGE_REF_RULES` as the
        ``%`` binding instead.
        """

        DESCENDANT_AND_PAGE_REF_RULES: Final[str] = f"[\n{_DESCENDANT_CLAUSES}\n{_PAGE_REF_CLAUSES}\n]"
        """Combined Datalog rules vector containing both :attr:`DESCENDANT_RULE` and :attr:`PAGE_REF_RULE` clauses.

        Pass this as the ``%`` rules binding for any query that uses both ``(descendant ...)``
        and ``(page-ref ...)``.  Because ``PAGE_REF_RULE`` depends on ``descendant``, the two
        rule sets must be shipped together in a single vector.
        """

        _BY_PAGE_TITLE_QUERY_BASE: Final[str] = textwrap.dedent("""\
            [:find (pull ?node [*])
             :in $ ?title %
             :where
             [?anchor :node/title ?title]
             (or-join [?anchor ?node]
               (and [?anchor :node/title ?title]
                    [?node :node/title ?title])
               (and [?anchor :node/title ?title]
                    (descendant ?anchor ?node))""")
        _PAGE_REF_OR_JOIN_BRANCH: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                (and [?anchor :node/title ?title]
                     (page-ref ?anchor ?node))"""),
            "   ",
        )
        _REF_DESCENDANT_OR_JOIN_BRANCH: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                (and [?anchor :node/title ?title]
                     (page-ref ?anchor ?ref)
                     (descendant ?ref ?node))"""),
            "   ",
        )
        _REF2_OR_JOIN_BRANCH: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                (and [?anchor :node/title ?title]
                     (page-ref ?anchor ?via)
                     (page-ref ?via ?node))"""),
            "   ",
        )
        BY_PAGE_TITLE_QUERY: Final[str] = f"{_BY_PAGE_TITLE_QUERY_BASE})]"
        """Datalog query fetching a page and all its descendant blocks by page title.

        Input bindings: ``?title`` (page title string) and ``%`` (rules vector —
        :attr:`DESCENDANT_RULE`).

        The ``or-join`` has two branches:

        1. The anchor node itself (``?node = ?anchor``).
        2. Every block reachable from ``?anchor`` through ``:block/children`` at any depth
           (via the ``descendant`` rule).

        ``or-join`` scoping: ``?anchor`` must appear in the join-variable list
        ``[?anchor ?node]`` *and* be re-bound inside each branch.  Variables from the outer
        ``:where`` clause absent from the join-variable list are treated as fresh free
        variables inside the ``or-join`` — not as the outer binding.  Omitting ``?anchor``
        would cause ``(descendant ?anchor ?node)`` to match every descendant pair in the
        entire graph, returning the full database instead of the target subtree.

        To also include nodes referenced via ``:block/refs``, use
        :attr:`BY_PAGE_TITLE_WITH_REFS_QUERY` instead.
        """

        BY_PAGE_TITLE_WITH_REFS_QUERY: Final[str] = (
            f"{_BY_PAGE_TITLE_QUERY_BASE}\n{_PAGE_REF_OR_JOIN_BRANCH}\n"
            f"{_REF_DESCENDANT_OR_JOIN_BRANCH}\n{_REF2_OR_JOIN_BRANCH})]"
        )
        """Datalog query fetching a page, all its descendants, all ``:block/refs`` targets, and their descendants.

        Input bindings: ``?title`` (page title string) and ``%`` (rules vector —
        :attr:`DESCENDANT_AND_PAGE_REF_RULES`).  Must be paired with
        :attr:`DESCENDANT_AND_PAGE_REF_RULES` (not :attr:`DESCENDANT_RULE` alone) because the
        ``page-ref`` rule calls ``(descendant ...)`` internally.

        The ``or-join`` has four branches:

        1. The anchor node itself (``?node = ?anchor``).
        2. Every block reachable from ``?anchor`` through ``:block/children`` at any depth
           (via the ``descendant`` rule).
        3. Every node referenced via ``:block/refs`` from ``?anchor`` directly or from any of
           its descendants (via the ``page-ref`` rule).
        4. Every block reachable through ``:block/children`` from any ``page-ref`` target of the
           anchor — i.e. the full subtree of every referenced node, whether referenced by the anchor
           node itself (e.g. a page-title reference) or by any of its descendants.  Combined with
           branch 3 (which fetches the ref targets themselves), this pulls every referenced block
           together with its full subtree, so referenced multi-block constructs (e.g. a ``{{table}}``)
           arrive complete.
        5. Second-hop ref targets: every node ``page-ref``-reachable from a (first-hop) ``page-ref``
           target of the anchor — i.e. pages referenced by a referenced node's own subtree (e.g. a
           ``tags::`` attribute on a referenced page).  These arrive as bare nodes (no subtree pull),
           bounding fan-out to two ref hops while still letting a referenced node's attributes resolve
           their own page references.
        """

        _BY_NODE_UID_QUERY_BASE: Final[str] = textwrap.dedent("""\
            [:find (pull ?node [*])
             :in $ ?uid %
             :where
             [?anchor :block/uid ?uid]
             (or-join [?anchor ?node]
               (and [?anchor :block/uid ?uid]
                    [?node :block/uid ?uid])
               (and [?anchor :block/uid ?uid]
                    (descendant ?anchor ?node))""")
        _PAGE_REF_OR_JOIN_BRANCH_UID: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                (and [?anchor :block/uid ?uid]
                     (page-ref ?anchor ?node))"""),
            "   ",
        )
        _REF_DESCENDANT_OR_JOIN_BRANCH_UID: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                (and [?anchor :block/uid ?uid]
                     (page-ref ?anchor ?ref)
                     (descendant ?ref ?node))"""),
            "   ",
        )
        _REF2_OR_JOIN_BRANCH_UID: Final[str] = textwrap.indent(
            textwrap.dedent("""\
                (and [?anchor :block/uid ?uid]
                     (page-ref ?anchor ?via)
                     (page-ref ?via ?node))"""),
            "   ",
        )
        BY_NODE_UID_QUERY: Final[str] = f"{_BY_NODE_UID_QUERY_BASE})]"
        """Datalog query fetching a node and all its descendant blocks by ``:block/uid``.

        Input bindings: ``?uid`` (``:block/uid`` string) and ``%`` (rules
        vector — :attr:`DESCENDANT_RULE`).

        The ``or-join`` has two branches:

        1. The anchor node itself (``?node = ?anchor``).
        2. Every block reachable from ``?anchor`` through ``:block/children`` at any depth
           (via the ``descendant`` rule).

        ``or-join`` scoping: ``?anchor`` must appear in the join-variable list
        ``[?anchor ?node]`` *and* be re-bound inside each branch.  Variables from the outer
        ``:where`` clause absent from the join-variable list are treated as fresh free
        variables inside the ``or-join`` — not as the outer binding.  Omitting ``?anchor``
        would cause ``(descendant ?anchor ?node)`` to match every descendant pair in the
        entire graph, returning the full database instead of the target subtree.

        To also include nodes referenced via ``:block/refs``, use
        :attr:`BY_NODE_UID_WITH_REFS_QUERY` instead.
        """

        BY_NODE_UID_WITH_REFS_QUERY: Final[str] = (
            f"{_BY_NODE_UID_QUERY_BASE}\n{_PAGE_REF_OR_JOIN_BRANCH_UID}\n"
            f"{_REF_DESCENDANT_OR_JOIN_BRANCH_UID}\n{_REF2_OR_JOIN_BRANCH_UID})]"
        )
        """Datalog query fetching a node, all its descendants, all ``:block/refs`` targets, and their descendants.

        Input bindings: ``?uid`` (``:block/uid`` string) and ``%`` (rules
        vector — :attr:`DESCENDANT_AND_PAGE_REF_RULES`).  Must be paired with
        :attr:`DESCENDANT_AND_PAGE_REF_RULES` (not :attr:`DESCENDANT_RULE` alone) because the
        ``page-ref`` rule calls ``(descendant ...)`` internally.

        The ``or-join`` has four branches:

        1. The anchor node itself (``?node = ?anchor``).
        2. Every block reachable from ``?anchor`` through ``:block/children`` at any depth
           (via the ``descendant`` rule).
        3. Every node referenced via ``:block/refs`` from ``?anchor`` directly or from any of
           its descendants (via the ``page-ref`` rule).
        4. Every block reachable through ``:block/children`` from any ``page-ref`` target of the
           anchor — i.e. the full subtree of every referenced node, whether referenced by the anchor
           node itself (e.g. a page-title reference) or by any of its descendants.  Combined with
           branch 3 (which fetches the ref targets themselves), this pulls every referenced block
           together with its full subtree, so referenced multi-block constructs (e.g. a ``{{table}}``)
           arrive complete.
        5. Second-hop ref targets: every node ``page-ref``-reachable from a (first-hop) ``page-ref``
           target of the anchor — i.e. pages referenced by a referenced node's own subtree (e.g. a
           ``tags::`` attribute on a referenced page).  These arrive as bare nodes (no subtree pull),
           bounding fan-out to two ref hops while still letting a referenced node's attributes resolve
           their own page references.
        """

        @staticmethod
        def payload_by_page_title(page_title: str, include_refs: bool = False) -> LocalApiRequest.Payload:
            """Build the ``data.q`` request payload for the given page title.

            Args:
                page_title: The exact title of the Roam page to fetch.
                include_refs: When ``True``, uses :attr:`BY_PAGE_TITLE_WITH_REFS_QUERY`
                    paired with :attr:`DESCENDANT_AND_PAGE_REF_RULES` to also pull every node
                    referenced via ``:block/refs`` from the page or any of its descendants.
                    When ``False`` (default), uses :attr:`BY_PAGE_TITLE_QUERY` paired with
                    :attr:`DESCENDANT_RULE` and returns only the page node and its descendants.

            Returns:
                A :class:`~guffin.roam.local_api.Request.Payload` with action ``"data.q"``
                and args set according to *include_refs*.
            """
            query, rules = (
                (
                    FetchRoamNodes.Request.BY_PAGE_TITLE_WITH_REFS_QUERY,
                    FetchRoamNodes.Request.DESCENDANT_AND_PAGE_REF_RULES,
                )
                if include_refs
                else (
                    FetchRoamNodes.Request.BY_PAGE_TITLE_QUERY,
                    FetchRoamNodes.Request.DESCENDANT_RULE,
                )
            )
            return LocalApiRequest.Payload(action="data.q", args=[query, page_title, rules])

        @staticmethod
        def payload_by_node_uid(node_uid: Uid, include_refs: bool = False) -> LocalApiRequest.Payload:
            """Build the ``data.q`` request payload for the given node UID.

            Args:
                node_uid: The ``:block/uid`` of the node to fetch.
                include_refs: When ``True``, uses :attr:`BY_NODE_UID_WITH_REFS_QUERY`
                    paired with :attr:`DESCENDANT_AND_PAGE_REF_RULES` to also pull every node
                    referenced via ``:block/refs`` from the anchor or any of its descendants.
                    When ``False`` (default), uses :attr:`BY_NODE_UID_QUERY` paired with
                    :attr:`DESCENDANT_RULE` and returns only the anchor node and its descendants.

            Returns:
                A :class:`~guffin.roam.local_api.Request.Payload` with action ``"data.q"``
                and args set according to *include_refs*.
            """
            query, rules = (
                (
                    FetchRoamNodes.Request.BY_NODE_UID_WITH_REFS_QUERY,
                    FetchRoamNodes.Request.DESCENDANT_AND_PAGE_REF_RULES,
                )
                if include_refs
                else (
                    FetchRoamNodes.Request.BY_NODE_UID_QUERY,
                    FetchRoamNodes.Request.DESCENDANT_RULE,
                )
            )
            return LocalApiRequest.Payload(action="data.q", args=[query, node_uid, rules])

    class Response:
        """Namespace for ``data.q`` page response types."""

        class Payload(BaseModel):
            """Parsed ``data.q`` response payload (raw wire format)."""

            model_config = ConfigDict(frozen=True)

            success: bool
            result: list[list[RoamNode]]

    @staticmethod
    def _fetch(
        request_payload: LocalApiRequest.Payload, api_endpoint: ApiEndpoint, fetch_spec: NodeFetchSpec
    ) -> NodeFetchResult:
        """Invoke the Local API, validate the response, and return a :class:`NodeFetchResult`.

        Shared implementation used by all public ``fetch_*`` methods.  Callers are
        responsible for building *request_payload* and logging their entry-point
        parameters before calling this method.

        Args:
            request_payload: A fully-constructed ``data.q`` request payload.
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.
            fetch_spec: The fetch specification driving this request; used both for the
                "no nodes found" log message and as the argument to
                :meth:`~guffin.roam.node_fetch_result.NodeFetchResult.from_network`.

        Returns:
            A :class:`~guffin.roam.node_fetch_result.NodeFetchResult` constructed from
            the fetched nodes and *fetch_spec*.

        Raises:
            RoamNodeNotFoundError: If the Datalog query returns no nodes.
            ValueError: If no node in the result matches the anchor in *fetch_spec*.
            requests.exceptions.ConnectionError: If unable to connect to the Local API.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        logger.debug("request_payload=%r, api_endpoint=%r, fetch_spec=%r", request_payload, api_endpoint, fetch_spec)
        local_api_response_payload: Final[LocalApiResponse.Payload] = invoke_action(request_payload, api_endpoint)
        logger.debug("local_api_response_payload: %s", local_api_response_payload)

        # Capture the raw Datalog result before RoamNode parsing; .get() on dict[str, Any]
        # returns Any, which is assignable to the declared list[list[dict[str, object]]] | None.
        raw_result: Final[list[list[dict[str, object]]] | None] = local_api_response_payload.model_dump(
            mode="json"
        ).get("result")

        # Fail fast before expensive RoamNode parsing if the API returned no rows.
        if not raw_result:
            raise RoamNodeNotFoundError(fetch_spec)

        if not fetch_spec.include_node_tree:
            logger.debug("include_node_tree=False; returning raw result without RoamNode parsing")
            return NodeFetchResult.from_raw_result(fetch_spec, raw_result)

        try:
            response_payload: Final[FetchRoamNodes.Response.Payload] = FetchRoamNodes.Response.Payload.model_validate(
                local_api_response_payload.model_dump(mode="json")
            )
        except ValidationError as exc:
            bad_nodes: Final[list[str]] = []
            for err in exc.errors():
                loc: tuple[int | str, ...] = err["loc"]
                if len(loc) >= 3 and loc[0] == "result" and isinstance(loc[1], int) and isinstance(loc[2], int):
                    raw_node: dict[str, object] = raw_result[loc[1]][loc[2]]
                    bad_nodes.append(f"  loc={loc!r} raw_node={raw_node!r}")
            if bad_nodes:
                raise ValueError("RoamNode validation failed; offending node(s):\n" + "\n".join(bad_nodes)) from exc
            raise
        logger.debug("response_payload: %s", response_payload)

        # Datalog :find returns an array-of-arrays; (pull ...) value is at row[0]
        result: Final[list[list[RoamNode]]] = response_payload.result
        network: Final[NodeNetwork] = [row[0] for row in result]
        return NodeFetchResult.from_network(network, fetch_spec, raw_result=raw_result)

    @staticmethod
    @validate_call
    def fetch_by_page_title(fetch_spec: NodeFetchSpec, api_endpoint: ApiEndpoint) -> NodeFetchResult:
        """Fetch all Roam nodes matching the given page title from the Roam Research Local API.

        Because this goes through the Local API, the Roam Research native App must be
        running at the time this method is called, and the user must be logged into the
        graph.

        Args:
            fetch_spec: The fetch specification whose
                :attr:`~guffin.roam.node_fetch_result.NodeFetchSpec.anchor` identifies
                the exact title of the Roam page to fetch, and whose
                :attr:`~guffin.roam.node_fetch_result.NodeFetchSpec.include_refs` controls
                whether ``:block/refs`` targets are included in the result.
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.

        Returns:
            A :class:`~guffin.roam.node_fetch_result.NodeFetchResult` whose
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.anchor_tree` is rooted
            at the matching page node and whose
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.network` contains the
            page node and all its descendant blocks (plus any ``:block/refs`` targets when
            :attr:`~guffin.roam.node_fetch_result.NodeFetchSpec.include_refs` is ``True``).

        Raises:
            ValidationError: If any parameter is ``None`` or invalid.
            ValueError: If ``fetch_spec.anchor.kind`` is not
                :attr:`~guffin.roam.node_fetch_result.QueryAnchorKind.PAGE_TITLE`, or if
                no page matching the title exists in the graph.
            requests.exceptions.ConnectionError: If unable to connect to the Local API.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        logger.debug(
            "api_endpoint: %s, anchor: %r, include_refs: %r",
            api_endpoint,
            fetch_spec.anchor.node_identifier,
            fetch_spec.include_refs,
        )
        if fetch_spec.anchor.kind is not QueryAnchorKind.PAGE_TITLE:
            raise ValueError(
                f"expected fetch_spec.anchor.kind=QueryAnchorKind.PAGE_TITLE; got {fetch_spec.anchor.kind!r}"
            )
        return FetchRoamNodes._fetch(
            FetchRoamNodes.Request.payload_by_page_title(
                fetch_spec.anchor.node_identifier, include_refs=fetch_spec.include_refs
            ),
            api_endpoint,
            fetch_spec,
        )

    @staticmethod
    @validate_call
    def fetch_by_node_uid(fetch_spec: NodeFetchSpec, api_endpoint: ApiEndpoint) -> NodeFetchResult:
        """Fetch the Roam node with the given UID and all its descendants from the Local API.

        Because this goes through the Local API, the Roam Research native App must be
        running at the time this method is called, and the user must be logged into the
        graph.

        Args:
            fetch_spec: The fetch specification whose
                :attr:`~guffin.roam.node_fetch_result.NodeFetchSpec.anchor` identifies
                the ``:block/uid`` of the root node to fetch, and whose
                :attr:`~guffin.roam.node_fetch_result.NodeFetchSpec.include_refs` controls
                whether ``:block/refs`` targets are included in the result.
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.

        Returns:
            A :class:`~guffin.roam.node_fetch_result.NodeFetchResult` whose
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.anchor_tree` is rooted
            at the matched node and whose
            :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.network` contains that
            node and every block reachable through ``:block/children`` at any depth (plus
            any ``:block/refs`` targets when
            :attr:`~guffin.roam.node_fetch_result.NodeFetchSpec.include_refs` is ``True``).

        Raises:
            ValidationError: If any parameter is ``None`` or invalid.
            ValueError: If ``fetch_spec.anchor.kind`` is not
                :attr:`~guffin.roam.node_fetch_result.QueryAnchorKind.NODE_UID`, or if
                no node with the given UID exists in the graph.
            requests.exceptions.ConnectionError: If unable to connect to the Local API.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        logger.debug(
            "api_endpoint: %s, anchor: %r, include_refs: %r",
            api_endpoint,
            fetch_spec.anchor.node_identifier,
            fetch_spec.include_refs,
        )
        if fetch_spec.anchor.kind is not QueryAnchorKind.NODE_UID:
            raise ValueError(
                f"expected fetch_spec.anchor.kind=QueryAnchorKind.NODE_UID; got {fetch_spec.anchor.kind!r}"
            )
        return FetchRoamNodes._fetch(
            FetchRoamNodes.Request.payload_by_node_uid(
                fetch_spec.anchor.node_identifier, include_refs=fetch_spec.include_refs
            ),
            api_endpoint,
            fetch_spec,
        )

    @staticmethod
    def fetch_roam_nodes(
        anchor: NodeFetchAnchor, api_endpoint: ApiEndpoint, include_refs: bool = False, include_node_tree: bool = True
    ) -> NodeFetchResult:
        """Fetch Roam nodes by page title or node UID, dispatching on *anchor* kind.

        Routes to :meth:`fetch_by_node_uid` when
        :attr:`~guffin.roam.node_fetch_result.NodeFetchAnchor.kind` is
        :attr:`~guffin.roam.node_fetch_result.QueryAnchorKind.NODE_UID`, or to
        :meth:`fetch_by_page_title` otherwise.

        Args:
            anchor: The resolved fetch anchor, carrying both the raw string and its kind.
            api_endpoint: The API endpoint (URL + bearer token) for the target Roam graph.
            include_refs: Forwarded to the dispatched fetch method; controls whether
                ``:block/refs`` targets are included in the result.
            include_node_tree: Forwarded to :class:`~guffin.roam.node_fetch_result.NodeFetchSpec`;
                when ``False``, skips :class:`~guffin.roam.node.RoamNode` parsing and returns
                only the raw Datalog result.

        Returns:
            A :class:`~guffin.roam.node_fetch_result.NodeFetchResult` from the
            dispatched fetch method.

        Raises:
            requests.exceptions.ConnectionError: If unable to connect to the Local API.
            requests.exceptions.HTTPError: If the Local API returns a non-200 status.
        """
        fetch_fn = (
            FetchRoamNodes.fetch_by_node_uid
            if anchor.kind is QueryAnchorKind.NODE_UID
            else FetchRoamNodes.fetch_by_page_title
        )
        return fetch_fn(
            fetch_spec=NodeFetchSpec(anchor=anchor, include_refs=include_refs, include_node_tree=include_node_tree),
            api_endpoint=api_endpoint,
        )
