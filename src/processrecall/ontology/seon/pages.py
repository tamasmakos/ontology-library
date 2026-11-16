"""Read the generated specification pages: the menu, one page per ontology.

The pages are produced by ``seon2html/parser/PageWriter.java`` from fixed templates,
so each construct is matched against its template in full. Text the templates do not
account for raises :class:`DigestError` instead of being skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from processrecall.ontology.seon import DigestError

if TYPE_CHECKING:
    from pathlib import Path

_MULTIPLICITY = r"[0-9*]+(?:\.\.[0-9*]+)?"
_RELATION_MIDDLE = re.compile(
    rf"(?: | \((?P<source_multiplicity>{_MULTIPLICITY})\) )"
    r"(?P<composition><>--)?"
    r"(?P<verb>[^\s()<>](?:[^()<>]*[^\s()<>])?)?"
    rf"(?: | \((?P<target_multiplicity>{_MULTIPLICITY})\) )"
)
_RELATION_STEREOTYPE = re.compile(r"(?P<line>.+?) {2}&lt&lt(?P<stereotype>\w+)&gt&gt")

_MENU_LAYER = re.compile(r"<p><h3>(?P<layer>\w+) Layer</h3></p>")
_MENU_ENTRY = re.compile(
    r'<p>(?P<indent>(?:&nbsp;)*)<a href="(?P<file>\w+)\.html">(?P<bold><b>)?'
    r"(?P<short_name>\w+) - (?P<full_name>[^<]+?)(?P<external> \(external\))?(?(bold)</b>)</a></p>"
)
# Between the layers: blank lines, and the rules the template draws under them.
_MENU_SKIPPED = re.compile(r'(?:<hr(?: size="3" noshade)?>)?')
_MENU_END = "<p><h3>Features</h3></p>"

_TITLE = re.compile(r'<h1 align="center">(?P<full_name>[^<]+) \((?P<short_name>\w+)\)</h1>')
_DESCRIPTION = re.compile(
    r'<h2>1\. Ontology Description</h2>\n\t<p align="justify">(?P<text>.*?)</p>', re.DOTALL
)
_DEPENDENCIES = re.compile(r"<h2>2\. Related Ontologies</h2>(?P<table>.*?)</tbody>", re.DOTALL)
_DEPENDENCY = re.compile(
    r'<tr><td><a href="(?P<file>\w+)\.html">(?P<target>\w+) - [^<]+</a></td>'
    r'<td>(?P<rationale>.*?)</td><td style="text-align:center">(?P<level>\w*)</td></tr>'
)
_MODELS = re.compile(
    r"<h2>3\. Ontology Models</h2>(?P<body>.*?)<h2>4\. Concepts Definition</h2>", re.DOTALL
)
_SECTION = re.compile(
    r'<h(?P<level>\d)><a name="(?P<anchor>[^"]+)_section">'
    r"(?P<number>\d+(?:\.\d+)+)\.  (?P<name>[^<]+)</a></h(?P=level)>"
)
_SUBONTOLOGY_FIGURE = re.compile(
    r"<p>Figure \d+ presents the conceptual model of the [^<]* subontology\.</p>"
)
_DETAILS = re.compile(
    r"<h2>Detailed Concepts</h2>\n\t?\n?(?P<body>.*?)\n\t<hr>\n\t<br/>\n\t<small>", re.DOTALL
)
_BLOCK = re.compile(
    r'<a name="(?P<anchor>[^"]+)_detail"><hr></a>'
    r'<table border="1" cellpadding="8" style="border:black">\n'
    r'<tr><td style="text-align:center">(?:<code>&lt&lt(?P<stereotype>\w+)&gt&gt</code><br/>\n)?'
    r"<strong>(?P<name>[^<]+)<strong></td></tr>\n</table><br/>\n"
    r"<b>(?P<qualified_name>[^<]+)</b><br/>\n"
    r"Specializes (?P<parents>[^<\n]*)<br/><br/>\n"
    r"(?P<definition>[^\n]*)<br/>\n"
    r"(?:Ex\.:<i>(?P<example>[^\n]*)</i>)?<br/>\n<br/>\n"
    r"(?:Relations:<br/>\n<code>(?P<relations>(?:[^\n<]*(?:<>--[^\n<]*)?<br/>\n)+)</code>)?"
    r"<br/>\n<br/><br/>\n\n"
)
_PARENT_SEPARATOR = re.compile(r", (?=\w+::)")
_BREAK = "<br/>"


@dataclass(frozen=True, slots=True)
class MenuEntry:
    """One ontology, or the subnetwork, as the menu lists it."""

    layer: str
    short_name: str
    full_name: str
    external: bool
    subnetwork: bool
    member_of: str | None


@dataclass(frozen=True, slots=True)
class DeclaredDependency:
    """A row of a page's Related Ontologies table: what the authors say is reused."""

    target: str
    rationale: str | None
    level: str | None


@dataclass(frozen=True, slots=True)
class Section:
    """A package or subontology heading in a page's Ontology Models chapter."""

    number: tuple[int, ...]
    name: str
    subontology: bool


@dataclass(frozen=True, slots=True)
class ConceptBlock:
    """A concept's detail block, the fullest text the pages hold for it."""

    qualified_name: str
    stereotype: str | None
    parents: tuple[str, ...]
    definition: str
    example: str | None
    relation_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OntologyPage:
    """Everything the digest reads from one ontology's page."""

    short_name: str
    full_name: str
    description: str
    dependencies: tuple[DeclaredDependency, ...]
    sections: tuple[Section, ...]
    blocks: tuple[ConceptBlock, ...]


@dataclass(frozen=True, slots=True)
class RelationLine:
    """One way to read a published relation line, given the known concept names."""

    text: str
    source: str
    verb: str
    composition: bool
    source_multiplicity: str | None
    target_multiplicity: str | None
    target: str
    stereotype: str | None


def read_menu(path: Path) -> tuple[MenuEntry, ...]:
    """Read the layers, their ontologies in order, and the subnetwork membership."""
    text = path.read_text(encoding="utf-8")
    start = _search(_MENU_LAYER, text, path).start()
    end = text.index(_MENU_END, start)
    entries: list[MenuEntry] = []
    layer = subnetwork = None
    for line in (line.strip() for line in text[start:end].splitlines()):
        if heading := _MENU_LAYER.fullmatch(line):
            layer, subnetwork = heading["layer"], None
        elif (entry := _MENU_ENTRY.fullmatch(line)) and layer is not None:
            if not entry["indent"]:
                subnetwork = None
            entries.append(_menu_entry(entry, layer, subnetwork))
            if entry["bold"]:
                subnetwork = entry["short_name"]
        elif not _MENU_SKIPPED.fullmatch(line):
            raise DigestError(f"{path}: unexpected menu line {line!r}")
    return tuple(entries)


def read_page(path: Path) -> OntologyPage:
    """Read one ontology page (or the subnetwork page, which has no concepts)."""
    text = path.read_text(encoding="utf-8")
    if "<span" in text:
        raise DigestError(f"{path}: flagged relations; the page is not a stable build")
    title = _search(_TITLE, text, path)
    return OntologyPage(
        short_name=title["short_name"],
        full_name=title["full_name"],
        description=_unbreak(_search(_DESCRIPTION, text, path)["text"]),
        dependencies=_read_dependencies(_search(_DEPENDENCIES, text, path)["table"], path),
        sections=_read_sections(_search(_MODELS, text, path)["body"]),
        blocks=_read_blocks(_search(_DETAILS, text, path)["body"], path),
    )


def parse_relation_line(text: str, names: frozenset[str]) -> tuple[RelationLine, ...]:
    """Every reading of *text* whose endpoints are both among *names*.

    The generator joins names, multiplicities and the verb with single spaces, and
    names may contain spaces and parentheses, so a line alone can be ambiguous. The
    caller settles it with the block the line was printed in.
    """
    line, stereotype = text, None
    if marked := _RELATION_STEREOTYPE.fullmatch(text):
        line, stereotype = marked["line"], marked["stereotype"]
    readings = []
    for source in (name for name in names if line.startswith(f"{name} ")):
        for target in (name for name in names if line.endswith(f" {name}")):
            if len(source) + len(target) + 2 > len(line):
                continue
            if middle := _RELATION_MIDDLE.fullmatch(line[len(source) : len(line) - len(target)]):
                readings.append(_relation_line(text, (source, target), middle, stereotype))
    return tuple(sorted(readings, key=lambda reading: (reading.source, reading.target)))


def _relation_line(
    text: str, endpoints: tuple[str, str], middle: re.Match[str], stereotype: str | None
) -> RelationLine:
    return RelationLine(
        text=text,
        source=endpoints[0],
        verb=middle["verb"] or "",
        composition=middle["composition"] is not None,
        source_multiplicity=middle["source_multiplicity"],
        target_multiplicity=middle["target_multiplicity"],
        target=endpoints[1],
        stereotype=stereotype,
    )


def _menu_entry(entry: re.Match[str], layer: str, subnetwork: str | None) -> MenuEntry:
    if entry["file"] != entry["short_name"] or bool(entry["indent"]) != (subnetwork is not None):
        raise DigestError(f"menu entry out of place: {entry.group()!r}")
    return MenuEntry(
        layer=layer,
        short_name=entry["short_name"],
        full_name=entry["full_name"],
        external=entry["external"] is not None,
        subnetwork=entry["bold"] is not None,
        member_of=subnetwork,
    )


def _read_dependencies(table: str, path: Path) -> tuple[DeclaredDependency, ...]:
    _, header_end, rows = table.partition("</tr>")
    if not header_end:
        raise DigestError(f"{path}: Related Ontologies table without a header row")
    dependencies = []
    for line in filter(None, (line.strip() for line in rows.splitlines())):
        row = _DEPENDENCY.fullmatch(line)
        if row is None or row["file"] != row["target"]:
            raise DigestError(f"{path}: unexpected dependency row {line!r}")
        dependencies.append(
            DeclaredDependency(
                target=row["target"],
                rationale=_unbreak(row["rationale"]) or None,
                level=row["level"] or None,
            )
        )
    return tuple(dependencies)


def _read_sections(models: str) -> tuple[Section, ...]:
    headings = list(_SECTION.finditer(models))
    ends = [heading.start() for heading in headings] + [len(models)]
    return tuple(
        Section(
            number=tuple(int(part) for part in heading["number"].split(".")[1:]),
            name=heading["name"],
            subontology=_SUBONTOLOGY_FIGURE.search(models, heading.end(), end) is not None,
        )
        for heading, end in zip(headings, ends[1:], strict=True)
    )


def _read_blocks(details: str, path: Path) -> tuple[ConceptBlock, ...]:
    blocks, position = [], 0
    while position < len(details):
        block = _BLOCK.match(details, position)
        if block is None:
            raise DigestError(
                f"{path}: unreadable concept block at {details[position : position + 80]!r}"
            )
        blocks.append(_concept_block(block))
        position = block.end()
    return tuple(blocks)


def _concept_block(block: re.Match[str]) -> ConceptBlock:
    qualified_name = block["qualified_name"]
    if qualified_name.partition("::")[2] != block["name"]:
        raise DigestError(f"{qualified_name}: block titled {block['name']!r}")
    relations = block["relations"] or ""
    return ConceptBlock(
        qualified_name=qualified_name,
        stereotype=block["stereotype"],
        parents=tuple(_PARENT_SEPARATOR.split(block["parents"])) if block["parents"] else (),
        definition=_unbreak(block["definition"]),
        example=block["example"],
        relation_lines=tuple(line for line in relations.split(f"{_BREAK}\n") if line),
    )


def _unbreak(html: str) -> str:
    """Undo the generator's newline encoding; refuse any other markup."""
    text = html.replace(_BREAK, "\n")
    if "<" in text.replace("<>--", ""):
        raise DigestError(f"unexpected markup in {html!r}")
    return text


def _search(pattern: re.Pattern[str], text: str, path: Path) -> re.Match[str]:
    if (found := pattern.search(text)) is None:
        raise DigestError(f"{path}: no match for {pattern.pattern[:60]!r}")
    return found
