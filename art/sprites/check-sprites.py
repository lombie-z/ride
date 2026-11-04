#!/usr/bin/env python3
"""Contact sheets, the loop check and the edge check for art/sprites/*.png.

    python3 art/sprites/check-sprites.py [names...]

Writes contact-<name>.png and loop-check.png, prints the numbers, and saves them to
qa.json beside the sheets.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
F = 128
T = 64
# Tint as used and the dark it sits on, sampled by eye from the concepts.
USE = {
    "steam-billow": dict(tint=(214, 236, 218), bg=(14, 20, 16), opacity=0.85, stretch=(1, 1)),
    "fog-bank": dict(tint=(84, 150, 92), bg=(8, 15, 9), opacity=0.9, stretch=(4, 1)),
    "sand-gust": dict(tint=(205, 140, 76), bg=(32, 22, 14), opacity=0.9, stretch=(3, 1)),
    "steam-rise": dict(tint=(214, 236, 218), bg=(10, 16, 13), opacity=0.8, stretch=(1, 2)),
    "light-shaft": dict(tint=(205, 240, 214), bg=(8, 13, 10), opacity=1.0, stretch=(1, 2)),
}


def font(size):
    for p in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Supplemental/Courier New.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load(name):
    a = np.asarray(Image.open(f"{HERE}/{name}.png").convert("L"), dtype=np.uint8)
    return np.stack([a[(t // 8) * F:(t // 8 + 1) * F, (t % 8) * F:(t % 8 + 1) * F] for t in range(T)])


def tinted(d, use):
    """Premultiplied over: bg * (1 - a) + tint * a, a = density * opacity."""
    a = (d.astype(np.float32) / 255 * use["opacity"])[..., None]
    rgb = np.array(use["bg"], np.float32) * (1 - a) + np.array(use["tint"], np.float32) * a
    return np.clip(rgb, 0, 255).astype(np.uint8)


def contact(name, frames):
    """8 frames in a row; under them either the same on its card, or (square cards) 8 consecutive frames."""
    use = USE[name]
    picks = list(range(0, T, 8))
    scale = 2
    W = F * 8 * scale
    strip = np.concatenate([tinted(frames[t], use) for t in picks], axis=1)
    strip = Image.fromarray(strip).resize((W, F * scale), Image.BICUBIC)
    sx, sy = use["stretch"]
    if (sx, sy) == (1, 1):
        ts, tw, th = list(range(8)), F * scale, F * scale
        label = "frames 0-7, consecutive"
    elif sy > 1:
        ts, tw, th = picks, F * sx, F * sy
        label = f"on its {sx}:{sy} card, same frames"
    else:
        n = 8 // sx if sx != 3 else 3
        ts, tw, th = [i * T // n for i in range(n)], W // n, W // n // sx
        label = f"on its {sx}:{sy} card, {n} frames evenly spaced"
    cell = W // len(ts)
    row = Image.new("RGB", (W, th), use["bg"])
    for i, t in enumerate(ts):
        im = Image.fromarray(tinted(frames[t], use)).resize((tw, th), Image.BICUBIC)
        row.paste(im, (i * cell + (cell - tw) // 2, 0))
    pad = 26
    out = Image.new("RGB", (W, pad + F * scale + pad + th), (6, 8, 7))
    dr = ImageDraw.Draw(out)
    f = font(15)
    dr.text((8, 4), f"{name}: frames {picks}, tinted as used", fill=(190, 200, 190), font=f)
    out.paste(strip, (0, pad))
    dr.text((8, pad + F * scale + 4), label, fill=(190, 200, 190), font=f)
    out.paste(row, (0, pad + F * scale + pad))
    out.save(f"{HERE}/contact-{name}.png", optimize=True)


def measure(name, frames):
    f = frames.astype(np.float32)
    steps = np.abs(np.roll(f, -1, axis=0) - f).mean(axis=(1, 2))  # steps[63] is last -> first
    seam = float(steps[-1])
    normal = steps[:-1]
    rms = np.sqrt(((np.roll(f, -1, axis=0) - f) ** 2).mean(axis=(1, 2)))
    outer = np.ones((F, F), bool)
    outer[4:-4, 4:-4] = False
    outer_max = int(frames[:, outer].max())
    outer_mean = float(frames[:, outer].mean())
    # How far in from the frame's edge the first non-zero pixel ever gets, over all frames.
    any_on = frames.max(axis=0) > 0
    rows = np.where(any_on.any(axis=1))[0]
    cols = np.where(any_on.any(axis=0))[0]
    gap = min(rows[0], cols[0], F - 1 - rows[-1], F - 1 - cols[-1]) if rows.size else F
    means = f.mean(axis=(1, 2))
    return dict(
        size_kb=round(os.path.getsize(f"{HERE}/{name}.png") / 1024, 1),
        seam_mae=round(seam, 3),
        step_mae_mean=round(float(normal.mean()), 3),
        step_mae_min=round(float(normal.min()), 3),
        step_mae_max=round(float(normal.max()), 3),
        seam_over_mean=round(seam / float(normal.mean()), 3),
        seam_rms=round(float(rms[-1]), 3),
        step_rms_mean=round(float(rms[:-1].mean()), 3),
        outer4px_max=outer_max,
        outer4px_mean=round(outer_mean, 4),
        first_lit_px_from_edge=int(gap),
        mean_density=round(float(f.mean()), 2),
        pulse_pct=round(float((means.max() - means.min()) / means.mean() * 100), 1),
        max=int(frames.max()),
        clipped_pct=round(float((frames >= 254).mean() * 100), 3),
    )


def loop_row(name, frames, m):
    """One row: last, first, seam diff, ordinary step diff, step sparkline, x-t and y-t tiled twice."""
    gain = 8
    rowh = F + 34
    tiles = []
    a, b = frames[-1].astype(np.float32), frames[0].astype(np.float32)
    mid = frames[T // 2].astype(np.float32), frames[T // 2 + 1].astype(np.float32)
    avg = np.abs(np.roll(frames.astype(np.float32), -1, axis=0) - frames)[:-1].mean(axis=0)
    tiles.append(("last (63)", a))
    tiles.append(("first (0)", b))
    tiles.append((f"|63-0| x{gain}", np.abs(a - b) * gain))
    tiles.append((f"avg |n-(n+1)| x{gain}", avg * gain))
    tiles.append((f"|32-33| x{gain}", np.abs(mid[0] - mid[1]) * gain))
    # Space-time slices through the densest row and column, the loop shown twice over.
    means_r = frames.mean(axis=(0, 2)); means_c = frames.mean(axis=(0, 1))
    r = int(np.argmax(means_r)); c = int(np.argmax(means_c))
    xt = np.concatenate([frames[:, r, :], frames[:, r, :]], axis=0)
    yt = np.concatenate([frames[:, :, c], frames[:, :, c]], axis=0).T
    w = F * 5 + 8 * 5 + 300 + 8 + F + 8 + F * 2 + 16
    row = Image.new("RGB", (w, rowh), (10, 12, 11))
    dr = ImageDraw.Draw(row)
    f = font(11)
    x = 8
    for label, im in tiles:
        row.paste(Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).convert("RGB"), (x, 18))
        dr.text((x, 3), label, fill=(170, 180, 170), font=f)
        x += F + 8
    # Sparkline of every step, the seam in amber.
    f32 = frames.astype(np.float32)
    steps = np.abs(np.roll(f32, -1, axis=0) - f32).mean(axis=(1, 2))
    top = max(float(steps.max()) * 1.15, 1e-3)
    dr.text((x, 3), f"step size per frame, seam amber (max {steps.max():.2f})", fill=(170, 180, 170), font=f)
    for i, s in enumerate(steps):
        hh = int(s / top * (F - 4))
        col = (240, 170, 60) if i == T - 1 else (110, 190, 130)
        dr.rectangle([x + i * 4, 18 + F - hh, x + i * 4 + 2, 18 + F], fill=col)
    dr.rectangle([x, 18, x + 256, 18 + 56], fill=(10, 12, 11))
    dr.text((x + 4, 22), f"{name}\nseam {m['seam_mae']} / mean step {m['step_mae_mean']} = x{m['seam_over_mean']}\n"
                         f"(range {m['step_mae_min']}..{m['step_mae_max']})\nouter 4px max {m['outer4px_max']}",
            fill=(235, 235, 225), font=f)
    x += 300
    row.paste(Image.fromarray(xt).resize((F, F), Image.BILINEAR).convert("RGB"), (x, 18))
    dr.text((x, 3), "x / t, x2 loops", fill=(170, 180, 170), font=f)
    x += F + 8
    row.paste(Image.fromarray(yt).resize((F * 2, F), Image.BILINEAR).convert("RGB"), (x, 18))
    dr.text((x, 3), "t / y, x2 loops", fill=(170, 180, 170), font=f)
    return row


def main():
    names = sys.argv[1:] or list(USE)
    qa_path = f"{HERE}/qa.json"
    qa = json.load(open(qa_path)) if os.path.exists(qa_path) else {}
    for name in names:
        frames = load(name)
        contact(name, frames)
        qa[name] = measure(name, frames)
        m = qa[name]
        print(f"{name:13s} {m['size_kb']:6.1f} KB  seam {m['seam_mae']:.3f} / step {m['step_mae_mean']:.3f} "
              f"(x{m['seam_over_mean']:.2f}; range {m['step_mae_min']:.2f}-{m['step_mae_max']:.2f})  "
              f"outer4 max {m['outer4px_max']} mean {m['outer4px_mean']}  first lit {m['first_lit_px_from_edge']}px  "
              f"mean {m['mean_density']} pulse {m['pulse_pct']}% max {m['max']} clip {m['clipped_pct']}%")
    json.dump(qa, open(qa_path, "w"), indent=1)
    done = [n for n in USE if os.path.exists(f"{HERE}/{n}.png") and n in qa]
    rows = [loop_row(n, load(n), qa[n]) for n in done]
    w = max(r.width for r in rows)
    out = Image.new("RGB", (w, sum(r.height for r in rows)), (10, 12, 11))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    out.save(f"{HERE}/loop-check.png", optimize=True)


if __name__ == "__main__":
    main()
