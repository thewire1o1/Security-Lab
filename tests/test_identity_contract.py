from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SURFACES = (
    ROOT / "README.md",
    ROOT / "ARCHITECTURE.md",
    ROOT / "docs" / "index.html",
    ROOT / "dashboard" / "web" / "index.html",
    ROOT / "bin" / "doctor",
)
FORBIDDEN_PUBLIC_IDENTITIES = (
    "Digital Paragon Security Research",
    "DPSR is a reproducible security-research environment",
    "DPSR containers",
    "FORGE",
)


class IdentityContractTests(unittest.TestCase):
    def test_primary_surfaces_use_apotheon_one_identity(self) -> None:
        for path in PUBLIC_SURFACES:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn("APOTHEON ONE", text)
                for legacy in FORBIDDEN_PUBLIC_IDENTITIES:
                    self.assertNotIn(legacy, text)

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
