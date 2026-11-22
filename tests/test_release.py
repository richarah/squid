"""Release: the dependency on tolk is a tag, and the README says at the top that it is private for now."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_tolk_is_depended_on_at_the_v0_1_5_tag() -> None:
    text = (ROOT / "pyproject.toml").read_text()
    assert "git+https://github.com/richarah/tolk.git@v0.1.5" in text
    assert "@housekeeping" not in text


def test_the_top_of_the_readme_says_it_depends_on_a_private_repository() -> None:
    head = "\n".join((ROOT / "README.md").read_text().splitlines()[:8]).lower()
    assert "private repository" in head and "only its owner can install" in head
