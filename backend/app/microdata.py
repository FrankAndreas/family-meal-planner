"""Recipes marked up as schema.org microdata (itemscope / itemprop in the page itself, e.g. swissmilk.ch), read into
the same shape as JSON-LD so `jsonld.draft_from_node` makes the draft. Nothing on the page is run or followed."""

from collections.abc import Callable
from html.parser import HTMLParser

from .jsonld import draft_from_node

# Elements that never have content or an end tag
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Their value is an attribute, not their text
_VALUE_ATTRIBUTE = {"meta": "content", "img": "src", "link": "href", "a": "href", "source": "src", "time": "datetime"}
# Properties that are lists in a recipe; the others take their first value
_LISTS = {"recipeIngredient", "recipeInstructions", "image"}


def _is_recipe_type(itemtype: str | None) -> bool:
    return any(t.rstrip("/").endswith("schema.org/Recipe") for t in (itemtype or "").split())


class _Element:
    def __init__(self, tag: str, attrs: dict[str, str], scope: "_Scope | None", owner: "_Scope | None"):
        self.tag, self.attrs = tag, attrs
        # The item this element opens (itemscope), and the item its itemprop belongs to
        self.scope, self.owner = scope, owner
        self.text: list[str] = []


class _Scope:
    def __init__(self, is_recipe: bool):
        self.is_recipe = is_recipe
        self.props: dict[str, list[str]] = {}


class _Reader(HTMLParser):
    def __init__(self, keep_ingredient: Callable[[dict[str, str]], bool]):
        super().__init__(convert_charrefs=True)
        self.keep_ingredient = keep_ingredient
        self.stack: list[_Element] = []
        self.recipe: _Scope | None = None

    def _current_scope(self) -> _Scope | None:
        return next((e.scope for e in reversed(self.stack) if e.scope is not None), None)

    def handle_starttag(self, tag, attrs):
        attributes = {k: v or "" for k, v in attrs}
        owner = self._current_scope() if "itemprop" in attributes else None
        scope = None
        if "itemscope" in attributes:
            scope = _Scope(_is_recipe_type(attributes.get("itemtype")))
            if scope.is_recipe and self.recipe is None:
                self.recipe = scope
        if tag in _VOID:
            # A void element's value is its attribute
            if owner is not None and tag in _VALUE_ATTRIBUTE:
                self._add(owner, attributes, attributes.get(_VALUE_ATTRIBUTE[tag], ""))
            return
        self.stack.append(_Element(tag, attributes, scope, owner))

    def handle_endtag(self, tag):
        # Close up to the matching element; pages with unclosed tags are common
        if not any(e.tag == tag for e in self.stack):
            return
        while self.stack:
            element = self.stack.pop()
            text = " ".join("".join(element.text).split())
            if self.stack:
                self.stack[-1].text.append(f" {''.join(element.text)} ")
            if element.owner is not None:
                attribute = _VALUE_ATTRIBUTE.get(element.tag)
                value = element.attrs.get(attribute, "") if attribute and element.attrs.get(attribute) else text
                self._add(element.owner, element.attrs, value)
            if element.tag == tag:
                break

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].text.append(data)

    def _add(self, owner: _Scope, attrs: dict[str, str], value: str) -> None:
        # Only the recipe's own properties: a video's or a rating's name is not the recipe's
        if owner is not self.recipe or not value.strip():
            return
        for name in attrs.get("itemprop", "").split():
            if name == "recipeIngredient" and not self.keep_ingredient(attrs):
                continue
            owner.props.setdefault(name, []).append(" ".join(value.split()))


def recipe_node(page: str, *, keep_ingredient: Callable[[dict[str, str]], bool] = lambda attrs: True) -> dict | None:
    """The page's first schema.org Recipe as a JSON-LD-like dict, or None. `keep_ingredient` gets the attributes of
    each recipeIngredient element (a site can tell real ingredients from equipment)."""
    reader = _Reader(keep_ingredient)
    try:
        reader.feed(page)
        reader.close()
    except Exception:
        return None
    if reader.recipe is None:
        return None
    return {name: values if name in _LISTS else values[0] for name, values in reader.recipe.props.items()}


def recipe_from_html(page: str, page_url: str, **kw) -> dict | None:
    node = recipe_node(page, **kw)
    return draft_from_node(node, page_url) if node else None
