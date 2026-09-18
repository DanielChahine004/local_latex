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

MATH = {
    r"\rightarrow": "→", r"\leftarrow": "←", r"\to": "→", r"\pm": "±", r"\mp": "∓",
    r"\geq": "≥", r"\leq": "≤", r"\ge": "≥", r"\le": "≤", r"\neq": "≠", r"\sim": "~",
    r"\approx": "≈", r"\propto": "∝", r"\times": "×", r"\cdot": "·", r"\infty": "∞",
    r"\circ": "°", r"\degree": "°", r"\partial": "∂", r"\sum": "Σ", r"\prod": "Π",
    r"\sqrt": "√", r"\ln": "ln", r"\log": "log", r"\exp": "exp",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\Delta": "Δ",
    r"\epsilon": "ε", r"\theta": "θ", r"\lambda": "λ", r"\mu": "µ", r"\nu": "ν",
    r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ", r"\Sigma": "Σ", r"\tau": "τ",
    r"\phi": "φ", r"\chi": "χ", r"\omega": "ω", r"\Omega": "Ω",
}


def math_text(s: str) -> str:
    """Inline math as readable text: symbols, super- and subscripts, no markup."""
    for k in sorted(MATH, key=len, reverse=True):
        s = re.sub(re.escape(k) + r"(?![A-Za-z])", MATH[k], s)
    s = re.sub(r"\\hat\s*\{?(\w)\}?", "\\1\u0302", s)
    s = re.sub(r"\\bar\s*\{?(\w)\}?", "\\1\u0304", s)
    s = re.sub(r"\\(?:mathrm|text|mathbf|mathit|tilde|left|right|big|Big)(?![A-Za-z])", "", s)
    s = re.sub(r"\\[td]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\[td]?frac\s*(\w)(\w)", r"\1/\2", s)
    s = re.sub(r"\((\w)\)/\((\w)\)", r"\1/\2", s)
    s = re.sub(r"\^\{([^{}]*)\}|\^(\S)", lambda m: f"<sup>{m.group(1) or m.group(2)}</sup>", s)
    s = re.sub(r"_\{([^{}]*)\}|_(\S)", lambda m: f"<sub>{m.group(1) or m.group(2)}</sub>", s)
    s = re.sub(r"\\[,;:! ]", " ", s)
    s = re.sub(r"\\[A-Za-z]+", "", s)
    return s.replace("{", "").replace("}", "")


REF_OPEN, REF_CLOSE = "\ue000", "\ue001"   # brackets a reference while its sentence is found

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
        self.labels: dict[str, str] = {}    # key -> readable name, for \ref (set by the renderer)
        self.macros: dict[str, tuple[int, Handler]] = {}   # insertion order is application order
        u = self.unit
        self.add("gap", 1, lambda a: f"**[gap: {self.to_md(a)}]**")
        self.add("aside", 1, lambda a: a)               # shown unless redacted (redact.py)
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
        self.add("ref", 1, self._ref)
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

    def _ref(self, target: str) -> str:
        key = target.split(":", 1)[-1]
        return self.labels.get(key, key)

    def mark_refs(self, tex: str, prefixes: list[str]) -> str:
        """Follow each \\ref{prefix:key} with a marker, so the sentence around it can be found."""
        pat = r"(\\ref\{(?:%s):([^}]+)\})" % "|".join(map(re.escape, prefixes))
        return re.sub(pat, lambda m: f"{m.group(1)}{REF_OPEN}{m.group(2)}{REF_CLOSE}", tex)

    @staticmethod
    def unmark(text: str) -> str:
        return re.sub(f"{REF_OPEN}[^{REF_CLOSE}]*{REF_CLOSE}", "", text)

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
        t = re.sub(r"\\\[(.*?)\\\]", lambda m: "\n\n" + math_text(m.group(1)) + "\n\n", t, flags=re.S)
        t = re.sub(r"(?<!\\)\$([^$]+?)(?<!\\)\$", lambda m: math_text(m.group(1)), t)
        for acc, plain, accented in ACCENTS:
            for p, a in zip(plain, accented):
                t = t.replace(f"\\{acc}{p}", a).replace(f"\\{acc}{{{p}}}", a)
        for k, v in BRACED_ACCENTS.items():
            t = t.replace(k, v)
        t = t.replace("\\\\", " ").replace("~", " ")
        t = re.sub(r"\\(\s)", r"\1", t)                        # "et al.\ " and "al.\" before a line break
        t = re.sub(r"\\[,;:!]", " ", t)
        t = t.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
        t = t.replace("\\%", "%").replace("\\&", "&").replace("\\$", "$").replace("\\_", "_")
        t = t.replace("\\S", "§").replace("\\textdegree", "°").replace("{,}", ",")
        for k in sorted(MATH, key=len, reverse=True):          # \pm and friends outside $...$,
            t = re.sub(re.escape(k) + r"(?![A-Za-z])", MATH[k], t)   # as in \mm{1.4 \pm 0.2}
        t = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", t)     # any leftover \cmd{arg}
        t = re.sub(r"\\[A-Za-z]+", "", t)
        t = t.replace("{", "").replace("}", "")
        t = re.sub(r"(?<=\S)[ \t]{2,}", " ", t)                # stray double spaces
        t = re.sub(r"\b([\w.-]+) \(\1\)", r"\1", t)           # "AnnPET (AnnPET)" from a \ref after its own name
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
