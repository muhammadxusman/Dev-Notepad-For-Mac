from __future__ import annotations

import re
from dataclasses import dataclass

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


@dataclass(frozen=True)
class Rule:
    pattern: str
    color: str
    bold: bool = False
    italic: bool = False


def make_format(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class SyntaxHighlighter(QSyntaxHighlighter):
    """Small regex highlighter tuned for scratchpad readability, not full parsing."""

    def __init__(self, document, language: str = "Plain Text") -> None:
        super().__init__(document)
        self.language = language
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self.set_language(language)

    def set_language(self, language: str) -> None:
        self.language = language
        self._rules = [
            (QRegularExpression(rule.pattern), make_format(rule.color, rule.bold, rule.italic))
            for rule in self._language_rules(language)
        ]
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        for expression, fmt in self._rules:
            match = expression.globalMatch(text)
            while match.hasNext():
                item = match.next()
                self.setFormat(item.capturedStart(), item.capturedLength(), fmt)

    def _language_rules(self, language: str) -> list[Rule]:
        common = [
            Rule(r'"(?:\\.|[^"\\])*"', "#a5d6ff"),
            Rule(r"'(?:\\.|[^'\\])*'", "#a5d6ff"),
            Rule(r"\b\d+(?:\.\d+)?\b", "#79c0ff"),
            Rule(r"\b(TODO|FIXME|NOTE|HACK)\b", "#ffa657", True),
        ]
        comments = {
            "Python": [Rule(r"#.*$", "#8b949e", italic=True)],
            "JavaScript": [Rule(r"//.*$", "#8b949e", italic=True), Rule(r"/\*.*\*/", "#8b949e", italic=True)],
            "TypeScript": [Rule(r"//.*$", "#8b949e", italic=True), Rule(r"/\*.*\*/", "#8b949e", italic=True)],
            "CSS": [Rule(r"/\*.*\*/", "#8b949e", italic=True)],
            "Bash": [Rule(r"#.*$", "#8b949e", italic=True)],
            "SQL": [Rule(r"--.*$", "#8b949e", italic=True)],
            "YAML": [Rule(r"#.*$", "#8b949e", italic=True)],
            "Markdown": [Rule(r"^#{1,6}\s.*$", "#d2a8ff", True), Rule(r"`[^`]+`", "#a5d6ff")],
        }
        keyword_map = {
            "Python": r"\b(False|None|True|and|as|assert|async|await|break|class|continue|def|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b",
            "JavaScript": r"\b(await|async|break|case|catch|class|const|continue|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|null|return|switch|this|throw|try|typeof|undefined|var|while|yield)\b",
            "TypeScript": r"\b(await|async|break|case|catch|class|const|continue|default|delete|do|else|enum|export|extends|finally|for|from|function|if|implements|import|interface|let|namespace|new|null|private|protected|public|readonly|return|type|switch|this|throw|try|typeof|undefined|var|while|yield)\b",
            "JSON": r"\b(true|false|null)\b",
            "HTML": r"</?[\w:-]+|/?>",
            "CSS": r"\b(display|grid|flex|color|background|border|padding|margin|font|position|width|height|content|align-items|justify-content)\b",
            "Bash": r"\b(alias|awk|case|cat|cd|curl|do|done|echo|elif|else|export|fi|for|function|grep|if|in|mkdir|rm|sed|set|then|while)\b",
            "SQL": r"\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|INSERT|INTO|UPDATE|DELETE|CREATE|ALTER|DROP|TABLE|ORDER|GROUP|BY|HAVING|LIMIT|OFFSET|VALUES|AND|OR|NOT|NULL|IS|AS|ON|CASE|WHEN|THEN|END)\b",
            "YAML": r"^\s*[\w.-]+\s*:",
        }
        rules = list(common)
        if language in keyword_map:
            rules.append(Rule(keyword_map[language], "#ff7b72", True))
        if language == "HTML":
            rules.extend([Rule(r"\s[\w:-]+=", "#79c0ff"), Rule(r"<!--.*-->", "#8b949e", italic=True)])
        if language == "CSS":
            rules.extend([Rule(r"[.#]?[\w-]+(?=\s*\{)", "#d2a8ff", True), Rule(r"#[0-9a-fA-F]{3,8}\b", "#79c0ff")])
        if language == "Markdown":
            rules.extend([Rule(r"\*\*[^*]+\*\*", "#ffa657", True), Rule(r"\[[^\]]+\]\([^)]+\)", "#7ee787")])
        rules.extend(comments.get(language, []))
        return rules


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

