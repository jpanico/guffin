"""Architecture invariants over the source tree's shape (not any single module's behavior)."""

import ast
import pathlib
from typing import Final

_PACKAGE_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).parent.parent / "src" / "guffin"
_RENDER_DIR: Final[pathlib.Path] = _PACKAGE_ROOT / "render"
_CLI_DIR: Final[pathlib.Path] = _PACKAGE_ROOT / "cli"
_SERVER_DIR: Final[pathlib.Path] = _PACKAGE_ROOT / "server"
_LAUNCHER_MODULE: Final[str] = "guffin.cli.serve"


def _import_targets(source: pathlib.Path) -> set[str]:
    """Return the dotted module paths *source* actually imports (submodule-aware).

    Both ``import a.b.c`` and every ``from a.b import c`` are resolved to fully-qualified targets
    (the latter contributing both ``a.b`` and ``a.b.c``), so a submodule imported either way is
    found.  Textual mentions that are not imports — notably Sphinx ``:mod:`...``` cross-references
    in docstrings — are ignored, since only real import edges express a consumption dependency.
    """
    targets: set[str] = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.add(node.module)
            targets.update(f"{node.module}.{alias.name}" for alias in node.names)
    return targets


def _imports_package(targets: set[str], package: str) -> bool:
    """Return whether any of *targets* is *package* or a module within it."""
    return any(target == package or target.startswith(package + ".") for target in targets)


def _library_modules() -> list[pathlib.Path]:
    """Return every source module outside the front-end packages (``cli/`` and ``server/``)."""
    return sorted(
        source
        for source in _PACKAGE_ROOT.rglob("*.py")
        if not source.is_relative_to(_CLI_DIR) and not source.is_relative_to(_SERVER_DIR)
    )


class TestFrontEndIsolation:
    """The front-end packages (``cli/``, ``server/``) are leaves: no library package imports them.

    ``server/`` is a peer front end whose charter is invoking the CLI entry points in process,
    so ``server/`` → ``cli/`` is allowed; ``cli/`` → ``server/`` is allowed only so the launcher
    can start the ASGI app.  That package-level cycle stays module-level acyclic because nothing
    in ``server/`` imports the launcher module.
    """

    def test_no_library_module_imports_cli(self) -> None:
        """No module outside the front-end packages imports ``guffin.cli``."""
        for source in _library_modules():
            assert not _imports_package(
                _import_targets(source), "guffin.cli"
            ), f"{source.relative_to(_PACKAGE_ROOT)} imports guffin.cli; only a front end may"

    def test_no_library_or_cli_module_imports_server(self) -> None:
        """No module outside ``server/`` imports ``guffin.server`` — except the ``cli/`` launcher."""
        sources: Final[list[pathlib.Path]] = _library_modules() + sorted(_CLI_DIR.glob("*.py"))
        for source in sources:
            if source == _CLI_DIR / "serve.py":
                continue
            assert not _imports_package(
                _import_targets(source), "guffin.server"
            ), f"{source.relative_to(_PACKAGE_ROOT)} imports guffin.server; only the launcher may"

    def test_server_never_imports_the_launcher(self) -> None:
        """No module in ``server/`` imports the launcher — the cycle stays module-level acyclic."""
        for source in sorted(_SERVER_DIR.glob("*.py")):
            assert _LAUNCHER_MODULE not in _import_targets(
                source
            ), f"server/{source.name} imports {_LAUNCHER_MODULE}, closing the cli/server import cycle"


class TestPackageLayout:
    """The guffin package root stays module-free: all code lives in the sub-packages."""

    def test_package_root_holds_no_modules(self) -> None:
        """The only .py file directly in guffin/ is __init__.py.

        Cross-sub-package code lives beside its consumer (currently ``cli/``) until a second
        consumer forces a promotion decision; the root stays a pure namespace.
        """
        root_modules = sorted(path.name for path in _PACKAGE_ROOT.glob("*.py"))
        assert root_modules == ["__init__.py"]


class TestPostProcessingSegregation:
    """A format's post-processing lives only in its own ``render/<format>_post_processing.py``.

    Policy: any post-processing — a transform of a format's rendered *output*, applied after the
    Pandoc/Typst conversion — MUST live in ``render/<format>_post_processing.py`` and never inline
    in the ``<format>_rendering.py`` renderer; a format with no post-processing omits the module.
    These tests guard the module boundary that policy draws (existence, naming, and single-consumer
    isolation); whether a renderer smuggles a post-conversion transform inline is a semantic
    property left to review, so keep the rule in mind when editing a ``*_rendering.py``.
    """

    def test_every_post_processing_module_has_a_renderer(self) -> None:
        """Each ``render/<format>_post_processing.py`` has a sibling ``<format>_rendering.py``.

        A post-processing module names a format, so it cannot exist without the renderer whose
        output it processes.
        """
        for post_processing in sorted(_RENDER_DIR.glob("*_post_processing.py")):
            output_format = post_processing.name.removesuffix("_post_processing.py")
            renderer = _RENDER_DIR / f"{output_format}_rendering.py"
            assert renderer.is_file(), f"{post_processing.name} has no sibling {output_format}_rendering.py"

    def test_post_processing_imported_only_by_own_renderer(self) -> None:
        """A ``<format>_post_processing`` module is imported only by its own ``<format>_rendering``.

        Post-processing is a private stage of one format's pipeline: no other renderer, and no
        shared render utility, may reach into it.  (Docstring ``:mod:`...``` cross-references are
        fine — only real imports are checked.)
        """
        for post_processing in sorted(_RENDER_DIR.glob("*_post_processing.py")):
            output_format = post_processing.name.removesuffix("_post_processing.py")
            target = f"guffin.render.{output_format}_post_processing"
            owning_renderer = f"{output_format}_rendering.py"
            for source in sorted(_RENDER_DIR.glob("*.py")):
                if source.name in {post_processing.name, owning_renderer}:
                    continue
                assert target not in _import_targets(source), (
                    f"{source.name} imports {target}; a format's post-processing must be consumed "
                    f"only by its own {owning_renderer}"
                )
