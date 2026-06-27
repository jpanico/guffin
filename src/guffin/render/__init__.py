"""Render sub-package: turn the normalized model into consumable output.

Holds everything that renders a :class:`~guffin.model.vertex_tree.VertexTree` (or
:class:`~guffin.model.render_bundle.RenderBundle`) into an output target — document export
(Markdown, PDF, EPUB) and terminal display (Rich) — along with the configuration that drives it
(output format, render options, project profile) and the bundled Pandoc/Typst resources.
"""
