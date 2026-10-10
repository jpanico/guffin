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

An unselected version can still enter a fetch indirectly, if some fetched block
references it by `((uid))`. It then arrives as a block claiming the page as its page
and parent while being absent from that parent's children, which is exactly the shape
the `all_children_present` / `all_parents_present` network validators are there to
catch. This has not been exercised.

Should a feature ever need the unselected versions (say, exporting every version, or
flagging versioned blocks), the fetch queries can be extended to return them; the
design is below. It is deliberately **not implemented**: nothing consumes the versions
today, and the query change is the easy half of the work.

## Fetching the versions (design, not implemented)

The `FetchRoamNodes.Request` queries (`roam/node_fetch.py`) can be extended so that,
for every node a query returns today, its sibling versions and their group entity come
back too. The mechanism was verified live against `[[Test Article]] 0`.

### The pivot

For a node `?member` the query already returns, its versions and group are one hop
away through the reverse of `:vc/blocks`. Two `or-join` branches cover it:

```clojure
(and (in-scope ?anchor ?member)
     [?vc :vc/blocks ?member]
     [?vc :vc/blocks ?node])        ; every sibling version, ?member itself included
(and (in-scope ?anchor ?member)
     [?node :vc/blocks ?member])    ; the group entity
```

Run against `[[Test Article]] 0`, this shape returns exactly four extra rows: the
three version blocks (string, order, and the rest of their attributes) and the group
row, which after namespace stripping is `uid` plus a `blocks` list of the three version
uids. Nothing else, and nothing twice. With `?member` bound, the
`[?vc :vc/blocks ?member]` clause is a VAET index probe, so an unversioned graph pays
almost nothing for the extra branches.

### Factor the existing branches into a rule

"Every node returned today" means every branch of the with-refs query, including
blocks reached through first- and second-hop references. Appending a version branch
to each of its six branches would double them to twelve. Instead, move the existing
branches into an `in-scope` rule in the rules vector:

```clojure
[(in-scope ?anchor ?node) [(identity ?anchor) ?node]]
[(in-scope ?anchor ?node) (descendant ?anchor ?node)]
[(in-scope ?anchor ?node) (page-ref ?anchor ?node)]
;; … one clause per existing or-join branch
```

and the `or-join` collapses to three branches: `(in-scope ?anchor ?node)` plus the two
pivots above. The two-branch no-refs queries get the same treatment with a two-clause
rule. The `or-join` scoping rule still applies: `?anchor` stays in the join-variable
list and is re-bound inside each branch, or the pivots would match every versioned
block in the graph.

### The alternative, and why not

A reverse reference in the pull pattern, `{:vc/_blocks [:block/uid {:vc/blocks [*]}]}`
beside the `[*]` wildcard, needs no query change and nests each node's versions inside
its own row. But it breaks the flat-rows contract that the raw-result parsing and
every recorded fixture rely on, so the branch design is preferred.

### Downstream consequences

The query change is the smaller part. Returning the rows commits the pipeline to
decisions it does not have to make today:

- **Version rows parse as ordinary nodes.** They carry page and parents but sit in no
  `:block/children` set, so `NodeTree.build` never reaches them and `nodes_by_uid` is
  where they land. The `all_children_present` / `all_parents_present` validators pass,
  since the parent they name is present.
- **The group row needs a model decision.** It is `uid`, `id`, and `blocks` (the
  schema has no other `blocks` attribute, so there is no key collision). `RoamNode`
  would validate it, since only `uid` and `id` are required and unknown keys are
  ignored, but the result is a node with no string, page, or parents, and `node_type`
  has no classification for it. Either a dedicated row model or a `blocks` field with
  its own `NodeType` is needed.
- **Selection stays derivable.** Nothing on the group says which version is selected;
  the selected one is the version present in the parent's `:block/children`, so the
  model can compute it from data it already holds.
- **The revision snapshot would move** when someone edits an unselected version,
  because the hash covers every fetched row. Arguably correct, since the page's
  content did change, but a behaviour change for the fixtures.

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
