from PIL import Image, ImageDraw


def draw_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    p = max(1, int(size * 0.06))
    mid = size // 2
    gap = max(1, size // 8)

    # Background rounded rectangle
    radius = max(2, int(size * 0.18))
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(30, 41, 59, 255))

    # Left: perspective trapezoid (amber) — wider at bottom, narrower at top
    lx0 = p * 2
    lx1 = mid - gap
    inset = int((lx1 - lx0) * 0.38)
    trap = [
        (lx0 + inset, p * 2),
        (lx1,          p * 2),
        (lx1,          size - p * 2),
        (lx0,          size - p * 2),
    ]
    stroke = max(1, size // 48)
    d.polygon(trap, fill=(251, 191, 36, 210))
    d.line(trap + [trap[0]], fill=(253, 224, 71, 255), width=stroke)

    # Arrow (white)
    ax0 = mid - gap + max(1, size // 16)
    ax1 = mid + gap - max(1, size // 16)
    ay  = size // 2
    lw  = max(1, size // 32)
    ah  = max(2, size // 12)
    aw  = max(2, size // 10)
    d.line([(ax0, ay), (ax1 - aw, ay)], fill=(255, 255, 255, 210), width=lw)
    d.polygon(
        [(ax1, ay), (ax1 - aw, ay - ah), (ax1 - aw, ay + ah)],
        fill=(255, 255, 255, 210),
    )

    # Right: clean rectangle (blue)
    rx0, rx1 = mid + gap, size - p * 2
    ry0, ry1 = p * 2,     size - p * 2
    d.rectangle([rx0, ry0, rx1, ry1], fill=(59, 130, 246, 210))
    d.rectangle([rx0, ry0, rx1, ry1], outline=(147, 197, 253, 255), width=stroke)

    return img


frame = draw_frame(256)
frame.save(
    "icon.ico",
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("Generated icon.ico")
