"""Architecture invariants over the source tree's shape (not any single module's behavior)."""

import pathlib
from typing import Final

_PACKAGE_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).parent.parent / "src" / "guffin"


class TestPackageLayout:
    """The guffin package root stays module-free: all code lives in the sub-packages."""

    def test_package_root_holds_no_modules(self) -> None:
        """The only .py file directly in guffin/ is __init__.py.

        Cross-sub-package code lives beside its consumer (currently ``cli/``) until a second
        consumer forces a promotion decision; the root stays a pure namespace.
        """
        root_modules = sorted(path.name for path in _PACKAGE_ROOT.glob("*.py"))
        assert root_modules == ["__init__.py"]
