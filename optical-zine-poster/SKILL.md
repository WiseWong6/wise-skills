---
name: optical-zine-poster
description: Turn one source image into a finished 3:4 Minimal Optical Zine poster with semantic style selection, a default full-design composition, an optional upper-photo/lower-design 1:1 split, and an 11-style local reference catalog. Use when Codex should create an optical zine poster, Layer Study poster, cyanotype or moire architectural print, compare optical print styles, or generate a full-design or split 1:1 variant from a supplied image.
---

# Optical Zine Poster

Generate each final poster from the original source image in one image-generation call. Default to a complete full-design poster. Never create a base image and then add effects in a second content-generation stage.

## Required tool policy

- Use only the Codex host built-in `image_gen.imagegen` tool.
- Never invoke, install, or fall back to a third-party image skill, Ark, Doubao, Gemini, a local model, CLI, or API workflow.
- If the built-in tool is unavailable or fails, stop and report the blocking reason.
- Treat style reference images as browse-only. Never pass them to image generation.

## Generate the default full poster

1. Require one source image. If it is a local file, inspect it with `view_image` before generation.
2. If the user names `S01`–`S11`, honor it. Otherwise read [style-selection.md](references/style-selection.md), analyze the source semantics, and select exactly one style.
3. Read [prompt-full-design.md](references/prompt-full-design.md) and the selected block in [style-programs.md](references/style-programs.md).
4. Replace `{{EFFECT_PROGRAM}}` with exactly one complete style block. Do not leave placeholders or merge multiple styles.
5. Call built-in `image_gen.imagegen` once with the original source as the only image input. State that the source is a semantic and structural source, not a style reference.
6. Save the selected image under the caller's current workspace at `outputs/optical-zine-poster/<source>-full-Sxx-vN.png`, unless the user supplied another destination. Never overwrite an existing file.
7. Save the exact final prompt beside it as `<source>-full-Sxx-vN.prompt.md`.
8. Run `python3 scripts/validate_output.py <image> --mode full`. If it fails, retry once from the original source with the same style and a stronger native 3:4 instruction. Never stretch or crop to hide a ratio failure. If the retry fails, report it as unaccepted.
9. Perform only a lightweight check on the returned image: the subject remains recognizable, the whole page is designed, and no photographic window remains. Do not start a browser or create extra screenshots.
10. Report the selected style ID and name, one concrete selection reason, image path, prompt path, validation result, and catalog path.

After delivery, ask whether the user wants:

- the same style as an upper-photo/lower-design 1:1 split; and
- to browse or try another style from `references/style-catalog.html`.

## Generate a split 1:1 variant

1. Reuse the original source image, not the previously generated full poster.
2. Reuse the selected style unless the user requests another `Sxx`.
3. Read [prompt-split-1x1.md](references/prompt-split-1x1.md), insert exactly one style block, and make one fresh built-in image generation call.
4. Save as `<source>-split-Sxx-vN.png` with a matching `.prompt.md` sidecar.
5. Run `python3 scripts/validate_output.py <image> --mode split`. Check that the only horizontal boundary is visually at the midpoint; do not claim pixel-level boundary verification from dimensions alone.

## Generate an alternate style

- Default an alternate `Sxx` choice to full-design mode.
- Generate a split alternate only when the user explicitly requests it.
- Return to the original source for every alternate; never chain generated posters as new inputs.

## Browse styles

- Direct the user to the absolute path of [style-catalog.html](references/style-catalog.html).
- Use [style-selection.md](references/style-selection.md) for semantic guidance and [style-programs.md](references/style-programs.md) only after a style is chosen.
- Keep `R-S08-B` labeled aesthetic-only: it is 2:3 and is not a valid delivery reference.

## Output acceptance

- Require an exact 3:4 pixel ratio.
- Require one recognizable subject and coherent environment.
- Reject empty cards, unrelated collage fragments, regular UI grids, mockups, logos, watermarks, and meaningless text.
- For full mode, reject every photographic-looking area or split composition.
- For split mode, require one midpoint boundary, faithful photography above, and complete design translation below.
