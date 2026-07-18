"""Roam Research Datomic schema model types.

Public symbols:

- :class:`SchemaNamespace` — enumeration of all Datomic attribute namespaces present
  in the Roam graph schema.
- :class:`SchemaAttribute` — enumeration of all ``(namespace, attr_name)`` pairs
  in the Roam Datomic schema.
- :data:`INTERMITTENT_ATTRIBUTES` — the :class:`SchemaAttribute` members that are fully
  retracted when inactive, so they may legitimately be absent from a live schema fetch.
- :data:`RoamSchema` — a list of :class:`SchemaAttribute` members representing the
  full schema of a live Roam graph.
"""

from enum import Enum, StrEnum
from typing import Final


class SchemaNamespace(StrEnum):
    """Enumeration of all Datomic attribute namespaces in the Roam graph schema.

    Each member's value is the namespace string as it appears in the Datomic schema
    (e.g. ``"block"``, ``"create"``, ``"user"``).  Because this is a :class:`StrEnum`,
    members compare equal to their string equivalents::

        assert SchemaNamespace.BLOCK == "block"
    """

    ANNOTATION = "annotation"
    ATTRS = "attrs"
    BLOCK = "block"
    CHILDREN = "children"
    CREATE = "create"
    EDIT = "edit"
    ENTITY = "entity"
    GRAPH = "graph"
    LOG = "log"
    NODE = "node"
    PAGE = "page"
    PDF = "pdf"
    RESTRICTIONS = "restrictions"
    TOKEN = "token"
    USER = "user"
    VC = "vc"
    VERSION = "version"
    WINDOW = "window"


class SchemaAttribute(Enum):
    """Enumeration of all ``(namespace, attr_name)`` pairs in the Roam Datomic schema.

    Each member's :attr:`value` is a ``tuple[SchemaNamespace, str]``.  Typed accessors
    :attr:`namespace` and :attr:`attr_name` expose the two components without
    requiring callers to unpack :attr:`value` manually::

        assert SchemaAttribute.BLOCK_UID.namespace is SchemaNamespace.BLOCK
        assert SchemaAttribute.BLOCK_UID.attr_name == "uid"
    """

    value: tuple[SchemaNamespace, str]  # type: ignore[override]

    # annotation/
    ANNOTATION_ORIGIN = (SchemaNamespace.ANNOTATION, "origin")

    # attrs/
    ATTRS_LOOKUP = (SchemaNamespace.ATTRS, "lookup")

    # block/
    BLOCK_CHILDREN = (SchemaNamespace.BLOCK, "children")
    BLOCK_HEADING = (SchemaNamespace.BLOCK, "heading")
    BLOCK_OPEN = (SchemaNamespace.BLOCK, "open")
    BLOCK_ORDER = (SchemaNamespace.BLOCK, "order")
    BLOCK_PAGE = (SchemaNamespace.BLOCK, "page")
    BLOCK_PARENTS = (SchemaNamespace.BLOCK, "parents")
    BLOCK_PROPS = (SchemaNamespace.BLOCK, "props")
    BLOCK_REFS = (SchemaNamespace.BLOCK, "refs")
    BLOCK_STRING = (SchemaNamespace.BLOCK, "string")
    BLOCK_TEXT_ALIGN = (SchemaNamespace.BLOCK, "text-align")
    BLOCK_UID = (SchemaNamespace.BLOCK, "uid")
    BLOCK_VIEW_TYPE = (SchemaNamespace.BLOCK, "view-type")

    # children/
    CHILDREN_VIEW_TYPE = (SchemaNamespace.CHILDREN, "view-type")

    # create/
    CREATE_TIME = (SchemaNamespace.CREATE, "time")
    CREATE_USER = (SchemaNamespace.CREATE, "user")

    # edit/
    EDIT_SEEN_BY = (SchemaNamespace.EDIT, "seen-by")
    EDIT_TIME = (SchemaNamespace.EDIT, "time")
    EDIT_USER = (SchemaNamespace.EDIT, "user")

    # entity/
    ENTITY_ATTRS = (SchemaNamespace.ENTITY, "attrs")

    # graph/
    GRAPH_SETTINGS = (SchemaNamespace.GRAPH, "settings")

    # log/
    LOG_ID = (SchemaNamespace.LOG, "id")

    # node/
    NODE_TITLE = (SchemaNamespace.NODE, "title")

    # page/
    PAGE_SIDEBAR = (SchemaNamespace.PAGE, "sidebar")
    PAGE_DIRTY = (SchemaNamespace.PAGE, "dirty?")
    PAGE_EDIT_USER = (SchemaNamespace.PAGE, "edit-user")
    PAGE_EDIT_NONCE = (SchemaNamespace.PAGE, "edit-nonce")
    PAGE_EDIT_TIME = (SchemaNamespace.PAGE, "edit-time")
    PAGE_WORD_COUNT = (SchemaNamespace.PAGE, "word-count")

    # pdf/
    PDF_FINGERPRINTS = (SchemaNamespace.PDF, "fingerprints")
    PDF_URL = (SchemaNamespace.PDF, "url")

    # restrictions/
    RESTRICTIONS_PREVENT_CLEAN = (SchemaNamespace.RESTRICTIONS, "prevent-clean")

    # token/
    TOKEN_AI = (SchemaNamespace.TOKEN, "ai")
    TOKEN_CREATED_BY_UID = (SchemaNamespace.TOKEN, "created-by-uid")
    TOKEN_DESCRIPTION = (SchemaNamespace.TOKEN, "description")
    TOKEN_DEVICE_NAME = (SchemaNamespace.TOKEN, "device-name")
    TOKEN_TYPE = (SchemaNamespace.TOKEN, "type")

    # user/
    USER_DISPLAY_NAME = (SchemaNamespace.USER, "display-name")
    USER_DISPLAY_PAGE = (SchemaNamespace.USER, "display-page")
    USER_PHOTO_URL = (SchemaNamespace.USER, "photo-url")
    USER_SETTINGS = (SchemaNamespace.USER, "settings")
    USER_UID = (SchemaNamespace.USER, "uid")

    # vc/
    VC_BLOCKS = (SchemaNamespace.VC, "blocks")

    # version/
    VERSION_ID = (SchemaNamespace.VERSION, "id")
    VERSION_NONCE = (SchemaNamespace.VERSION, "nonce")
    VERSION_UPGRADED_NONCE = (SchemaNamespace.VERSION, "upgraded-nonce")

    # window/
    WINDOW_ID = (SchemaNamespace.WINDOW, "id")
    WINDOW_FILTERS = (SchemaNamespace.WINDOW, "filters")
    WINDOW_MENTIONS_STATE = (SchemaNamespace.WINDOW, "mentions-state")

    def __init__(self, namespace: SchemaNamespace, attr_name: str) -> None:
        """Bind typed accessors from the ``(namespace, attr_name)`` member value."""
        self.namespace: SchemaNamespace = namespace
        self.attr_name: str = attr_name

    def __str__(self) -> str:
        """Return the Datomic attribute key, e.g. ``:block/uid``."""
        return f":{self.namespace}/{self.attr_name}"


INTERMITTENT_ATTRIBUTES: Final[frozenset[SchemaAttribute]] = frozenset({SchemaAttribute.PAGE_DIRTY})
"""The :class:`SchemaAttribute` members that may legitimately be absent from a live schema fetch.

Roam's schema introspection query reports only attributes with at least one currently asserted
datom.  Most attributes are always asserted on some entity, but an *intermittent* attribute is
asserted only while its condition holds and fully retracted afterwards, so it flickers in and out
of the live schema depending on graph state at fetch time — e.g. ``:page/dirty?`` marks a page
with pending unsynced changes and disappears once the page syncs clean.
"""


type RoamSchema = list[SchemaAttribute]
"""Roam Datomic schema as a list of :class:`SchemaAttribute` members.

Each member corresponds to one row from the ``[:find ?namespace ?attr ...]``
schema query, e.g. :attr:`SchemaAttribute.BLOCK_UID`.
"""
