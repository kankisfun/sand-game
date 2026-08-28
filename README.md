# sand-game

A small Pygame prototype inspired by color-sand puzzle ads: upload any picture, turn it into a manageable grid of colored sand grains, then send color-matching buckets underneath it while the remaining grains obey simple falling-sand physics.

## Current prototype

- **Upload an image** with the button, or drag and drop an image onto the window.
- The image is downscaled to at most **190 x 120 simulation cells**. Downscaling averages/merges source pixels so a large photo does not become millions of particles.
- Each non-transparent cell becomes one colored sand grain.
- Sand uses a simple cellular automaton: grains try to fall down, then diagonally down-left/down-right.
- The game samples the **bottom 5 sand rows** and offers **three color bucket buttons**.
- Color choices deliberately try to be different: after the first pick, the chooser first looks for colors farther than **2x the current tolerance** from earlier picks, then **1x tolerance**, then falls back to any available color.
- Clicking a color spawns a bucket of that color. A bucket only scoops grains within the current RGB color-distance tolerance.
- Use the **- / + tolerance controls** to make matching stricter or looser.
- Up to **3 buckets** can be active/queued. If the spawn area is occupied, new buckets wait briefly instead of overlapping.
- Buckets travel across a track that extends beyond both sides of the picture, so the first and last image columns get a full pass.
- At the right edge a bucket loops back to the left. If the left spawn area is occupied, it waits at the right edge until it can re-enter safely.
- A bucket disappears when it fills, or after **3 complete loops** without filling.
- **Reset** restores the original sand picture and clears all buckets.

## Run it

Python 3.10+ is recommended.

```bash
python -m venv .venv
```

Activate the environment, then install the dependency:

```bash
pip install -r requirements.txt
python app.py
```

On systems where the Tk file picker is unavailable, drag-and-drop an image file onto the Pygame window instead.

## Useful tuning knobs

Most balancing values are near the top of `app.py`:

- `MAX_GRID_W` / `MAX_GRID_H` — maximum sand simulation resolution.
- `PHYSICS_HZ` — falling-sand update rate.
- `SCOOP_ROWS` — fixed number of bottom rows a bucket can eat (currently 5).
- `BUCKET_SPEED` — bucket movement speed.
- `SCOOP_INTERVAL` — how often buckets attempt to collect matching grains.
- `MAX_BUCKETS` — active/queued bucket limit.
- `DEFAULT_TOLERANCE`, `TOLERANCE_STEP`, `MIN_TOLERANCE`, `MAX_TOLERANCE` — RGB matching controls.
- `BUCKET_GAP` — minimum spacing used by the anti-overlap/queue logic.

Bucket capacity is based on how many grains currently match the chosen color and tolerance, capped so a bucket does not become enormous.

## Next ideas

- Make grains physically pour through a bucket mouth instead of being sampled from the bottom band.
- Quantize nearby source colors into cleaner game-like color groups before the sand simulation starts.
- Add score/completion rules, combos, levels, sounds, bucket shake, and satisfying fill effects.
- Move the simulation to NumPy or a shader if we want much higher particle counts.
