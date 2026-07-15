# AxiDraw plot workflow — the full ritual

Reconstructed 2026-07 from send_to_pi.sh, git history, and the NextDraw CLI
docs (https://bantam.tools/nd_cli/). The send script was only ever the last
step; this documents everything that used to live in Geoff's head.

Hardware: **AxiDraw V3/A3** (11×17 travel), driven from a Raspberry Pi
(`plotterpi.local`, user `xbno`) so no laptop stays USB-tethered for hours.
NextDraw CLI lives in `~/plotterpi/venv` on the pi; SVGs land in
`~/plotterpi/svg/`.

Standard flags every hardware command needs: `-q 3 -L 2`
(`-q 3` = brushless pen-lift servo, `-L 2` = V3/A3 model → 11×17 travel
limits; paths clip to SVG doc edge or travel, whichever is smaller).

---

## 1. Prep the SVG

- gen2 output needs **no Inkscape layer surgery**: layers are already named
  `1 - black03 0.3` etc. (leading digit = what layers-mode selects on).
- Hand-made or gen1-era SVGs: in Inkscape, put each pen's paths on its own
  layer, name layers starting with a digit (`1 - black`, `2 - blue`), and
  **delete** anything that must not plot (backgrounds, guides, raster refs).
- gen1-era caveat: px-sized SVGs get interpreted at 96 dpi. gen2 SVGs are true
  mm — what Inkscape shows is what plots.

## 2. Time estimate — no hardware needed

```
nextdraw file.svg -v -T -L 2
```
`-v` (`--preview`) simulates offline (no USB needed, runs anywhere —
laptop or pi), `-T` (`--report_time`) prints estimated time + pen-down/up
travel distance. Do this per layer for multi-pen plots (`-m layers -l N -v -T`).

## 3. Physical setup (the part muscle memory forgot)

1. **Free the carriage**: `nextdraw -m align -L 2` — raises pen, disables
   motors so you can slide the carriage by hand.
2. Slide carriage to the **home corner** (top-left). AxiDraw has no limit
   switches: wherever the carriage sits when the plot starts IS the origin.
3. Align paper to the machine, square it, tape all four corners.
4. **Pen height**: clamp pen so the tip sits a few mm above paper while up.
   Test with `nextdraw -m cycle -d 30 -u 70 -q 3 -L 2` (lowers 0.5s, raises).
   Adjust clamp/percentages until pen-down draws and pen-up clears reliably.
   `-d` / `-u` are down/up heights as % of servo travel — if you settle on
   custom values, they must ALSO be passed to the plot command itself.
5. Ink test: `reset_pi.sh lower_pen` / `raise_pen`, scribble check on scrap
   in a margin, or just trust the first strokes.

## 4. Plot

```
./plotterpi/send_to_pi.sh path/to/file.svg
```
= scp to pi + `nextdraw <file> -q 3 -L 2 -Y` over ssh (`-Y` randomizes start
points of closed paths so pen-down blobs don't align).

**Long plots, laptop-free**: the ssh session must survive laptop sleep — run
it in tmux on the pi (`ssh xbno@plotterpi.local`, `tmux`, run nextdraw there,
detach) rather than through the synchronous send script, or the plot dies
with the connection.

### Multi-pen

```
nextdraw file.svg -m layers -l 1 -q 3 -L 2 -Y    # pen 1
# swap pens WITHOUT nudging the carriage or paper
nextdraw file.svg -m layers -l 2 -q 3 -L 2 -Y    # pen 2
```
Registration depends entirely on carriage/paper not moving between passes.

### Pause / resume

- Pause: physical button on the machine, or Ctrl-C.
- Resumable plots need progress saved: plot with `-o progress.svg`, then
  `nextdraw progress.svg -m res_plot` to continue,
  or `-m res_home` to return home first. `-m utility -M res_read` inspects
  saved state.

## 5. After

- `./plotterpi/reset_pi.sh walk_home` — return carriage to origin.
- Nudge utilities when needed: `walk_x <in>`, `walk_y <in>`, `raise_pen`,
  `lower_pen` (walk args in inches; CLI also has `walk_mmx/walk_mmy`).
- Let ink dry before untaping. Pen caps on.

## Inkscape route (testing without the pi — works UNPLUGGED)

Install the plotter extension in Inkscape on the laptop
(Bantam "NextDraw software for Inkscape" via
https://support.bantamtools.com → Software Installation; it's the renamed
fork of the classic **AxiDraw Control** extension, same dialog. Legacy
AxiDraw version: https://axidraw.com/legacy_sw.html).

Dialog: **Extensions > AxiDraw > AxiDraw Control** (Bantam build:
Extensions > Bantam Tools submenu). Six tabs — each tab is an action you
fire by clicking **Apply**:

- **Plot** — plots the document. With preview enabled (below), Apply
  simulates instead: no hardware needed.
- **Setup** — "Pen height: UP (%)" / "Pen height: DOWN (%)" sliders plus
  actions: "Cycle pen down then up", "Raise pen, turn off motors" (= align,
  for hand-homing the carriage), "Toggle pen between up, down".
- **Options** — speed, and under its notification/preview section:
  **"Preview mode rendering"** (All movement / Pen-down / Pen-up / None)
  and **"Report time elapsed"**. Turn both on → Apply on Plot tab gives an
  offline dry-run: overlays the travel paths on the canvas as a new layer
  and reports the time estimate. This is the "test it in Inkscape" step.
- **Manual** — walk carriage X/Y, walk home, raise/lower pen,
  enable/disable motors, "Strip plotter data" (removes saved progress/
  preview layers from the SVG).
- **Layers** — "Plot only layers beginning with" N → one pen at a time.
- **Resume** — "Resume (From Home or where paused)" / "Return to Home
  Corner (only)"; progress is stored inside the SVG itself.

Model matters even for preview time: set the machine model to AxiDraw V3/A3
in the extension's config so speeds/travel match.

## Pi maintenance

- `ssh xbno@plotterpi.local`; venv at `~/plotterpi/venv`.
- Fresh SD card: reinstall NextDraw CLI per bantam link, `mkdir ~/plotterpi/svg`.
