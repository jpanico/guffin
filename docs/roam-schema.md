# Roam Schema

Kept in sync with the `SchemaAttribute` enum in `src/guffin/roam/schema.py`.
Namespaces and attr_names are sorted alphabetically.

Roam's schema introspection reports only attributes with at least one currently
asserted datom, and `page/dirty?` is *intermittent*: asserted while a page has
pending unsynced changes and fully retracted once it syncs clean, so it may be
absent from any given live schema fetch (see `INTERMITTENT_ATTRIBUTES` in
`src/guffin/roam/schema.py`).

**Attr_names are not unique across namespaces**, and the Local API strips namespaces from
pull-block keys — so two attributes sharing an attr_name arrive on the same JSON key, one
silently overwriting the other. `block/view-type` and `children/view-type` are such a pair
(a per-block display default vs. the authored children layout), which is why the node queries
pull them under `:as` aliases. Check this table for a name collision before adding an attribute
to a pull pattern; see [roam-querying.md](roam-querying.md), *Stripping makes distinct attributes
collide*.

| namespace      | attr_name         |
| -------------- | ----------------- |
| annotation     | origin            |
| attrs          | lookup            |
| block          | children          |
| block          | heading           |
| block          | open              |
| block          | order             |
| block          | page              |
| block          | parents           |
| block          | props             |
| block          | refs              |
| block          | string            |
| block          | text-align        |
| block          | uid               |
| block          | view-type         |
| children       | view-type         |
| create         | time              |
| create         | user              |
| edit           | seen-by           |
| edit           | time              |
| edit           | user              |
| entity         | attrs             |
| graph          | settings          |
| log            | id                |
| node           | title             |
| page           | dirty?            |
| page           | edit-nonce        |
| page           | edit-time         |
| page           | edit-user         |
| page           | sidebar           |
| page           | word-count        |
| pdf            | fingerprints      |
| pdf            | url               |
| restrictions   | prevent-clean     |
| token          | ai                |
| token          | created-by-uid    |
| token          | description       |
| token          | device-name       |
| token          | type              |
| user           | display-name      |
| user           | display-page      |
| user           | photo-url         |
| user           | settings          |
| user           | uid               |
| vc             | blocks            |
| version        | id                |
| version        | nonce             |
| version        | upgraded-nonce    |
| window         | filters           |
| window         | id                |
| window         | mentions-state    |
