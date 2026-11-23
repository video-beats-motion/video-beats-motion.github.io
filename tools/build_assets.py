"""Build every media asset the project page uses, from the raw research folders.

Run from anywhere:   python tools/build_assets.py
Needs ffmpeg/ffprobe and pdftoppm (poppler) on PATH, and Pillow.

Inputs live one level above this repo (the "Website" folder):
    ../Video_Models_Are_Excellent_Motion_Models.pdf
    ../teaser_video.mp4
    ../figures/*.pdf
    ../paper_motions_final/{A_Range,B_Video-to-Motion,C_Motion-to-Video,D-Failure_cases}/<clip>/animation.mp4

Outputs (all under static/):
    results/<EXP>/<slug>.mp4   remuxed with +faststart (no re-encode, no quality loss)
    results/<EXP>/<slug>.jpg   thumbnail cropped to the 3D viewport
    videos/teaser.mp4 (+ poster), videos/wall.mp4 (+ poster)   hero background mosaic
    figures/*.webp, figures/og.jpg, paper.pdf
    js/data.js                 the clip list read by app.js

To add, remove or reorder clips, edit CLIPS below and re-run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SRC = REPO.parent
RAW = SRC / "paper_motions_final"
OUT = REPO / "static"

EXP_DIRS = {
    "A": "A_Range",
    "B": "B_Video-to-Motion",
    "C": "C_Motion-to-Video",
    "D": "D-Failure_cases",
}

# 3D-viewport box of each experiment's render layout, as fractions of the frame
# (x0, y0, x1, y1). Thumbnails and the hero wall crop to this.
# The bottom edge stops just above each layout's legend box.
VIEWPORT = {
    "A": (0.015, 0.118, 0.658, 0.780),
    "B": (0.015, 0.118, 0.716, 0.625),
    "C": (0.015, 0.118, 0.530, 0.645),
    "D": (0.015, 0.118, 0.742, 0.780),
}

# (folder-name prefix, display prompt, tags). Order here is display order.
CLIPS = {
    "A": [
        ("A631_", "A person walks forward while holding a coffee cup and talking on a phone.", ["Simultaneous"]),
        ("A1416_", "A person walks to a ladder, climbs up, and sits at the top.", ["Sequential", "Interaction"]),
        ("A518_", "A person walks forward while carrying a box.", ["Simultaneous", "Interaction"]),
        ("A1273_", "A person dribbles a soccer ball while running.", ["Simultaneous"]),
        ("A228_", "A person swings a tennis racket.", []),
        ("A192_", "A person sweeps the floor with a broom.", ["Interaction"]),
        ("A466_", "A person walks forward with the arms out like airplane wings.", ["Simultaneous"]),
        ("A344_", "A person marches in place while clapping.", ["Simultaneous"]),
        ("A278_", "A person juggles three balls.", []),
        ("A144_", "A person mimes shooting a basketball.", []),
        ("A140_", "A person mimes a volleyball spike.", []),
        ("A141_", "A person mimes bowling a ball.", []),
        ("A105_", "A person stretches after waking up.", []),
        ("U001_", "A person is walking while talking on a phone while holding a coffee cup.", ["Simultaneous"]),
    ],
    "B": [
        ("A616_", "A person lunges forward while punching with the opposite hand.", ["Simultaneous"]),
        ("A698_", "A person turns around, then waves.", ["Sequential"]),
        ("A138_", "A person mimes a golf swing.", []),
        ("A163_a_person_throws_a_hook_punch_s5678_k5", "A person throws a hook punch.", ["K = 5"]),
        ("A163_a_person_throws_a_hook_punch_s5678_k8", "A person throws a hook punch.", ["K = 8"]),
        ("A281_", "A person climbs a rock wall.", ["Interaction"]),
        ("A139_", "A person mimes a tennis serve.", []),
        ("A308_", "A person squats down while clapping.", ["Simultaneous"]),
        ("A017_", "A person twists the torso left and right.", []),
        ("A061_", "A person walks in a circle.", []),
        ("A154_", "A person zigzags forward.", []),
        ("A011_", "A person does calf raises.", []),
    ],
    "C": [
        ("A142_", "A person mimes jumping rope.", []),
        ("A143_", "A person mimes kicking a soccer ball.", []),
        ("A115_", "A person does a burpee.", ["K = 8"]),
        ("A1343_", "A person kicks forward, then bows.", ["Sequential"]),
        ("A500_", "A person steps forward while throwing a straight punch.", ["Simultaneous"]),
        ("A577_", "A person walks like a zombie with the arms stretched forward.", ["Simultaneous"]),
        ("A632_", "A person walks forward while throwing a ball up and catching it.", ["Simultaneous"]),
        ("A899_", "A person walks forward, picks something up from the ground, and walks back.", ["Sequential"]),
        ("A269_", "A person jumps over a high bar.", []),
        ("A163_", "A person throws a hook punch.", []),
        ("A061_", "A person walks in a circle.", []),
        ("A017_", "A person twists the torso left and right.", []),
        ("A011_", "A person does calf raises.", []),
    ],
    "D": [
        ("A249_", "A person does a cartwheel.", ["Acrobatic"]),
        ("A252_", "A person does a headstand.", ["Inverted"]),
    ],
}

# Clips mixed into the hero background wall: (experiment, folder prefix).
WALL = [
    ("A", "A631_"), ("B", "A616_"), ("A", "A1416_"), ("C", "A142_"),
    ("A", "A228_"), ("D", "A249_"), ("B", "A138_"), ("A", "A518_"),
    ("C", "A115_"), ("A", "A1273_"), ("B", "A281_"), ("C", "A143_"),
]
WALL_TILE = (384, 240)
WALL_COLS, WALL_ROWS = 4, 3
WALL_SECONDS = 5.0

TEASER_POSTER_AT = 100  # seconds into the overview video


def run(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{res.stderr}")
    return res.stdout


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(path)]).strip())


def find_clip(exp: str, prefix: str) -> Path:
    base = RAW / EXP_DIRS[exp]
    hits = sorted(d for d in base.iterdir() if d.is_dir() and d.name.startswith(prefix))
    if len(hits) != 1:
        sys.exit(f"{exp}/{prefix}: expected one folder, found {[h.name for h in hits]}")
    return hits[0]


def slug_of(folder: Path) -> str:
    code = folder.name.split("_")[0].lower()
    k = folder.name.rsplit("_", 1)[-1]
    return f"{code}-{k}" if k.startswith("k") and k[1:].isdigit() and k != "k5" else code


def crop_filter(exp: str, w: int, h: int) -> str:
    x0, y0, x1, y1 = VIEWPORT[exp]
    return (f"crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f},"
            f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}")


def build_results() -> dict:
    data = {}
    for exp, clips in CLIPS.items():
        out_dir = OUT / "results" / exp
        out_dir.mkdir(parents=True, exist_ok=True)
        items = []
        for prefix, prompt, tags in clips:
            folder = find_clip(exp, prefix)
            src = folder / "animation.mp4"
            slug = slug_of(folder)
            mp4 = out_dir / f"{slug}.mp4"
            jpg = out_dir / f"{slug}.jpg"
            run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c", "copy", "-an",
                 "-movflags", "+faststart", str(mp4)])
            dur = duration(src)
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{dur * 0.42:.2f}", "-i", str(src),
                 "-frames:v", "1", "-vf", crop_filter(exp, 480, 300), "-q:v", "4", str(jpg)])
            poster = out_dir / f"{slug}-poster.jpg"
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{min(1.2, dur / 3):.2f}", "-i", str(src),
                 "-frames:v", "1", "-vf", "scale=960:-2:flags=lanczos", "-q:v", "4", str(poster)])
            items.append({
                "id": f"{exp}-{slug}",
                "prompt": prompt,
                "tags": tags,
                "src": f"static/results/{exp}/{slug}.mp4",
                "thumb": f"static/results/{exp}/{slug}.jpg",
                "poster": f"static/results/{exp}/{slug}-poster.jpg",
                "duration": round(dur, 2),
            })
            print(f"  {exp}/{slug}: {prompt}")
        data[exp] = items
    return data


def build_wall() -> None:
    vids = OUT / "videos"
    vids.mkdir(parents=True, exist_ok=True)
    tw, th = WALL_TILE
    inputs, chains, labels = [], [], []
    for i, (exp, prefix) in enumerate(WALL):
        src = find_clip(exp, prefix) / "animation.mp4"
        inputs += ["-ss", "0.3", "-t", f"{WALL_SECONDS}", "-i", str(src)]
        chains.append(f"[{i}:v]{crop_filter(exp, tw, th)},fps=24,setpts=PTS-STARTPTS[t{i}]")
        labels.append(f"[t{i}]")
    layout = "|".join(f"{(i % WALL_COLS) * tw}_{(i // WALL_COLS) * th}" for i in range(len(WALL)))
    graph = ";".join(chains) + f";{''.join(labels)}xstack=inputs={len(WALL)}:layout={layout}[v]"
    wall = vids / "wall.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[v]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-an", str(wall)])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(wall), "-frames:v", "1", "-q:v", "5",
         str(vids / "wall.jpg")])
    print(f"  wall.mp4 {wall.stat().st_size / 1e6:.1f} MB")


def build_teaser() -> None:
    vids = OUT / "videos"
    src = SRC / "teaser_video.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c", "copy",
         "-movflags", "+faststart", str(vids / "teaser.mp4")])
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(TEASER_POSTER_AT), "-i", str(src),
         "-frames:v", "1", "-vf", "scale=1600:-2:flags=lanczos", "-q:v", "3",
         str(vids / "teaser-poster.jpg")])
    print(f"  teaser.mp4 {(vids / 'teaser.mp4').stat().st_size / 1e6:.1f} MB")


def build_figures() -> dict:
    figs = OUT / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    tmp = figs / "_tmp"
    tmp.mkdir(exist_ok=True)
    sizes = {}
    for pdf in sorted((SRC / "figures").glob("*.pdf")):
        stem = pdf.stem
        run(["pdftoppm", "-r", "260", "-png", "-singlefile", str(pdf), str(tmp / stem)])
        im = Image.open(tmp / f"{stem}.png").convert("RGB")
        max_w = 2600
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(figs / f"{stem}.webp", "WEBP", quality=90, method=6)
        sizes[stem] = [im.width, im.height]
        if stem == "teaser":
            og = im.copy()
            og.thumbnail((1200, 1200), Image.LANCZOS)
            og.save(figs / "og.jpg", "JPEG", quality=88, optimize=True)
        print(f"  {stem}.webp {im.width}x{im.height}")
    shutil.rmtree(tmp)
    return sizes


def main() -> None:
    print("results:")
    data = build_results()
    print("hero wall:")
    build_wall()
    print("overview video:")
    build_teaser()
    print("figures:")
    sizes = build_figures()
    shutil.copyfile(SRC / "Video_Models_Are_Excellent_Motion_Models.pdf", OUT / "paper.pdf")
    js = OUT / "js" / "data.js"
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(
        "// Generated by tools/build_assets.py; edit CLIPS there and re-run.\n"
        f"window.CLIPS = {json.dumps(data, indent=1)};\n"
        f"window.FIGURE_SIZES = {json.dumps(sizes)};\n",
        encoding="utf-8",
    )
    print("done.")


if __name__ == "__main__":
    main()
