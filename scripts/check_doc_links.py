"""Check Git-tracked Markdown links locally; never request external URLs."""

import argparse
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
from markdown_it.rules_inline import image, link


def located(rule):
    """Preserve source lines, including links in multiline paragraphs."""

    def wrapper(state, silent):
        start, count = state.pos, len(state.tokens)
        matched = rule(state, silent)
        if matched and not silent:
            for token in state.tokens[count:]:
                if token.type in {"link_open", "image"}:
                    token.meta.setdefault("line", state.src.count("\n", 0, start))
        return matched

    return wrapper


def parser():
    md = MarkdownIt("commonmark")
    md.inline.ruler.at("link", located(link))
    md.inline.ruler.at("image", located(image))
    return md


def plain_text(tokens):
    parts = []
    for token in tokens:
        if token.type in {"text", "code_inline"}:
            parts.append(token.content)
        elif token.type in {"softbreak", "hardbreak"}:
            parts.append(" ")
        elif token.type == "image":
            parts.append(plain_text(token.children or []))
    return "".join(parts)


def slug(text):
    # GitHub-style headings: preserve Unicode letters/numbers and '-'/'_',
    # remove punctuation/symbols, and replace each space with a hyphen.
    return "".join(
        c for c in text.lower() if c in " -_" or unicodedata.category(c)[0] in "LMN"
    ).replace(" ", "-")


class ExplicitAnchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if value is not None and (key == "id" or (tag == "a" and key == "name")):
                self.anchors.add(value)


@dataclass
class Document:
    anchors: set[str]
    links: list[tuple[int, str]]


def parse_document(text):
    tokens = parser().parse(text)
    anchors, links = set(), []
    html = ExplicitAnchors()
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            base = slug(plain_text(tokens[index + 1].children or []))
            anchor, suffix = base, 0
            while anchor in anchors:
                suffix += 1
                anchor = f"{base}-{suffix}"
            anchors.add(anchor)
        if token.type == "html_block":
            html.feed(token.content)
        if token.type != "inline":
            continue
        for child in token.children or []:
            if child.type == "html_inline":
                html.feed(child.content)
            attr = {"link_open": "href", "image": "src"}.get(child.type)
            if attr:
                line = token.map[0] + child.meta.get("line", 0) + 1
                links.append((line, child.attrGet(attr)))
    return Document(anchors | html.anchors, links)


def tracked_markdown(root):
    output = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
    return sorted(
        root / name
        for name in output.decode().split("\0")
        if Path(name).suffix.lower() == ".md"
    )


def check(root, paths):
    documents = {}
    errors = []

    def document(path):
        if path not in documents:
            documents[path] = parse_document(path.read_text(encoding="utf-8"))
        return documents[path]

    for source in paths:
        try:
            links = document(source).links
        except (OSError, UnicodeError) as exc:
            errors.append(f"{source.relative_to(root)}:1: cannot read Markdown: {exc}")
            continue
        for line, destination in links:
            # Schemes (https:, mailto:, data:, etc.) and protocol-relative URLs
            # are out of scope. Do not contact the network, even to validate them.
            if re.match(
                r"^[a-zA-Z][a-zA-Z0-9+.-]*:", destination
            ) or destination.startswith("//"):
                continue
            prefix = f"{source.relative_to(root)}:{line}: {destination!r}: "
            try:
                url = urlsplit(destination)
                path = unquote(url.path)
                target = (
                    root / path.lstrip("/")
                    if path.startswith("/")
                    else source.parent / path
                    if path
                    else source
                ).resolve()
                if not target.is_relative_to(root):
                    errors.append(prefix + "target is outside the repository")
                elif not target.exists():
                    errors.append(prefix + "local target does not exist")
                elif url.fragment and target.suffix.lower() == ".md":
                    anchor = unquote(url.fragment)
                    if anchor not in document(target).anchors:
                        errors.append(
                            prefix + f"heading/HTML anchor #{anchor} does not exist"
                        )
            except (OSError, UnicodeError, ValueError) as exc:
                errors.append(prefix + f"cannot check target: {exc}")
    return errors


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Git repository root (defaults to this script's repository)",
    )
    args = cli.parse_args()
    root = args.root.resolve()
    try:
        paths = tracked_markdown(root)
    except subprocess.CalledProcessError:
        cli.error(f"cannot list tracked files in {root}")
    errors = check(root, paths)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Checked local links and anchors in {len(paths)} Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
