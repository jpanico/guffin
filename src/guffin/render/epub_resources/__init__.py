"""EPUB Pandoc Lua filters — bundled package data for ``guffin``.

Holds the ``epub_*.lua`` Pandoc filters applied when converting to EPUB 3.  EPUB content is XHTML,
so these emit the same raw-HTML markup as their GFM counterparts (inline-styled ``<span>``/``<mark>``
elements) to preserve Roam color/highlight/pill styling in the e-book.
"""
