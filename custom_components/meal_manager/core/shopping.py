"""Shopping list written by the local model from the ingredients of the uncooked meals.

The model turns recipe amounts into products as they are sold ("Kokosmilch: 2 Dosen à 400 ml"),
merges what is the same product, leaves out what the household always has and writes in the
household's language. Its answer is checked strictly; a broken answer is rejected with a reason.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import Any

from .llm import LANGUAGES, Rejected, split_lines
from .models import Ingredient, nice_quantity

DEFAULT_PANTRY = "Wasser, Salz, Pfeffer, Speiseöl, Essig, Mehl, Zucker, getrocknete Gewürze"

_EXAMPLES = {
    "de": "'Kokosmilch | 2 Dosen à 400 ml', 'Petersilie | 1 Bund', 'Kartoffeln | 1,5 kg',"
    " 'Eier | 1 Packung (10 Stück)'",
    "en": "'Coconut milk | 2 cans of 400 ml', 'Parsley | 1 bunch', 'Potatoes | 1.5 kg', 'Eggs | 1 box of 10'",
}
_DIGIT = re.compile(r"\d")


@dataclass(frozen=True, slots=True)
class ShoppingItem:
    name: str
    amount: str

    def display(self) -> str:
        """E.g. 'Kokosmilch: 2 Dosen à 400 ml'; name first so the list reads by product."""
        return f"{self.name}: {self.amount}"


def build_shopping_instructions(ingredients: Iterable[Ingredient], pantry: str, language: str) -> str:
    """Instructions to turn the summed recipe ingredients into a shopping list."""
    needed = "\n".join(
        f"- {nice_quantity(i.quantity):g} {i.unit} {i.name}" if i.quantity else f"- {i.name}"
        for i in ingredients
    )
    examples = _EXAMPLES.get(language, _EXAMPLES["en"])
    lines = [
        "Write a shopping list for a supermarket in Central Europe for the ingredients below"
        " (total amounts of all meals).",
        f"Write it in {LANGUAGES.get(language, 'English')}.",
        "Merge ingredients that are the same product, e.g. different spellings or kinds of onions.",
        "Give every product as it is sold, with the package size, and round up so there is enough:"
        f" whole pieces, packs, cans, jars, bottles or bunches, e.g. {examples}.",
    ]
    if pantry.strip():
        lines.append(f"Leave out what the household always has at home: {pantry.strip()}.")
    lines += [
        "Answer with:",
        "- items: one product per line, formatted 'product | amount'. Nothing else: no headings,"
        " no sections, no comments. Answers in any other format are rejected.",
        "Ingredients:",
        needed,
    ]
    return "\n".join(lines)


def parse_shopping_list(data: Any, ingredients: list[Ingredient]) -> list[ShoppingItem]:
    """The model's shopping list, or raise Rejected with the reason."""
    if not isinstance(data, dict):
        raise Rejected("the answer is not a shopping list")
    items: list[ShoppingItem] = []
    malformed: list[str] = []
    for line in split_lines(data.get("items")):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 2 or not parts[0] or not _DIGIT.search(parts[1]):
            malformed.append(line)
        else:
            items.append(ShoppingItem(" ".join(parts[0].split()), " ".join(parts[1].split())))
    if malformed:
        raise Rejected(f"lines not written as 'product | amount' with a number: {'; '.join(malformed)}")
    if ingredients and not items:
        raise Rejected("the list is empty")
    if len(items) > len(ingredients):
        raise Rejected("the list has more products than there are ingredients")
    names = [i.name.casefold() for i in items]
    if duplicates := sorted({n for n in names if names.count(n) > 1}):
        raise Rejected(f"products listed more than once (merge them): {', '.join(duplicates)}")
    return items
