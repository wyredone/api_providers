"""Small safe Markdown renderer for Tk text. No HTML execution or remote fetching."""
import re
from tkinter import font

INLINE = re.compile(r"(`[^`\n]+`|\*\*[^*\n]+\*\*|(?<!\*)\*[^*\n]+\*(?!\*)|\[[^\]\n]+\]\([^\s)]+\))")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})([^\n]*)$")


def blocks(text):
    fence = None
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line.rstrip("\r\n"))
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                yield "code_end", "\n"
                fence = None
            else:
                yield "code", line
        elif marker:
            fence = marker.group(1)
            yield "code_start", marker.group(2).strip() or "code"
        else:
            heading = re.match(r"^(#{1,6})\s+(.+?)(?:\n)?$", line)
            if heading:
                yield "heading", heading.group(2) + "\n"
            elif re.match(r"^\s*[-*+]\s+", line):
                yield "text", re.sub(r"^\s*[-*+]\s+", "• ", line)
            elif line.startswith("> "):
                yield "quote", line[2:]
            else:
                yield "text", line


def inline(text):
    for piece in INLINE.split(text):
        if piece.startswith("**") and piece.endswith("**"):
            yield piece[2:-2], "bold"
        elif piece.startswith("`") and piece.endswith("`"):
            yield piece[1:-1], "inline_code"
        elif piece.startswith("*") and piece.endswith("*"):
            yield piece[1:-1], "italic"
        elif re.fullmatch(r"\[[^\]]+\]\([^\s)]+\)", piece):
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", piece).groups()
            yield label + " (" + url + ")", "link"
        elif piece:
            yield piece, ""


def code_blocks(text):
    result, buffer, language = [], None, ""
    for kind, value in blocks(text):
        if kind == "code_start":
            buffer, language = [], value
        elif kind == "code" and buffer is not None:
            buffer.append(value)
        elif kind == "code_end" and buffer is not None:
            result.append((language, "".join(buffer)))
            buffer = None
    if buffer is not None:
        result.append((language, "".join(buffer)))
    return result


def configure(widget):
    base = font.nametofont("TkDefaultFont", root=widget)
    bold = base.copy(); bold.configure(weight="bold")
    italic = base.copy(); italic.configure(slant="italic")
    heading = base.copy(); heading.configure(weight="bold", size=base.cget("size") + 2)
    widget._markdown_fonts = (bold, italic, heading)
    widget.tag_configure("bold", font=bold)
    widget.tag_configure("italic", font=italic)
    widget.tag_configure("heading", font=heading, spacing1=6, spacing3=4)
    widget.tag_configure("code", font="TkFixedFont", background="#eef1f5", lmargin1=12, lmargin2=12, spacing1=2, spacing3=2, wrap="none")
    widget.tag_configure("inline_code", font="TkFixedFont", background="#eef1f5")
    widget.tag_configure("quote", foreground="#657080", lmargin1=12, lmargin2=12)
    widget.tag_configure("link", foreground="#145da0", underline=True)
    widget.tag_configure("code_start", foreground="#657080", font="TkFixedFont")


def insert(widget, text):
    for kind, value in blocks(text):
        if kind == "code_start":
            widget.insert("end", value + "\n", ("code_start",))
        elif kind == "code":
            widget.insert("end", value, ("code",))
        elif kind == "code_end":
            widget.insert("end", value)
        else:
            for piece, tag in inline(value):
                tags = tuple(x for x in (kind if kind != "text" else "", tag) if x)
                widget.insert("end", piece, tags)
