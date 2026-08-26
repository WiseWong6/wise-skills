# E01 Tokyo Tower validation case

Use this case only for static prompt assembly and output-contract checks. Do not treat its content as a universal composition template.

| ID | Asset | Role | Status |
| --- | --- | --- | --- |
| E01-SOURCE | `assets/examples/E01-SOURCE-tokyo-tower.jpg` | original source image | input only; 2927×4390 |
| E01-FULL-S08 | `assets/examples/E01-FULL-S08-material-tectonics.webp` | Full Design with S08 | accepted; 1086×1448 |
| E01-SPLIT-S08 | `assets/examples/E01-SPLIT-S08-material-tectonics.webp` | Split 1:1 with S08 | accepted; 1086×1448 |

The accepted case confirms these reusable rules:

- Generate each final image in one call from E01-SOURCE.
- Keep exactly one S08 effect program in each assembled prompt.
- Make the full output entirely designed with zero photographic region.
- Make the split output one 3:4 canvas with the photograph above and complete design translation below.
- Do not use either accepted output as the next generation's input.

`../../blue-poster/assets/style-references/secondary/R-S08-B-material-tectonics-aesthetic-only-2x3.webp` is a useful aesthetic direction but is not a delivery reference because it is 1024×1536.
