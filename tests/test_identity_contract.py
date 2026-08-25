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
ACCEPTED_APOTHEON_IDENTITIES = (
    "APOTHEON:ONE",
    "APOTHEON ONE",
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
SCRIPT_ROOTS = {"admin", "bin"}
IGNORED_PARTS = {".git", "artifacts", "cases", "reports"}
THIS_FILE = Path(__file__).resolve()


def repository_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() == THIS_FILE:
            continue
        relative = path.relative_to(ROOT)
        if IGNORED_PARTS.intersection(relative.parts):
            continue
        is_script_surface = bool(relative.parts) and relative.parts[0] in SCRIPT_ROOTS
        if path.suffix.lower() not in TEXT_SUFFIXES and not is_script_surface:
            continue
        yield path


class IdentityContractTests(unittest.TestCase):
    def test_primary_surfaces_use_apotheon_one_identity(self) -> None:
        for path in PUBLIC_SURFACES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(
                    any(identity in text for identity in ACCEPTED_APOTHEON_IDENTITIES),
                    f"APOTHEON identity missing from {path.relative_to(ROOT)}",
                )

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
