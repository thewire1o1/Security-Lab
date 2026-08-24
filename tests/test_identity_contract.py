from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SURFACES = (
    ROOT / "README.md",
    ROOT / "ARCHITECTURE.md",
    ROOT / "docs" / "index.html",
    ROOT / "dashboard" / "web" / "index.html",
    ROOT / "bin" / "dpsr",
    ROOT / "bin" / "sec",
    ROOT / "bin" / "doctor",
    ROOT / "bin" / "dashboard-control",
    ROOT / "bin" / "mcp-control",
    ROOT / "bin" / "repair-tools",
    ROOT / "bin" / "update-all",
)
FORBIDDEN_PUBLIC_IDENTITIES = (
    "Digital Paragon Security Research",
    "DPSR Platform",
    "DPSR is a reproducible security-research environment",
    "DPSR Operations Console",
    "DPSR containers",
    "FORGE",
)
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_PARTS = {".git", "artifacts", "cases", "reports"}


def repository_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if IGNORED_PARTS.intersection(path.relative_to(ROOT).parts):
            continue
        yield path


class IdentityContractTests(unittest.TestCase):
    def test_primary_surfaces_use_apotheon_one_identity(self) -> None:
        for path in PUBLIC_SURFACES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn("APOTHEON ONE", text)

    def test_retired_product_names_do_not_reappear_in_source(self) -> None:
        violations: list[str] = []
        for path in repository_text_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            for legacy in FORBIDDEN_PUBLIC_IDENTITIES:
                if legacy in text:
                    violations.append(f"{path.relative_to(ROOT)}: {legacy}")
        self.assertEqual(violations, [], "Retired public identity found:\n" + "\n".join(violations))

    def test_readme_preserves_brand_hierarchy(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "Unified. Elevated.",
            "Digital Paragon",
            "Information Technology Excellence",
            "TheWire1o1",
            "James Porath",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
