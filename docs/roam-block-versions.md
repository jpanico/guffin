# Roam Block Versions

Roam's built-in **Block Versions** feature lets one block hold several alternative
texts, with exactly one shown at a time. In the UI a versioned block carries a small
version selector, and keyboard shortcuts add a version, cycle between them, or expand
them all into ordinary sibling blocks. This document records how the feature is stored
in the graph, what the storage means for guffin's fetch pipeline, and why the feature
can only be exercised through the Roam UI. The findings were verified empirically
against a live graph (October 2026) and are backed by the `[[Test Article]] 0`
fixtures, whose `block 3.4` holds a block with three versions.

Roam's own name for the feature is **Version Control**, which is where the `vc`
attribute namespace below comes from. The official help page,
[Version Control](https://roamresearch.com/#/app/help/page/JsFdrvAde) in the public
`help` graph, is two sentences and a demo block: it says the feature "helps you create
different versions of the same block" for multiple drafts, and shows a three-version
example. Nothing there describes the storage, which is why this document exists.

See [roam-querying.md](roam-querying.md) for the Datalog background and
[roam-schema.md](roam-schema.md) for the full attribute table.

## Storage model

A "block with three versions" is not one block with three strings. It is **three
independent block entities plus one small grouping entity**:

| Entity | Attributes |
|---|---|
| version block (×3) | the ordinary block set — `:block/uid`, `:block/string`, `:block/order`, `:block/open`, `:block/page`, `:block/parents`, `:create/*`, `:edit/*`, plus `:block/refs` / `:block/props` / `:block/children` when the text warrants them |
| version group (×1) | `:block/uid` and `:vc/blocks` — nothing else |

### The version blocks

Each version is a complete, self-standing block. It has its own uid, string, create
and edit times, and user, and it can carry references and children of its own. All of
a block's versions share the **same `:block/order`**, and each one's `:block/page` and
`:block/parents` point at the host page and parent exactly as a normal child's would.
Looking at any one version in isolation, nothing distinguishes it from an ordinary
block at that position.

### The version group

The group entity is minimal: a `:block/uid` (so it can be addressed) and a
cardinality-many reference attribute **`:vc/blocks`** listing every version block. It
has no string, no page, no parents, no order, no timestamps, and no props. The
`vc` namespace is the only place the feature surfaces in the schema. The schema's
`version/*` attributes (`version/id`, `version/nonce`, `version/upgraded-nonce`) are
unrelated: they are Roam's graph-migration version records.

The version blocks carry **no forward attribute** back to their group. The only path
from a block to its group is the reverse reference `:vc/_blocks`.

### Selection lives in the parent's children

The selected version is encoded by the parent's **`:block/children`** set and nowhere
else. The parent's children ref points at exactly one of the versions, the selected
one. The unselected versions are in **no** `:block/children` set anywhere in the graph:
they keep their `:block/page` and `:block/parents` links intact but dangle from the
tree.

Cycling versions in the UI swaps which entity the parent's children ref points at.
The transaction Roam issues when a block *becomes* a version was observed in the
client's sync log, and it is as small as the model suggests: retract the parent's
`:block/children` ref to the block, set the block's `:block/order` to its sibling
version's, and assert a new group entity with a `:block/uid` and a `:vc/blocks` ref to
each version. The cycle and expand transactions were not captured, but the model
leaves them little room: cycling must move the parent's children ref, and expanding
must re-attach every version as an ordinary sibling.

### Display order

The UI presents versions in creation order, which coincides with entity-id order.
DataScript stores `:vc/blocks` as an unordered set, so the ordering is applied at
display time; which key Roam sorts on (entity id or create time) was not determined.

## Worked example

`[[Test Article]] 0`, `block 3.4`, holds a child block with three versions. The
Datalog below pulls the group through the reverse reference and shows, per version,
whether a parent's children ref selects it:

```clojure
[:find (pull ?v [:block/uid
                 {:vc/blocks [:block/uid :block/string :block/order
                              {:block/_children [:block/uid]}]}])
 :where [?b :block/uid "PUrwWBbbi"]
        [?v :vc/blocks ?b]]
```

Result (abbreviated; the Local API strips the namespaces from the keys):

```yaml
uid: e9j_vHjGQ                       # the group: uid + vc/blocks only
blocks:
- uid: PUrwWBbbi                      # version 1
  string: This block has 3 versions. This is __version 1__.
  order: 0
- uid: zHbMF7Ozq                      # version 2
  string: This block has 3 versions. This is **version 2**.
  order: 0
- uid: YYysqBFqy                      # version 3 — the selected one
  string: This block has 3 versions. This is version 3.
  order: 0
  _children:
  - uid: xPUIusgqA                    # block 3.4, the parent
```

All three share order 0 under the same parent; only version 3 appears in that
parent's `:block/children`.

## What guffin sees

guffin's node fetch (`roam/node_fetch.py`) collects a page's blocks by walking
`:block/children` transitively from the anchor, and its `[*]` pull pattern returns no
reverse references. Two consequences follow:

- **Only the selected version is fetched.** A fetch of a page containing a versioned
  block sees one ordinary block at that position, the selected version, and never
  learns the other versions exist. The export renders the selected version silently,
  which is the sensible default.
- **Nothing marks the block as versioned.** The `:vc/_blocks` reverse ref never
  reaches the wire, so neither the fixtures nor the model carry any trace of the group.
  The `[[Test Article]] 0` fixtures confirm this: no unselected version's uid and no
  group uid appears in any of the six files.

That was the state of play until the fetch queries were taught to follow the group,
as the next section describes. The tree-building and transcription stages still behave
exactly as above: the anchor tree is extracted by walking `:block/children`, so the
unselected versions never enter it and the export still renders the selected version
alone. What changed is that the versions now *arrive*, in the flat node network, where
a consumer can find them.

## Fetching the versions

The `FetchRoamNodes.Request` queries (`roam/node_fetch.py`) return, for every node in
scope of a fetch, its sibling versions as well, and stamp every version block with its
group's uid. Verified live against `[[Test Article]] 0`.

### The pivot

For a node `?member` the fetch would return anyway, its versions are one hop away
through the reverse of `:vc/blocks`. One extra `or-join` branch covers it:

```clojure
(and (in-scope ?anchor ?member)
     [?group :vc/blocks ?member]
     [?group :vc/blocks ?node])     ; every sibling version, ?member itself included
```

Run against `[[Test Article]] 0`, the branch adds exactly the two unselected versions
to the fetch: the selected one was already in scope through the parent's children, and
the branch yields it again, which the `or-join` deduplicates. With `?member` bound, the
`[?group :vc/blocks ?member]` clause is a VAET index probe, so an unversioned graph pays
almost nothing for the branch.

### Scope lives in the rules

"Every node in scope" means every branch of the with-refs fetch, including blocks
reached through first- and second-hop references. Appending a version branch to each of
its six `or-join` branches would have doubled them to twelve. Instead, the scope moved
out of the query and into an `in-scope` rule in the rules vector:

```clojure
[(in-scope ?anchor ?node) [(identity ?anchor) ?node]]
[(in-scope ?anchor ?node) (descendant ?anchor ?node)]
[(in-scope ?anchor ?node) (page-ref ?anchor ?node)]
;; … one clause per former or-join branch
```

so each query's `or-join` has two branches, `(in-scope ?anchor ?node)` and the pivot,
and the with-refs choice selects the rules vector: `SCOPE_RULES` (anchor plus
descendants, two clauses) or `SCOPE_WITH_REFS_RULES` (six clauses). There is now one
query per anchor kind, `BY_PAGE_TITLE_QUERY` and `BY_NODE_UID_QUERY`. The `or-join`
scoping rule still applies: `?anchor` stays in the join-variable list and is re-bound
inside each branch, or the pivot would match every versioned block in the graph.

### The group is a row, and rides on the versions too

The pivot joins through the group entity, and the `raw_result` design principle
([roam-querying.md](roam-querying.md#raw_result-is-a-faithful-picture-of-the-database))
requires every entity a fetch joins through to be a row. So a third `or-join` branch
returns it:

```clojure
(and (in-scope ?anchor ?member)
     [?node :vc/blocks ?member])    ; the group entity itself
```

On the wire the group row is `uid`, `id`, and `blocks` (the namespace-stripped
`:vc/blocks`), a list of id stubs naming the versions. The schema has no other `blocks`
attribute, so the stripped key is unambiguous. It parses as a `RoamNode` of the third
entity kind, **version group**: `title` and `string` are `None`, `blocks` is set, and
`node_type` classifies it as `NodeType.VERSION_GROUP`. It has no `page` or `parents`, so
it sits in the fetched network without belonging to any tree, and the transcriber refuses
to make a vertex of it, since it has no content of its own.

The group's uid also rides on each version block, through a reverse reference in the
shared pull pattern:

```clojure
[* … {(:vc/_blocks :as "version-group") [:block/uid]}]
```

Every version of a versioned block, the selected one included, arrives with
`"version-group": [{"uid": "<group uid>"}]`; a block that is not versioned carries no
such key, because a reverse reference with no match is omitted from the pull. The two
views are complementary: the group row answers "which blocks are the versions" in one
place, and the stub answers "is this block versioned, and by what" without a scan.
Pulling only a uid stub keeps the rows flat; nesting the sibling versions themselves
inside each row (`{:vc/_blocks [{:vc/blocks [*]}]}`) would have broken the flat-rows
contract the raw-result parsing and every recorded fixture rely on.

### What arrives downstream

- **Version rows parse as ordinary nodes.** They carry page and parents but sit in no
  `:block/children` set, so `NodeTree.build` never reaches them and `nodes_by_uid` is
  where they land. The `all_children_present` / `all_parents_present` validators pass,
  since the parent they name is present. The `[[Test Article]] 0` fixtures show it:
  the two unselected versions and the group row appear in `nodes_by_uid` and
  `raw_result`, and nowhere else.
- **The group row is a `VERSION_GROUP` node.** Its `blocks` field holds the id stubs of
  the versions, so "which blocks are the versions of this group" is answered by the row
  itself. The `version-group` stub on each version is on the wire only; `RoamNode`
  ignores unknown keys, so it is visible in `raw_result` until a field is added for it,
  which is for the consuming feature to decide.
- **Selection stays derivable.** Nothing on the group says which version is selected;
  the selected one is the version present in the parent's `:block/children`, so the
  model can compute it from data it already holds.
- **The revision snapshot moves** when someone edits an unselected version, because the
  hash covers every fetched row. That is correct: the page's content did change.

## No API creates a version

There is no programmatic way to create, select, or expand versions:

- `window.roamAlphaAPI` exposes no versions method, so neither the Local API (which
  proxies Alpha API method paths) nor the Roam MCP server can do it.
- The feature exists in the client only as hotkey-bound commands:
  `expand-versions`, `cycle-version-left`, `cycle-version-right`,
  `collapse-selected-into-versions`, and `version-control`. None is invocable from
  outside the UI.

Creating a versioned test block therefore means a person doing it in the Roam UI. On
macOS the default bindings are:

| Action | Shortcut |
|---|---|
| Add a new version of the block | Ctrl-, |
| Cycle to the next version (right) | Ctrl-Shift-. |
| Cycle to the previous version (left) | Ctrl-Shift-, |
| Expand all versions into separate blocks | Ctrl-. |

The surrounding structure (the parent block, the first version's text) can be created
through the API as usual; only the versioning step is manual.
