"""Regenerate ``guffin/common/programming_language_data.py`` from GitHub Linguist.

Fetches ``lib/linguist/languages.yml`` at a pinned Linguist release tag and emits a
generated Python module holding the canonical programming-language vocabulary: one
mapping from every lowercased language name and alias to its canonical language id
(the lowercased Linguist language name).

Usage (from the repository root)::

    python scripts/regen_programming_languages.py [--tag v9.6.0]

The output file is fully generated — never edit it by hand; re-run this script to
refresh the vocabulary at a newer Linguist release.
"""

import argparse
import json
import pathlib
import sys
from typing import Final

import requests
import yaml
from pydantic import TypeAdapter

DEFAULT_TAG: Final[str] = "v9.6.0"
LANGUAGES_YML_URL: Final[str] = (
    "https://raw.githubusercontent.com/github-linguist/linguist/{tag}/lib/linguist/languages.yml"
)
OUTPUT_PATH: Final[pathlib.Path] = pathlib.Path("src/guffin/common/programming_language_data.py")

_HEADER_TEMPLATE: Final[str] = '''"""Canonical programming-language vocabulary, generated from GitHub Linguist {tag}.

**GENERATED FILE — DO NOT EDIT.**  Regenerate with::

    python scripts/regen_programming_languages.py --tag {tag}

Source: {url}

Public symbols:

- :data:`LANGUAGE_ID_BY_ALIAS` — mapping from every lowercased Linguist language name
  and alias to its canonical language id (the lowercased Linguist language name).
"""

from collections.abc import Mapping
from typing import Final

LANGUAGE_ID_BY_ALIAS: Final[Mapping[str, str]] = {{
'''


_LANGUAGES_ADAPTER: Final[TypeAdapter[dict[str, dict[str, object]]]] = TypeAdapter(dict[str, dict[str, object]])
_ALIASES_ADAPTER: Final[TypeAdapter[list[str]]] = TypeAdapter(list[str])


def _fetch_languages_yml(tag: str) -> dict[str, dict[str, object]]:
    """Fetch and parse languages.yml at *tag*."""
    url: Final[str] = LANGUAGES_YML_URL.format(tag=tag)
    print(f"fetching {url} …")
    response: Final[requests.Response] = requests.get(url, timeout=30)
    response.raise_for_status()
    return _LANGUAGES_ADAPTER.validate_python(yaml.safe_load(response.text))


def _alias_map(languages: dict[str, dict[str, object]]) -> dict[str, str]:
    """Build the lowercased name/alias → canonical-id mapping.

    The canonical id is the lowercased Linguist language name.  A name key always wins
    over a colliding alias from a different language; a colliding alias is dropped with
    a warning (Linguist aliases are unique in practice, so collisions indicate an
    upstream change worth reviewing).
    """
    mapping: dict[str, str] = {}
    # Names first, so a name key can never be shadowed by another language's alias.
    for name in languages:
        mapping[name.lower()] = name.lower()
    for name, entry in languages.items():
        canonical: str = name.lower()
        raw_aliases: object = entry.get("aliases")
        if raw_aliases is None:
            continue
        aliases: list[str] = _ALIASES_ADAPTER.validate_python(raw_aliases)
        for alias in aliases:
            key: str = alias.lower()
            existing: str | None = mapping.get(key)
            if existing is not None and existing != canonical:
                print(f"  WARNING: alias {key!r} of {canonical!r} collides with {existing!r}; keeping {existing!r}")
                continue
            mapping[key] = canonical
    return mapping


def main() -> None:
    """Regenerate the vocabulary module."""
    parser: Final[argparse.ArgumentParser] = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=DEFAULT_TAG, help=f"Linguist release tag (default {DEFAULT_TAG})")
    args: Final[argparse.Namespace] = parser.parse_args()

    languages: Final[dict[str, dict[str, object]]] = _fetch_languages_yml(args.tag)
    mapping: Final[dict[str, str]] = _alias_map(languages)

    lines: Final[list[str]] = [_HEADER_TEMPLATE.format(tag=args.tag, url=LANGUAGES_YML_URL.format(tag=args.tag))]
    # json.dumps emits black-style double-quoted string literals, so `black .` never
    # reformats the generated module.
    for key in sorted(mapping):
        lines.append(f"    {json.dumps(key)}: {json.dumps(mapping[key])},\n")
    lines.append('}\n"""Maps every lowercased Linguist language name and alias to its canonical language id."""\n')

    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({len(mapping)} alias keys, {len(set(mapping.values()))} languages)")


if __name__ == "__main__":
    sys.exit(main())
