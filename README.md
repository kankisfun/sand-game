# sand-game

A small Pygame prototype inspired by color-sand puzzle ads: upload any picture, turn it into a manageable grid of colored sand grains, then send color-matching buckets underneath it while the remaining grains obey simple falling-sand physics.

## Current prototype

- **Upload an image** with the button, or drag and drop an image onto the window.
- The image is downscaled to at most **190 x 120 simulation cells** so large photos do not become millions of particles.
- Each non-transparent cell becomes one colored sand grain.
- Sand uses a simple cellular automaton: grains try to fall down, then diagonally down-left/down-right.
- The game samples the **bottom 5 sand rows** and offers **three color bucket buttons**.
- Color choices try to stay distinct: after the first pick, the chooser looks for colors farther than **2x tolerance**, then **1x tolerance**, then falls back to any available color.
- Base RGB matching tolerance is **50**. Tolerance is no longer manually adjustable; it is upgraded in the shop.
- Base bucket capacity is **100 grains**. When fewer matching grains than the current capacity remain anywhere on the board, a newly spawned bucket has its capacity reduced to that remaining matching count so it can still finish.
- Base maximum bucket count is **2**. New buckets queue briefly if the spawn area is occupied.
- Buckets travel across a track that extends beyond both sides of the picture and loop from right back to left.
- A bucket disappears when it fills, or after **3 complete loops** without filling.
- **Reset** restores the original sand picture and clears active buckets, while session gold and upgrades remain.

## Gold and shop

Every sand grain collected gives **1 gold**. The shop is in the bottom-right corner and upgrades persist for the current game session.

| Upgrade | Effect | First cost |
| --- | --- | ---: |
| Tolerance | +10 RGB tolerance | 20 gold |
| Speed | +10% bucket speed | 20 gold |
| Buckets | +1 maximum bucket | 200 gold |
| Capacity | +100 bucket capacity | 20 gold |

Each upgrade doubles in price after every purchase. Normal upgrade prices therefore go **20, 40, 80, 160...** and bucket-slot prices go **200, 400, 800, 1600...**.

Maximum bucket count is capped at **8**.

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
- `SCOOP_ROWS` — fixed number of bottom rows a bucket can eat.
- `BASE_BUCKET_SPEED` — starting bucket movement speed.
- `BASE_BUCKET_CAPACITY` — starting bucket capacity.
- `BASE_MAX_BUCKETS` / `MAX_BUCKET_LIMIT` — starting and maximum upgraded bucket limits.
- `DEFAULT_TOLERANCE` — starting RGB matching tolerance.
- `SCOOP_INTERVAL` — how often buckets attempt to collect matching grains.
- `BUCKET_GAP` — minimum spacing used by the anti-overlap/queue logic.
- `SHOP_BASE_PRICE` / `EXTRA_BUCKET_PRICE_MULTIPLIER` — shop economy values.

## Next ideas

- Make grains physically pour through a bucket mouth instead of being sampled from the bottom band.
- Quantize nearby source colors into cleaner game-like color groups before the sand simulation starts.
- Add completion rules, combos, levels, sounds, bucket shake, and satisfying fill effects.
- Save gold/upgrades between launches.
- Move the simulation to NumPy or a shader if we want much higher particle counts.
