"""Hand-written lexer for the Nimbus language."""

from __future__ import annotations

from .errors import LexError
from .tokens import KEYWORDS, Token, TokenType


class Tokenizer:
    def __init__(self, source: str) -> None:
        self.source = source
        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def scan_tokens(self) -> list[Token]:
        while not self._is_at_end():
            self.start = self.current
            self.column = self._column_of(self.start)
            self._scan_token()
        self.tokens.append(Token(TokenType.EOF, "", None, self.line, self.column))
        return self.tokens

    def _column_of(self, index: int) -> int:
        line_start = self.source.rfind("\n", 0, index) + 1
        return index - line_start + 1

    def _is_at_end(self) -> bool:
        return self.current >= len(self.source)

    def _advance(self) -> str:
        char = self.source[self.current]
        self.current += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _peek(self) -> str:
        return "\0" if self._is_at_end() else self.source[self.current]

    def _peek_next(self) -> str:
        if self.current + 1 >= len(self.source):
            return "\0"
        return self.source[self.current + 1]

    def _match(self, expected: str) -> bool:
        if self._is_at_end() or self.source[self.current] != expected:
            return False
        self._advance()
        return True

    def _add(self, token_type: TokenType, literal: object = None) -> None:
        text = self.source[self.start : self.current]
        self.tokens.append(Token(token_type, text, literal, self.line, self._column_of(self.start)))

    def _scan_token(self) -> None:
        char = self._advance()
        if char == "(":
            self._add(TokenType.LEFT_PAREN)
        elif char == ")":
            self._add(TokenType.RIGHT_PAREN)
        elif char == "{":
            self._add(TokenType.LEFT_BRACE)
        elif char == "}":
            self._add(TokenType.RIGHT_BRACE)
        elif char == "[":
            self._add(TokenType.LEFT_BRACKET)
        elif char == "]":
            self._add(TokenType.RIGHT_BRACKET)
        elif char == ",":
            self._add(TokenType.COMMA)
        elif char == ".":
            self._add(TokenType.DOT)
        elif char == ":":
            self._add(TokenType.COLON)
        elif char == ";":
            self._add(TokenType.SEMICOLON)
        elif char == "+":
            self._add(TokenType.PLUS)
        elif char == "-":
            self._add(TokenType.MINUS)
        elif char == "*":
            self._add(TokenType.STAR)
        elif char == "/":
            if self._match("/"):
                while self._peek() != "\n" and not self._is_at_end():
                    self._advance()
            else:
                self._add(TokenType.SLASH)
        elif char == "%":
            self._add(TokenType.PERCENT)
        elif char == "!":
            self._add(TokenType.BANG_EQUAL if self._match("=") else TokenType.BANG)
        elif char == "=":
            self._add(TokenType.EQUAL_EQUAL if self._match("=") else TokenType.EQUAL)
        elif char == ">":
            self._add(TokenType.GREATER_EQUAL if self._match("=") else TokenType.GREATER)
        elif char == "<":
            self._add(TokenType.LESS_EQUAL if self._match("=") else TokenType.LESS)
        elif char == "#":
            if self._match("{"):
                self._add(TokenType.MAP_OPEN)
            else:
                self._error("unexpected character '#'; use '#{...}' for maps or '//' for comments")
        elif char == '"':
            self._string()
        elif char in " \r\t":
            pass
        elif char == "\n":
            pass
        elif char.isdigit():
            self._number()
        elif char.isalpha() or char == "_":
            self._identifier()
        else:
            self._error(f"unexpected character '{char}'")

    def _string(self) -> None:
        while self._peek() != '"' and not self._is_at_end():
            if self._peek() == "\n":
                self._advance()
            elif self._peek() == "\\":
                self._advance()
                self._escape()
            else:
                self._advance()
        if self._is_at_end():
            self._error("unterminated string")
        self._advance()
        literal = self.source[self.start + 1 : self.current - 1]
        literal = self._decode_escapes(literal)
        self._add(TokenType.STRING, literal)

    def _escape(self) -> None:
        char = self._peek()
        if char not in '"\\nrtbf':
            self._error("invalid escape sequence")
        self._advance()

    def _decode_escapes(self, text: str) -> str:
        replacements = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "b": "\b",
            "f": "\f",
            '"': '"',
            "\\": "\\",
        }
        out: list[str] = []
        i = 0
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in replacements:
                out.append(replacements[text[i + 1]])
                i += 2
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    def _number(self) -> None:
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek_next().isdigit():
            self._advance()
            while self._peek().isdigit():
                self._advance()
        text = self.source[self.start : self.current]
        literal = float(text) if "." in text else int(text)
        self._add(TokenType.NUMBER, literal)

    def _identifier(self) -> None:
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        text = self.source[self.start : self.current]
        token_type = KEYWORDS.get(text, TokenType.IDENTIFIER)
        self._add(token_type)

    def _error(self, message: str) -> None:
        raise LexError(message, self.line, self._column_of(self.start))
