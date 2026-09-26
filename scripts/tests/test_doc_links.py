"""Focused regression tests for rendered Markdown and CLI failures."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_doc_links import check, parse_document, tracked_markdown


class MarkdownTests(unittest.TestCase):
    def test_rendered_heading_ids_and_collisions(self):
        document = parse_document(
            "# Hello, *world*! `code` &amp; café\n"
            "# Repeat\n# Repeat\n# Repeat-1\n# Repeat\n"
            "Setext **title**\n---\n"
            "# With <em>HTML</em> and ![alt text](icon.svg)\n"
            '<a id="custom"></a>\n<a name="legacy"></a>\n'
        )
        self.assertEqual(
            document.anchors,
            {
                "hello-world-code--café",
                "repeat",
                "repeat-1",
                "repeat-1-1",
                "repeat-2",
                "setext-title",
                "with-html-and-alt-text",
                "custom",
                "legacy",
            },
        )

    def test_code_and_comments_are_not_links_or_headings(self):
        document = parse_document(
            "````markdown\n# Fake\n[bad](missing.md)\n```\n````\n"
            "~~~md\n# Also fake\n[bad](missing.md)\n~~~\n\n"
            "    # Indented fake\n    [bad](missing.md)\n\n"
            "`[bad](missing.md)` and ``[bad](missing.md)``\n"
            "<!-- [bad](missing.md) -->\n"
            "# Real\n[good](#real)\n"
        )
        self.assertEqual(document.anchors, {"real"})
        self.assertEqual(document.links, [(17, "#real")])

    def test_inline_reference_image_and_multiline_source_locations(self):
        document = parse_document(
            'Paragraph first line\n[inline](file(1).md "Title")\n'
            "and ![image](<image file.png>)\n\n"
            "[Full][ref] and [ref][] and [ref]\n\n"
            '[ref]: target.md#heading "Title"\n\n'
            "> [quoted](quote.md)\n\n- [listed](list.md)\n"
        )
        self.assertEqual(
            document.links,
            [
                (2, "file(1).md"),
                (3, "image%20file.png"),
                (5, "target.md#heading"),
                (5, "target.md#heading"),
                (5, "target.md#heading"),
                (9, "quote.md"),
                (11, "list.md"),
            ],
        )


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def write(self, name, text=""):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_relative_root_encoded_and_external_links(self):
        self.write("docs/target file.md", "# Café\n# Café\n<a id='manual'></a>\n")
        self.write("asset.png")
        self.write("file(1).md", "# Heading\n")
        source = self.write(
            "docs/source.md",
            """# Local
[same](#local)
[relative](target%20file.md#caf%C3%A9-1)
[root](/docs/target%20file.md?view=1#manual)
[parent](../file(1).md#heading)
![image](../asset.png)
[directory](../docs/)
[external](https://invalid.example/missing#absent)
[protocol-relative](//invalid.example/missing)
[email](mailto:someone@example.com)
[custom](custom:resource)
""",
        )
        self.assertEqual(check(self.root, [source]), [])

    def test_errors_include_file_line_destination_and_reason(self):
        self.write("target.md", "# Present\n```md\n# Fake\n```\n")
        source = self.write(
            "docs/source.md",
            """# Source
[missing](absent.md)
paragraph
[anchor](../target.md#absent)
[example heading](../target.md#fake)
[escape](../../outside.md)
![missing image](missing.png)
""",
        )
        self.assertEqual(
            check(self.root, [source]),
            [
                "docs/source.md:2: 'absent.md': local target does not exist",
                "docs/source.md:4: '../target.md#absent': heading/HTML anchor #absent does not exist",
                "docs/source.md:5: '../target.md#fake': heading/HTML anchor #fake does not exist",
                "docs/source.md:6: '../../outside.md': target is outside the repository",
                "docs/source.md:7: 'missing.png': local target does not exist",
            ],
        )

    def test_cli_tracked_files_only_and_exit_status(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        source = self.write("docs/with spaces.MD", "# Good\n[link](#good)\n")
        self.write("untracked.md", "[bad](missing.md)")
        subprocess.run(["git", "-C", str(self.root), "add", "docs"], check=True)
        self.assertEqual(tracked_markdown(self.root), [source])
        command = [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "check_doc_links.py"),
            "--root",
            str(self.root),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 Markdown files", result.stdout)
        source.write_text("# Good\n[link](#wrong)\n")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/with spaces.MD:2: '#wrong'", result.stderr)


if __name__ == "__main__":
    unittest.main()
