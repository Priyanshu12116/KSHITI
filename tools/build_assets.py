"""Build brand and font assets for the web interface.

1. Wordmarks: "क्षिति" and "KSHITI" in Tillana, shaped with HarfBuzz (so the क्ष
   conjunct and the ि matra are correct) and written out as one SVG path per glyph,
   which the opening animation draws stroke by stroke.
2. Web fonts: WOFF2 subsets of Anek Devanagari, Inter and Tillana (Devanagari +
   Latin only), so the interface loads fast on office networks.

Run: python tools/build_assets.py
"""
from __future__ import annotations

from pathlib import Path

import uharfbuzz as hb
from fontTools import subset
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "app" / "static" / "fonts"
BRAND = ROOT / "app" / "static" / "brand"
WEB = FONTS / "web"


def shaped_paths(font_path: Path, text: str) -> tuple[list[str], float, float, float]:
    """Return per-glyph SVG paths (y flipped), total advance, ascender, descender."""
    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})

    tt = TTFont(str(font_path))
    order = tt.getGlyphOrder()
    glyphs = tt.getGlyphSet()
    asc = tt["hhea"].ascent
    desc = tt["hhea"].descent
    paths, x = [], 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        pen = SVGPathPen(glyphs)
        tpen = TransformPen(pen, (1, 0, 0, -1, x + pos.x_offset, asc - pos.y_offset))
        glyphs[order[info.codepoint]].draw(tpen)
        d = pen.getCommands()
        if d:
            paths.append(d)
        x += pos.x_advance
    return paths, x, asc, desc


def write_wordmark(name: str, font_file: str, text: str, label: str) -> None:
    paths, width, asc, desc = shaped_paths(FONTS / font_file, text)
    height = asc - desc
    pad = 40
    body = "\n".join(f'  <path class="g" style="--i:{i}" d="{d}"/>' for i, d in enumerate(paths))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {width + 2 * pad:.0f} {height + 2 * pad:.0f}" '
        f'role="img" aria-label="{label}">\n<title>{label}</title>\n{body}\n</svg>\n'
    )
    (BRAND / name).write_text(svg, encoding="utf-8")
    print(f"{name}: {len(paths)} glyph paths, {width:.0f}x{height:.0f}")


def web_fonts() -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    unicodes = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0900-097F,U+1CD0-1CF9,U+200C-200D,U+20A8,U+20B9,U+2000-206F,U+2190-21FF,U+2212,U+25CC,U+A830-A839,U+A8E0-A8FF"
    jobs = [
        ("AnekDevanagari.ttf", "AnekDevanagari.woff2"),
        ("Inter.ttf", "Inter.woff2"),
        ("Tillana-SemiBold.ttf", "Tillana-SemiBold.woff2"),
        ("Tillana-Bold.ttf", "Tillana-Bold.woff2"),
    ]
    for src, dst in jobs:
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        f = TTFont(str(FONTS / src))
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=subset.parse_unicodes(unicodes))
        sub.subset(f)
        f.flavor = "woff2"
        f.save(str(WEB / dst))
        print(f"{dst}: {(WEB / dst).stat().st_size // 1024} KB")


def write_favicon() -> None:
    """Orange tile with a black 'क्ष' in Tillana."""
    paths, width, asc, desc = shaped_paths(FONTS / "Tillana-Bold.ttf", "क्ष")
    h = asc - desc
    size = max(width, h) * 1.25
    s = 52 / size
    tx = (64 - width * s) / 2
    ty = (64 - h * s) / 2 + 2
    body = "".join(f'<path d="{d}"/>' for d in paths)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect x="2" y="2" width="60" height="60" rx="8" fill="#EA580C" stroke="#111" stroke-width="4"/>'
        f'<g fill="#111" transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f})">{body}</g></svg>\n'
    )
    (BRAND / "favicon.svg").write_text(svg, encoding="utf-8")
    print("favicon.svg written")


if __name__ == "__main__":
    BRAND.mkdir(parents=True, exist_ok=True)
    write_favicon()
    write_wordmark("wordmark-hi.svg", "Tillana-Bold.ttf", "क्षिति", "Kshiti")
    write_wordmark("wordmark-en.svg", "Tillana-Bold.ttf", "KSHITI", "Kshiti")
    web_fonts()
