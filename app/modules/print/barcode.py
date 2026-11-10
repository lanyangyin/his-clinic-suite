"""Code128-B barcode renderer (SVG, no external dependency)."""

# Code 128 patterns, 11 modules each; index 106 is STOP, 107 is the final bar.
PATTERNS = [
    "11011001100", "11001101100", "11001100110", "10010011000",
    "10010001100", "10001001100", "10011001000", "10011000100",
    "10001100100", "11001001000", "11001000100", "11000100100",
    "10110011100", "10011011100", "10011001110", "10111001100",
    "10011101100", "10011100110", "11001110010", "11001011100",
    "11001001110", "11011100100", "11001110100", "11101101110",
    "11101001100", "11100101100", "11100100110", "11101100100",
    "11100110100", "11100110010", "11011011000", "11011000110",
    "11000110110", "10100011000", "10001011000", "10001000110",
    "10110001000", "10001101000", "10001100010", "11010001000",
    "11000101000", "11000100010", "10110111000", "10110001110",
    "10001101110", "10111011000", "10111000110", "10001110110",
    "11101110110", "11010001110", "11000101110", "11011101000",
    "11011100010", "11011101110", "11101011000", "11101000110",
    "11100010110", "11101101000", "11101100010", "11100011010",
    "11101111010", "11001000010", "11110001010", "10100110000",
    "10100001100", "10010110000", "10010000110", "10000101100",
    "10000100110", "10110010000", "10110000100", "10011010000",
    "10011000010", "10000110100", "10000110010", "11000010010",
    "11001010000", "11110111010", "11000010100", "10001111010",
    "10100111100", "10010111100", "10010011110", "10111100100",
    "10011110100", "10011110010", "11110100100", "11110010100",
    "11110010010", "11011011110", "11011110110", "11110110110",
    "10101111000", "10100011110", "10001011110", "10111101000",
    "10111100010", "11110101000", "11110100010", "10111011110",
    "10111101110", "11101011110", "11110101110", "11010000100",
    "11010010000", "11010011100", "11000111010", "11",
]

START_B = 104
STOP = 106
QUIET_MODULES = 10


def encode_bits(text: str) -> str:
    """Return the Code128-B module bit string (1 = bar, 0 = space)."""
    if not text:
        raise ValueError("条码内容不能为空")
    if any(ord(char) < 32 or ord(char) > 126 for char in text):
        raise ValueError("Code128-B 仅支持 ASCII 32-126")
    bits = PATTERNS[START_B]
    total = START_B
    for position, char in enumerate(text, 1):
        value = ord(char) - 32
        total += value * position
        bits += PATTERNS[value]
    bits += PATTERNS[total % 103]
    bits += PATTERNS[STOP]
    bits += PATTERNS[107]
    return bits


def code128_svg(text: str, module: int = 2, height: int = 54) -> str:
    """Render a scannable Code128-B SVG with quiet zones."""
    bits = encode_bits(text)
    width = (len(bits) + QUIET_MODULES * 2) * module
    rects = []
    x = QUIET_MODULES
    index = 0
    while index < len(bits):
        if bits[index] == "1":
            run = 0
            while index + run < len(bits) and bits[index + run] == "1":
                run += 1
            rects.append(
                f'<rect x="{x * module}" y="0" width="{run * module}" height="{height}"/>'
            )
            x += run
            index += run
        else:
            x += 1
            index += 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" shape-rendering="crispEdges" '
        f'role="img" aria-label="Code128 {text}">'
        f'<rect width="{width}" height="{height}" fill="#fff"/>'
        f'<g fill="#000">{"".join(rects)}</g>'
        f"</svg>"
    )
