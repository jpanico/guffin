# Roam Schema

Kept in sync with the `SchemaAttribute` enum in `src/guffin/roam/schema.py`.
Namespaces and attr_names are sorted alphabetically.

Roam's schema introspection reports only attributes with at least one currently
asserted datom, and `page/dirty?` is *intermittent*: asserted while a page has
pending unsynced changes and fully retracted once it syncs clean, so it may be
absent from any given live schema fetch (see `INTERMITTENT_ATTRIBUTES` in
`src/guffin/roam/schema.py`).

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
| block          | uid               |
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
