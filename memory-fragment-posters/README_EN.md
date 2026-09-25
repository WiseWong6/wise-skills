# Memory Fragment Posters · 记忆碎片摄影海报

<p align="center"><a href="README.md">简体中文</a> · <strong>English</strong></p>
<p align="center">
  <a href="https://github.com/WiseWong6/memory-fragment-posters/blob/main/LICENSE"><img src="https://img.shields.io/github/license/WiseWong6/memory-fragment-posters?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/WiseWong6/wise-skills"><img src="https://img.shields.io/badge/More-Wise%20Skills-173F5F?style=for-the-badge" alt="Wise Skills"></a>
</p>

Take a memory from each photograph, place it on warm ivory paper, and assemble the fragments into one complete poster.

This Codex skill combines visual selection by the assistant with deterministic photo compositing. The upper fragment, lower cutout, and final assembly reuse the same photo crop and alpha mask. Original colors, perspective, and lighting are preserved.

By default, it delivers **Puzzle + Ticket** editions. Each contains one poster per photograph and one assembled poster: **9 photographs produce 20 images**.

## Preview

These final examples are published with the author’s permission. Puzzle and Ticket editions are shown side by side; click to view original dimensions. Examples illustrate the design and are not photo inputs for new tasks.

<table>
  <tr><th>Puzzle</th><th>Ticket</th></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/10.png"><img src="assets/examples/puzzle/10.png" alt="Complete assembly · puzzle" width="100%" loading="lazy"></a><br>Complete assembly</td><td width="50%"><a href="assets/examples/ticket/10.png"><img src="assets/examples/ticket/10.png" alt="Complete assembly · ticket" width="100%" loading="lazy"></a><br>Complete assembly</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/01.png"><img src="assets/examples/puzzle/01.png" alt="Mountains and sea · puzzle" width="100%" loading="lazy"></a><br>Mountains and sea</td><td width="50%"><a href="assets/examples/ticket/01.png"><img src="assets/examples/ticket/01.png" alt="Mountains and sea · ticket" width="100%" loading="lazy"></a><br>Mountains and sea</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/02.png"><img src="assets/examples/puzzle/02.png" alt="Golden years · puzzle" width="100%" loading="lazy"></a><br>Golden years</td><td width="50%"><a href="assets/examples/ticket/02.png"><img src="assets/examples/ticket/02.png" alt="Golden years · ticket" width="100%" loading="lazy"></a><br>Golden years</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/03.png"><img src="assets/examples/puzzle/03.png" alt="Sunlit wing · puzzle" width="100%" loading="lazy"></a><br>Sunlit wing</td><td width="50%"><a href="assets/examples/ticket/03.png"><img src="assets/examples/ticket/03.png" alt="Sunlit wing · ticket" width="100%" loading="lazy"></a><br>Sunlit wing</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/04.png"><img src="assets/examples/puzzle/04.png" alt="Nanjing avenue · puzzle" width="100%" loading="lazy"></a><br>Nanjing avenue</td><td width="50%"><a href="assets/examples/ticket/04.png"><img src="assets/examples/ticket/04.png" alt="Nanjing avenue · ticket" width="100%" loading="lazy"></a><br>Nanjing avenue</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/05.png"><img src="assets/examples/puzzle/05.png" alt="Hangzhou airport · puzzle" width="100%" loading="lazy"></a><br>Hangzhou airport</td><td width="50%"><a href="assets/examples/ticket/05.png"><img src="assets/examples/ticket/05.png" alt="Hangzhou airport · ticket" width="100%" loading="lazy"></a><br>Hangzhou airport</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/06.png"><img src="assets/examples/puzzle/06.png" alt="Sea sunset · puzzle" width="100%" loading="lazy"></a><br>Sea sunset</td><td width="50%"><a href="assets/examples/ticket/06.png"><img src="assets/examples/ticket/06.png" alt="Sea sunset · ticket" width="100%" loading="lazy"></a><br>Sea sunset</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/07.png"><img src="assets/examples/puzzle/07.png" alt="Winter branches · puzzle" width="100%" loading="lazy"></a><br>Winter branches</td><td width="50%"><a href="assets/examples/ticket/07.png"><img src="assets/examples/ticket/07.png" alt="Winter branches · ticket" width="100%" loading="lazy"></a><br>Winter branches</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/08.png"><img src="assets/examples/puzzle/08.png" alt="Portrait sign · puzzle" width="100%" loading="lazy"></a><br>Portrait sign</td><td width="50%"><a href="assets/examples/ticket/08.png"><img src="assets/examples/ticket/08.png" alt="Portrait sign · ticket" width="100%" loading="lazy"></a><br>Portrait sign</td></tr>
  <tr><td width="50%"><a href="assets/examples/puzzle/09.png"><img src="assets/examples/puzzle/09.png" alt="Snowy street · puzzle" width="100%" loading="lazy"></a><br>Snowy street</td><td width="50%"><a href="assets/examples/ticket/09.png"><img src="assets/examples/ticket/09.png" alt="Snowy street · ticket" width="100%" loading="lazy"></a><br>Snowy street</td></tr>
</table>

## Core Capabilities

- The assistant selects recognizable details automatically; explicit user choices take priority.
- Original photographs are orientation-corrected and cropped proportionally, without repainting, stretching, outpainting, or added color filters.
- Every poster is exactly 1800×2400 pixels, with two 1200-pixel halves.
- A single crop and mask serve the fragment, its original-position cutout, and the assembly.
- Neighboring pieces share complementary boundaries; the assembly is connected and has no internal holes.
- Existing outputs are preserved. A batch is published only after its checks pass.

## Two Editions

| | Puzzle | Ticket |
|---|---|---|
| Edges | Rounded tabs and complementary sockets | Complementary perforations; outer perforations face inward |
| Base cell | 390×390 pixels | 420×320 pixels |
| Individual poster | Paper and fragment above; photograph and cutout below | Same |
| Final poster | All fragments assembled on ivory paper | Same |

For larger batches, all cells are scaled together **before extraction**, keeping the assembly within 70% of canvas width and 60% of canvas height. Final assembly translates pieces without resizing or rotating them.

The visual direction is warm ivory fiber paper, subtle grain, and generous space. No added text, logos, watermarks, stickers, tape, or heavy shadows. Signs and lettering already present in the photographs remain.

## Installation

Requires Python 3, Pillow, NumPy, and a Codex environment that can read photographs and execute local scripts. Missing dependencies produce an explicit error; nothing is installed automatically.

```bash
git clone https://github.com/WiseWong6/memory-fragment-posters.git \
  ~/.codex/skills/memory-fragment-posters
```

If your environment discovers skills through `~/.agents/skills`, create a shared entry only when the destination does not already exist:

```bash
mkdir -p ~/.agents/skills
ln -s ~/.codex/skills/memory-fragment-posters \
  ~/.agents/skills/memory-fragment-posters
```

Inspect existing installations before making changes. To update:

```bash
git -C ~/.codex/skills/memory-fragment-posters pull --ff-only
```

Also available in [Wise Skills](https://github.com/WiseWong6/wise-skills). The entry sets `allow_implicit_invocation: false`: explicitly invoke or select the skill to use it.

## Quick Start

Attach original photographs in Codex:

```text
Use $memory-fragment-posters on these photos. Create both Puzzle and Ticket editions.
```

Choose one edition:

```text
Use $memory-fragment-posters on these photos. Puzzle edition only.
```

Choose memorable details:

```text
Use $memory-fragment-posters for this collection.
Select the distant snow mountains in the coastal photo and the treetop or branch edge in the tree photo. Choose the remaining details automatically.
```

Selection and production proceed automatically by default. Ask explicitly if you want candidate crops first.

## How Exact Correspondence Works

1. The assistant reads each photo and selects a 3:2 landscape crop and fragment center.
2. The script handles orientation and fits the crop proportionally into the lower half.
3. It plans the entire connected assembly and shared boundaries before extracting pieces.
4. It extracts each photo fragment once, places it above, and fills the same original coordinates with paper.
5. The final assembly translates those same fragments without rotation, resizing, or recropping.
6. Saved pixels are checked, including partially transparent edges. Failed batches are not published.

**The assistant chooses meaningful details; the script has no independent semantic recognition model.** Rendering needs no network, image API, or credentials. The host must permit original-photo processing; this skill does not override host restrictions.

### Manual Execution

From the repository directory:

```bash
python3 scripts/render.py inspect /absolute/path/photo.jpg
python3 scripts/render.py render \
  --config /absolute/path/config.json \
  --output /absolute/path/outputs/memory-fragment-posters
```

See the [input reference](references/input.md) for the configuration: ordered photo paths, orientation-corrected source crop coordinates, normalized fragment centers, and requested styles. Do not commit personal photo paths.

## Output and Acceptance

For nine photographs, the output contains `拼图版/` and `票根版/`, each holding nine numbered photo posters and `10_完整拼接.png`, plus a root `制作检查.json` report.

Every PNG is 1800×2400. Individual posters have equal upper and lower halves; assembled posters use the entire paper canvas. Existing output names advance to `-v2`, `-v3`, and so on.

Checks cover dimensions, crop pixels, original-position cutouts, complementary masks, partial transparency, connectivity, and internal holes. A `complete` report confirms the programmatic checks; aesthetic crop preference remains the user's judgment.

Run regression checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_render.py
```

Tests cover 1, 2, 5, and 10-photo layouts, portrait orientation, EXIF rotation, edge subjects, Unicode filenames, missing files, repeated output paths, and failed-batch isolation. Temporary test material is removed afterward.

## Known Boundaries

- Portrait images require landscape cropping; the full original environment may not fit.
- Near an image edge, the source box shifts inward as a whole. Actual coordinates are recorded.
- Animated and multi-frame files are rejected, including some MPO files with JPG extensions. Supply a definite static primary image first.
- Arbitrary canvas ratios and independent piece resizing are unsupported.
- No repainting, outpainting, content reconstruction, or third-party image generation. The repository includes only author-authorized final examples, with no original source photos, private paths, or task records.

## About

Find me as **@歪斯Wise**, sharing AI creation, agent workflows, visual design, and productivity tools.

[X / Twitter](https://x.com/killthewhys) · [Xiaohongshu](https://www.xiaohongshu.com/user/profile/61f3ea4f000000001000db73) · [Wise Skills](https://github.com/WiseWong6/wise-skills)

<p><img src="assets/social/xiaohongshu-qr.jpg" width="180" alt="Wise’s Xiaohongshu card"></p>

## License

[MIT](LICENSE) © 2026 Wise Wong. The license covers skill code and documentation; example artwork and user-supplied photographs remain the property of their respective rights holders and are not sublicensed under MIT.
