# Video Models are Excellent Motion Models — project page

Live at **https://video-beats-motion.github.io/**

Plain static site (no build step to serve it): `index.html`, `static/css/style.css`,
`static/js/app.js`, and media under `static/`.

## Preview locally

```bash
python -m http.server 8000
# open http://localhost:8000
```

(Opening `index.html` directly from disk also works, but some browsers block video seeking on `file://`.)

## Rebuilding the media

All videos, thumbnails, figures and `static/js/data.js` are generated from the raw research folders
that sit next to this repo (`../paper_motions_final`, `../figures`, `../teaser_video.mp4`, the paper PDF):

```bash
python tools/build_assets.py      # needs ffmpeg, pdftoppm (poppler) and Pillow
```

To add, remove, reorder or re-caption result clips, edit `CLIPS` in `tools/build_assets.py` and re-run.
Result videos are remuxed (not re-encoded), so there is no quality loss.

## Things to update later

- **arXiv / Code buttons**: in `index.html`, replace the two `<span class="btn pending">` elements with
  `<a class="btn" href="...">` links once they are public.
- **BibTeX**: update the entry in the `#cite` section with the venue / arXiv id.
