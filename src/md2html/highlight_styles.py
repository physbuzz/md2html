"""Wolfram palettes used with the default Pygments light and dark themes."""

from mathematica import MathematicaStyle
from pygments.style import Style
from pygments.token import Comment, Error, Name, Number, Operator, Punctuation, String, Text


class WolframLightStyle(MathematicaStyle):
    """Mathematica colors with black built-ins and an explicit text foreground."""

    styles = {**MathematicaStyle.styles, Text: "#24292f", Name.Builtin: "#000000"}


class WolframDarkStyle(Style):
    """Distinguish symbols, patterns, locals, and built-ins on a dark background."""

    background_color = "#0d1117"
    styles = {
        Text: "#e6edf3",
        Comment: "italic #8b949e",
        Name.Builtin: "#e6edf3",
        Name.Variable: "#79c0ff",
        Name.Variable.Class: "#7ee787",
        Name.Tag: "italic #7ee787",
        Name.Function: "italic #7ee787",
        Name.Exception: "#ff7b72",
        Number: "#ffa657",
        String: "#a5d6ff",
        Operator: "#c9d1d9",
        Punctuation: "#c9d1d9",
        Error: "#ff7b72",
    }
