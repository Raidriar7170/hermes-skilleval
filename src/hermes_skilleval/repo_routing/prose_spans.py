"""Original-character positions for conservative prose-aside correction.

Recognizes fenced/indented blocks and equal-length backtick spans. Container,
HTML, escaped delimiter and unclosed syntax is deliberately fail-closed. This
is a small safety filter, not a CommonMark renderer or conformance claim.
"""

import ast
import re


def prose_call_spans(text):
    protected = []
    uncertainty = []
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        if fence:
            protected.append((offset, end))
            marker, length = fence
            if re.fullmatch(
                r" {0,3}" + re.escape(marker) + "{" + str(length) + r",}[ \t]*[\r\n]*",
                line,
            ):
                fence = None
        else:
            opening = re.match(r" {0,3}(`{3,}|~{3,})(.*)", line)
            if opening:
                fence = (opening[1][0], len(opening[1]))
                protected.append((offset, end))
                if fence[0] == "`" and "`" in opening[2]:
                    uncertainty.append("ambiguous_fence_info")
            elif (
                len(line) - len(line.lstrip(" \t")) > 0
                and len(line[: len(line) - len(line.lstrip(" \t"))].expandtabs(4)) >= 4
            ):
                protected.append((offset, end))
            elif re.match(r" {0,3}(?:>|[-+*] |\d+[.)] |<)", line):
                uncertainty.append("unsupported_container_or_html")
        offset = end
    if fence:
        uncertainty.append("unclosed_fence")
    if re.search(r"</?[A-Za-z][^>]*>", text):
        uncertainty.append("unsupported_inline_html")
    if re.search(r"\\[`~]", text):
        uncertainty.append("escaped_delimiter")

    def overlaps(a, b):
        return any(a < y and b > x for x, y in protected)

    runs = list(re.finditer(r"`+", text))
    i = 0
    while i < len(runs):
        run = runs[i]
        if overlaps(*run.span()):
            i += 1
            continue
        j = i + 1
        while j < len(runs):
            other = runs[j]
            if overlaps(run.start(), other.end()):
                break
            if len(other[0]) == len(run[0]):
                protected.append((run.start(), other.end()))
                i = j
                break
            j += 1
        else:
            j = len(runs)
        if j == len(runs) or i != j:
            uncertainty.append("unclosed_or_cross_block_code_span")
        i += 1
    candidates = re.finditer(
        r"\b[A-Za-z_]\w*[ \t]+\((?:the |maybe |an |a |e\.g\.|i\.e\.)[^()\r\n]*\)", text
    )
    spans = []
    for match in candidates:
        if overlaps(*match.span()):
            continue
        body = match[0].split("(", 1)[1][:-1]
        try:
            ast.parse(body, mode="eval")
        except SyntaxError:
            spans.append(match.span())
        # A syntactically valid expression is ambiguous even outside markup.
        # Parsing checks syntax only; it never executes the expression.
    return spans, sorted(protected), sorted(set(uncertainty))
