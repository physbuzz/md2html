"""Metamath source highlighting, including ordinary and compressed proofs."""

from pygments.lexer import RegexLexer, include
from pygments.token import Comment, Keyword, Name, Punctuation, String, Text, Whitespace


class MetamathLexer(RegexLexer):
    name = "Metamath"
    aliases = ["metamath", "mm"]
    filenames = ["*.mm"]

    tokens = {
        "common": [
            (r"\s+", Whitespace),
            (r"\$\(", Comment.Multiline, "comment"),
        ],
        "comment": [
            (r"\$\)", Comment.Multiline, "#pop"),
            (r"[^$]+|\$", Comment.Multiline),
        ],
        "root": [
            include("common"),
            (r"\$\[", Comment.Preproc, "include"),
            (r"\$[{}.]", Punctuation),
            (r"\$[cvdfeap]", Keyword, "statement"),
            (r"[^\s$]+", Name.Label),
            (r"\$", Text),
        ],
        "include": [
            include("common"),
            (r"\$\]", Comment.Preproc, "#pop"),
            (r"[^\s$]+", String),
            (r"\$", Text),
        ],
        "statement": [
            include("common"),
            (r"\$\.", Punctuation, "#pop"),
            (r"\$=", Keyword, ("#pop", "proof")),
            (r"[^\s$]+", Name),
            (r"\$", Text),
        ],
        "proof": [
            include("common"),
            (r"\$\.", Punctuation, "#pop"),
            (r"\((?=\s|$)", Punctuation, ("#pop", "compressed-labels")),
            (r"[^\s$]+", Name.Label),
            (r"\$", Text),
        ],
        "compressed-labels": [
            include("common"),
            (r"\)(?=\s|$)", Punctuation, ("#pop", "compressed")),
            (r"\$\.", Punctuation, "#pop"),
            (r"[^\s$]+", Name.Label),
            (r"\$", Text),
        ],
        "compressed": [
            include("common"),
            (r"\$\.", Punctuation, "#pop"),
            (r"[^\s$]+", String.Other),
            (r"\$", Text),
        ],
    }
