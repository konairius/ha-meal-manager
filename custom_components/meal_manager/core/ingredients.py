"""Known ingredients: canonical names, units, translations, supermarket sections and packages."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Package:
    """How an ingredient is sold, e.g. 400 ml per can."""

    size: float
    unit: str  # unit of the recipe amounts it covers: g, ml or pcs
    labels: Mapping[str, str]  # language -> e.g. "Dose 400 ml"


@dataclass(frozen=True, slots=True)
class IngredientInfo:
    """Everything known about one ingredient."""

    unit: str = ""  # the unit recipes use for it: g, ml or pcs
    category: str = "other"
    names: Mapping[str, str] = field(default_factory=dict)  # language -> name
    package: Package | None = None
    aliases: tuple[str, ...] = ()


def _key(name: str) -> str:
    return " ".join(name.casefold().split())


class IngredientCatalog(Mapping[str, IngredientInfo]):
    """Canonical ingredients by English name, with lookup by alias and simple plural forms."""

    def __init__(self, items: Mapping[str, IngredientInfo]) -> None:
        self._items = {_key(name): info for name, info in items.items()}
        self._aliases = {_key(alias): name for name, info in self._items.items() for alias in info.aliases}

    def __getitem__(self, name: str) -> IngredientInfo:
        return self._items[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def resolve(self, name: str) -> str | None:
        """The canonical name for 'Onions', 'yellow onion' or 'fresh thyme'; None if unknown."""
        key = _key(name)
        candidates = [key]
        if key.startswith("fresh "):
            candidates.append(key.removeprefix("fresh "))
        for base in list(candidates):
            candidates += [base + "s", base + "es", base.removesuffix("s"), base.removesuffix("es")]
        for candidate in candidates:
            if candidate in self._items:
                return candidate
            if candidate in self._aliases:
                return self._aliases[candidate]
        return None

    def info(self, name: str) -> IngredientInfo | None:
        resolved = self.resolve(name)
        return self._items[resolved] if resolved else None

    def prompt_list(self) -> str:
        """'apple (pcs), basil (g), ...' for a model prompt."""
        return ", ".join(f"{name} ({info.unit})" for name, info in sorted(self._items.items()))
