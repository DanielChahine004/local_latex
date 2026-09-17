"""Note bodies -> Markdown.

Deliberately not a TeX engine: a table of macros, applied in order, then a few
structural rules and a sweep that drops whatever is left. A lab extends it in
two ways, both read from notesmap.toml:

    [latex.macros]  name = "template"   {1}..{n} are the arguments; {n:unit}
                                        maps an siunitx unit, {n:md} converts
                                        the argument recursively
    [latex.units]   "\\kilo\\gram" = "kg"
    [latex]         plugins = ["mylab"]  a module beside notesmap.toml with
                                        register(converter), for anything a
                                        template cannot express
"""
from __future__ import annotations

import importlib
import re
import sys
from typing import Callable

UNITS = {
    r"\milli\metre": "mm", r"\centi\metre": "cm", r"\metre": "m", r"\micro\metre": "µm",
    r"\nano\second": "ns", r"\pico\second": "ps", r"\second": "s", r"\volt": "V",
    r"\percent": "%", r"\degreeCelsius": "°C", r"\kilo\electronvolt": "keV",
    r"\mega\electronvolt": "MeV", r"\mega\hertz": "MHz",
    r"cps\per\kilo\becquerel": "cps/kBq", r"\kilo\becquerel": "kBq",
}

# symbol accents only: \'e, \'{e}. Letter accents such as \c{c} are handled
# with braces alone, since \cc would also match the start of a macro name
ACCENTS = (("'", "aeiouAEIOU", "áéíóúÁÉÍÓÚ"), ("`", "aeiou", "àèìòù"), ('"', "aeiouAEIOU", "äëïöüÄËÏÖÜ"),
           ("~", "aonAON", "ãõñÃÕÑ"), ("^", "aeiou", "âêîôû"))
BRACED_ACCENTS = {r"\c{c}": "ç", r"\c{C}": "Ç", r"\v{s}": "š", r"\v{c}": "č", r"\l{}": "ł", r"\o{}": "ø"}

Handler = Callable[..., str]


def take_args(text: str, i: int, n: int) -> tuple[list[str], int]:
    """Read n brace-delimited arguments from text[i], skipping one leading [optional]."""
    while i < len(text) and text[i] in " \t":
        i += 1
    if i < len(text) and text[i] == "[":
        j = text.find("]", i)
        if j != -1:
            i = j + 1
    args = []
    for _ in range(n):
        while i < len(text) and text[i] in " \t":
            i += 1
        if i >= len(text) or text[i] != "{":
            break
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        args.append(text[i + 1:j])
        i = j + 1
    return args, i


def expand(text: str, macro: str, n: int, fn: Handler) -> str:
    """Replace every \\macro{..}..{..} (n arguments) with fn(*args)."""
    out, i, key = [], 0, "\\" + macro
    while True:
        k = text.find(key, i)
        # not a longer macro name (\mm is not \mmx) and not an escaped backslash
        while k != -1 and ((k + len(key) < len(text) and text[k + len(key)].isalpha())
                           or (k > 0 and text[k - 1] == "\\")):
            k = text.find(key, k + 1)
        if k == -1:
            out.append(text[i:])
            break
        out.append(text[i:k])
        args, end = take_args(text, k + len(key), n)
        out.append(fn(*args) if len(args) == n else text[k:end])
        i = end
    return "".join(out)


class Converter:
    def __init__(self, units: dict[str, str] | None = None) -> None:
        self.units = dict(UNITS, **(units or {}))
        self.macros: dict[str, tuple[int, Handler]] = {}   # insertion order is application order
        u = self.unit
        self.add("gap", 1, lambda a: f"**[gap: {self.to_md(a)}]**")
        self.add("qtyproduct", 2, lambda v, x: f"{v.replace(' x ', '×')} {u(x)}")
        self.add("qtyrange", 3, lambda a, b, x: f"{a}–{b} {u(x)}")
        self.add("qty", 2, lambda v, x: f"{v} {u(x)}")
        for m, s in {"mm": "mm", "cm": "cm", "um": "µm", "ps": "ps", "ns": "ns",
                     "keV": "keV", "MeV": "MeV"}.items():
            self.add(m, 1, lambda v, s=s: f"{v} {s}")
        self.add("emph", 1, lambda a: f"*{a}*")
        self.add("textit", 1, lambda a: f"*{a}*")
        self.add("textbf", 1, lambda a: f"**{a}**")
        self.add("textsuperscript", 1, lambda a: f"<sup>{a}</sup>")
        self.add("textsubscript", 1, lambda a: a)
        self.add("textcolor", 2, lambda c, a: a)
        self.add("ref", 1, lambda a: a.split(":", 1)[-1])
        self.add("cite", 1, lambda a: f"[{a}]")
        self.add("label", 1, lambda a: "")
        self.add("thumb", 1, lambda a: "")              # read by Entry.thumb, not shown in the text
        self.add("location", 3, lambda la, lo, name: "")  # read by Entry.location
        self.add("doi", 1, lambda a: f"doi:{a}")
        self.add("href", 2, lambda url, a: a)
        self.add("url", 1, lambda a: a)

    # --- extension points -------------------------------------------------------

    def add(self, name: str, nargs: int, fn: Handler) -> None:
        """Register (or replace, keeping its place) a macro handler."""
        self.macros[name] = (nargs, fn)

    def add_template(self, name: str, template: str) -> None:
        """A handler from a string: {1}.. are arguments, {n:unit} and {n:md} filter them."""
        slots = [int(m) for m in re.findall(r"\{(\d+)(?::\w+)?\}", template)]
        nargs = max(slots, default=0)

        def fn(*args: str) -> str:
            def sub(m: re.Match) -> str:
                a = args[int(m.group(1)) - 1]
                f = m.group(2)
                return self.unit(a) if f == "unit" else self.to_md(a) if f == "md" else a
            return re.sub(r"\{(\d+)(?::(\w+))?\}", sub, template)
        self.add(name, nargs, fn)

    def load_plugins(self, names: list[str], folder) -> None:
        if not names:
            return
        sys.path.insert(0, str(folder))
        for name in names:
            importlib.import_module(name).register(self)

    # --- conversion ---------------------------------------------------------------

    def unit(self, s: str) -> str:
        s = s.strip()
        return self.units.get(s, s.lstrip("\\"))

    def to_md(self, tex: str) -> str:
        t = "\n".join(l for l in tex.splitlines() if not l.lstrip().startswith("%"))
        t = re.sub(r"(?<!\\)%.*", "", t)                       # trailing comments
        for name, (nargs, fn) in self.macros.items():
            t = expand(t, name, nargs, fn)
        t = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", r"\n\n![](\1)\n\n", t)
        t = expand(t, "paragraph", 1, lambda a: f"\n\n**{a}**\n\n")
        t = re.sub(r"\\begin\{(?:itemize|enumerate)\}|\\end\{(?:itemize|enumerate)\}", "\n", t)
        t = re.sub(r"\\begin\{quote\}(.*?)\\end\{quote\}",
                   lambda m: "\n> " + " ".join(m.group(1).split()) + "\n", t, flags=re.S)
        t = re.sub(r"^\s*\\item\s*", "- ", t, flags=re.M)
        t = re.sub(r"\$([^$]+)\$", r"`\1`", t)
        for acc, plain, accented in ACCENTS:
            for p, a in zip(plain, accented):
                t = t.replace(f"\\{acc}{p}", a).replace(f"\\{acc}{{{p}}}", a)
        for k, v in BRACED_ACCENTS.items():
            t = t.replace(k, v)
        t = t.replace("\\\\", " ").replace("\\ ", " ").replace("~", " ")
        t = t.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
        t = t.replace("\\%", "%").replace("\\&", "&").replace("\\$", "$").replace("\\_", "_")
        t = t.replace("\\S", "§").replace("\\textdegree", "°").replace("{,}", ",")
        t = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", t)     # any leftover \cmd{arg}
        t = re.sub(r"\\[A-Za-z]+", "", t)
        t = t.replace("{", "").replace("}", "")
        # join hard-wrapped lines inside a paragraph; keep list items, quotes, images
        out: list[str] = []
        for line in t.splitlines():
            s = line.strip()
            if not s:
                out.append("")
            elif out and out[-1] and not s.startswith(("- ", ">", "![")) \
                    and not out[-1].startswith("!["):
                out[-1] += " " + s
            else:
                out.append(s)
        return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
