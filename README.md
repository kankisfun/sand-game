# sand-game

A small Pygame prototype inspired by those color-sand puzzle ads: upload any picture, turn it into a manageable grid of colored sand grains, then send a bucket underneath it to scoop away the bottom of the image while the remaining grains obey simple falling-sand physics.

## Current prototype

- **Upload an image** with the button, or drag and drop an image onto the window.
- The image is downscaled to at most **190 x 120 simulation cells**. Downscaling averages/merges source pixels so a large photo does not become millions of particles.
- Each non-transparent cell becomes one colored sand grain.
- Sand uses a simple cellular automaton: grains try to fall down, then diagonally down-left/down-right.
- **Place bucket** enters placement mode. Click the track below the image to spawn it.
- The bucket moves from left to right, slowly scooping grains from a randomized **5-15 row** band at the bottom of the picture.
- Bucket capacity scales with the uploaded picture, and the bucket stops when full or when it reaches the right edge.
- **Reset** restores the original sand picture for another run.

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
- `Bucket.speed` — left-to-right movement speed.
- `random.randint(5, 15)` in `place_bucket()` — scoop depth range.
- Capacity currently targets roughly 12% of the source grain count, clamped to a reasonable range.

## Next ideas

- Quantize nearby colors so the image looks more like grouped colored sand.
- Add a real bucket mouth/opening so grains physically fall into it instead of being sampled from the bottom band.
- Add multiple buckets, upgrades, levels, scoring, and completion conditions.
- Move the simulation to NumPy or a shader if we want much higher particle counts.
- Add sound, grain trails, bucket shake, and satisfying fill effects.
