from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

WINDOW_WIDTH = 1240
WINDOW_HEIGHT = 920
FPS = 60
PHYSICS_HZ = 30

BACKGROUND = (21, 24, 31)
PANEL = (33, 37, 47)
PANEL_LIGHT = (46, 51, 63)
TEXT = (237, 240, 246)
MUTED = (161, 169, 184)
ACCENT = (83, 152, 255)
TRACK = (107, 114, 128)
BUCKET_RIM = (210, 216, 228)

CANVAS_RECT = pygame.Rect(120, 105, 1000, 555)
TRACK_RECT = pygame.Rect(10, 680, 1220, 78)

# The source image is merged into at most this many simulation cells.
MAX_GRID_W = 190
MAX_GRID_H = 120
MIN_CELL_SIZE = 3
MAX_CELL_SIZE = 6

SCOOP_ROWS = 5
MAX_BUCKETS = 3
BUCKET_SPEED = 66.0
BUCKET_GAP = 14
SCOOP_INTERVAL = 0.040

DEFAULT_TOLERANCE = 40
TOLERANCE_STEP = 10
MIN_TOLERANCE = 0
MAX_TOLERANCE = 180

Color = tuple[int, int, int]


def color_distance_sq(a: Color, b: Color) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def color_matches(a: Color, b: Color, tolerance: int) -> bool:
    return color_distance_sq(a, b) <= tolerance * tolerance


def shade(color: Color, factor: float) -> Color:
    return tuple(max(0, min(255, round(channel * factor))) for channel in color)


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    enabled: bool = True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.enabled:
            fill = (54, 58, 68)
            color = (112, 119, 132)
        else:
            fill = PANEL_LIGHT
            color = TEXT

        pygame.draw.rect(surface, fill, self.rect, border_radius=10)
        if self.enabled:
            pygame.draw.rect(surface, (66, 73, 88), self.rect, 1, border_radius=10)
        label = font.render(self.label, True, color)
        surface.blit(label, label.get_rect(center=self.rect.center))

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(pos)


@dataclass
class ColorBucketButton:
    center: tuple[int, int]
    radius: int
    color: Optional[Color] = None
    enabled: bool = False

    def hit(self, pos: tuple[int, int]) -> bool:
        if not self.enabled or self.color is None:
            return False
        dx = pos[0] - self.center[0]
        dy = pos[1] - self.center[1]
        return dx * dx + dy * dy <= self.radius * self.radius

    def draw(self, surface: pygame.Surface) -> None:
        cx, cy = self.center
        outer = (69, 75, 89) if self.enabled else (48, 52, 61)
        pygame.draw.circle(surface, outer, self.center, self.radius)

        if self.color is None:
            pygame.draw.circle(surface, (71, 76, 87), self.center, self.radius - 7)
            pygame.draw.line(surface, MUTED, (cx - 12, cy), (cx + 12, cy), 3)
            return

        fill = self.color if self.enabled else shade(self.color, 0.45)
        pygame.draw.circle(surface, fill, self.center, self.radius - 7)
        pygame.draw.circle(surface, BUCKET_RIM, self.center, self.radius - 7, 2)

        # Tiny bucket cues inside the color circle: rim and handle.
        pygame.draw.line(surface, BUCKET_RIM, (cx - 15, cy - 9), (cx + 15, cy - 9), 4)
        handle_rect = pygame.Rect(cx - 15, cy - 25, 30, 25)
        pygame.draw.arc(surface, BUCKET_RIM, handle_rect, math.pi, 2 * math.pi, 3)


@dataclass
class Bucket:
    x: float
    y: int
    width: int
    height: int
    capacity: int
    target_color: Color
    speed: float = BUCKET_SPEED
    fill: int = 0
    loops: int = 0
    waiting_for_wrap: bool = False

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x), self.y, self.width, self.height)

    @property
    def full(self) -> bool:
        return self.fill >= self.capacity

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        rect = self.rect
        body_color = shade(self.target_color, 0.70)
        rim_color = shade(self.target_color, 1.18)

        rim = pygame.Rect(rect.x - 5, rect.y, rect.width + 10, 10)
        pygame.draw.rect(surface, rim_color, rim, border_radius=5)
        pygame.draw.rect(surface, body_color, rect, border_radius=8)
        pygame.draw.rect(surface, (42, 47, 57), rect, 2, border_radius=8)

        inner = rect.inflate(-12, -16)
        inner.y += 5
        pygame.draw.rect(surface, (34, 38, 47), inner, border_radius=5)
        if self.capacity > 0 and self.fill > 0:
            ratio = min(1.0, self.fill / self.capacity)
            fill_h = max(2, int(inner.height * ratio))
            fill_rect = pygame.Rect(inner.x, inner.bottom - fill_h, inner.width, fill_h)
            pygame.draw.rect(surface, self.target_color, fill_rect, border_radius=4)

        loop_label = font.render(f"{self.loops}/3", True, TEXT)
        surface.blit(loop_label, loop_label.get_rect(center=(rect.centerx, rect.centery + 1)))


class SandPicture:
    def __init__(self) -> None:
        self.grid: list[list[Optional[Color]]] = []
        self.original_grid: list[list[Optional[Color]]] = []
        self.grid_w = 0
        self.grid_h = 0
        self.cell_size = 4
        self.pixel_rect = pygame.Rect(0, 0, 0, 0)
        self.source_name = ""
        self.initial_particles = 0
        self.physics_active = False

    @property
    def loaded(self) -> bool:
        return bool(self.grid)

    @property
    def particle_count(self) -> int:
        return sum(cell is not None for row in self.grid for cell in row)

    def _fit_grid(self, width: int, height: int) -> tuple[int, int]:
        ratio = min(MAX_GRID_W / width, MAX_GRID_H / height, 1.0)
        return max(1, round(width * ratio)), max(1, round(height * ratio))

    def load(self, path: str) -> None:
        image = pygame.image.load(path).convert_alpha()
        width, height = image.get_size()
        grid_w, grid_h = self._fit_grid(width, height)

        # smoothscale averages source pixels when shrinking. That gives us a simple
        # pixel-merging pass and keeps the number of simulated grains bounded.
        merged = pygame.transform.smoothscale(image, (grid_w, grid_h))

        available_w = CANVAS_RECT.width - 60
        available_h = CANVAS_RECT.height - 60
        cell_size = min(available_w // grid_w, available_h // grid_h, MAX_CELL_SIZE)
        self.cell_size = max(MIN_CELL_SIZE, cell_size)

        draw_w = grid_w * self.cell_size
        draw_h = grid_h * self.cell_size
        self.pixel_rect = pygame.Rect(
            CANVAS_RECT.centerx - draw_w // 2,
            CANVAS_RECT.centery - draw_h // 2,
            draw_w,
            draw_h,
        )

        grid: list[list[Optional[Color]]] = []
        for y in range(grid_h):
            row: list[Optional[Color]] = []
            for x in range(grid_w):
                r, g, b, a = merged.get_at((x, y))
                row.append((r, g, b) if a >= 32 else None)
            grid.append(row)

        self.grid = grid
        self.original_grid = [row[:] for row in grid]
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.source_name = Path(path).name
        self.initial_particles = self.particle_count
        self.physics_active = False

    def reset(self) -> None:
        if self.original_grid:
            self.grid = [row[:] for row in self.original_grid]
            self.physics_active = False

    def step(self) -> None:
        if not self.loaded or not self.physics_active:
            return

        # Bottom-up falling-sand cellular automaton. Each grain tries down first,
        # then one of the two diagonals. Random scan/direction avoids a strong bias.
        for y in range(self.grid_h - 2, -1, -1):
            xs = range(self.grid_w) if random.random() < 0.5 else range(self.grid_w - 1, -1, -1)
            for x in xs:
                color = self.grid[y][x]
                if color is None:
                    continue

                if self.grid[y + 1][x] is None:
                    self.grid[y + 1][x] = color
                    self.grid[y][x] = None
                    continue

                directions = [-1, 1]
                random.shuffle(directions)
                for dx in directions:
                    nx = x + dx
                    if 0 <= nx < self.grid_w and self.grid[y + 1][nx] is None:
                        self.grid[y + 1][nx] = color
                        self.grid[y][x] = None
                        break

    def bottom_band_colors(self, rows: int = SCOOP_ROWS) -> list[Color]:
        if not self.loaded:
            return []
        y0 = max(0, self.grid_h - rows)
        return [
            color
            for row in self.grid[y0:]
            for color in row
            if color is not None
        ]

    def matching_count(self, target: Color, tolerance: int) -> int:
        return sum(
            1
            for row in self.grid
            for color in row
            if color is not None and color_matches(color, target, tolerance)
        )

    def scoop(self, bucket: Bucket, tolerance: int, max_grains: int = 5) -> int:
        if not self.loaded or bucket.full:
            return 0

        # Map the bucket mouth from screen pixels to sand-grid columns.
        bx0 = max(bucket.rect.left, self.pixel_rect.left)
        bx1 = min(bucket.rect.right, self.pixel_rect.right)
        if bx0 >= bx1:
            return 0

        x0 = max(0, (bx0 - self.pixel_rect.left) // self.cell_size)
        x1 = min(self.grid_w - 1, (bx1 - 1 - self.pixel_rect.left) // self.cell_size)
        y0 = max(0, self.grid_h - SCOOP_ROWS)

        candidates: list[tuple[int, int]] = []
        for y in range(self.grid_h - 1, y0 - 1, -1):
            for x in range(x0, x1 + 1):
                color = self.grid[y][x]
                if color is not None and color_matches(color, bucket.target_color, tolerance):
                    candidates.append((x, y))

        random.shuffle(candidates)
        room = bucket.capacity - bucket.fill
        amount = min(max_grains, room, len(candidates))
        for x, y in candidates[:amount]:
            self.grid[y][x] = None

        bucket.fill += amount
        return amount

    def draw(self, surface: pygame.Surface) -> None:
        if not self.loaded:
            return
        cell = self.cell_size
        left = self.pixel_rect.left
        top = self.pixel_rect.top
        for y, row in enumerate(self.grid):
            py = top + y * cell
            for x, color in enumerate(row):
                if color is not None:
                    pygame.draw.rect(surface, color, (left + x * cell, py, cell, cell))


class SandGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Sand Picture Prototype")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 20)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.tiny_font = pygame.font.SysFont("arial", 13, bold=True)
        self.title_font = pygame.font.SysFont("arial", 30, bold=True)

        self.picture = SandPicture()
        self.buckets: list[Bucket] = []
        self.pending_colors: list[Color] = []
        self.choice_colors: list[Optional[Color]] = [None, None, None]
        self.tolerance = DEFAULT_TOLERANCE
        self.status = "Upload or drag-and-drop an image to begin."
        self.physics_accum = 0.0
        self.scoop_accum = 0.0
        self.queue_timer = 0.0

        self.upload_button = Button(pygame.Rect(50, 28, 170, 50), "Upload image")
        self.reset_button = Button(pygame.Rect(235, 28, 120, 50), "Reset", enabled=False)
        self.tolerance_minus = Button(pygame.Rect(815, 818, 54, 46), "-")
        self.tolerance_plus = Button(pygame.Rect(1015, 818, 54, 46), "+")
        self.color_buttons = [
            ColorBucketButton((420, 841), 38),
            ColorBucketButton((535, 841), 38),
            ColorBucketButton((650, 841), 38),
        ]

    def choose_file(self) -> Optional[str]:
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Choose an image",
                filetypes=[
                    ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
            return path or None
        except Exception:
            self.status = "File picker unavailable. Drag an image file onto the window instead."
            return None

    def load_image(self, path: str) -> None:
        try:
            self.picture.load(path)
            self.buckets.clear()
            self.pending_colors.clear()
            self.reset_button.enabled = True
            self.refresh_color_choices()
            self.status = (
                f"{self.picture.source_name}: {self.picture.grid_w}x{self.picture.grid_h} sand cells. "
                "Choose a color bucket."
            )
        except Exception as exc:
            self.status = f"Could not load image: {exc}"

    def reset(self) -> None:
        self.picture.reset()
        self.buckets.clear()
        self.pending_colors.clear()
        self.queue_timer = 0.0
        self.refresh_color_choices()
        if self.picture.loaded:
            self.status = "Picture reset. Choose a color bucket."

    def choose_diverse_colors(self, colors: list[Color], count: int = 3) -> list[Color]:
        if not colors:
            return []

        available = colors[:]
        picks: list[Color] = []
        for _ in range(count):
            if not available:
                available = colors[:]

            candidates = available
            if picks:
                for multiplier in (2, 1):
                    threshold_sq = (self.tolerance * multiplier) ** 2
                    separated = [
                        color
                        for color in available
                        if all(color_distance_sq(color, picked) > threshold_sq for picked in picks)
                    ]
                    if separated:
                        candidates = separated
                        break
                else:
                    different = [color for color in available if color not in picks]
                    if different:
                        candidates = different

            choice = random.choice(candidates)
            picks.append(choice)
            available = [color for color in available if color != choice]

        return picks

    def refresh_color_choices(self) -> None:
        colors = self.picture.bottom_band_colors(SCOOP_ROWS)
        picks = self.choose_diverse_colors(colors, 3)
        self.choice_colors = picks + [None] * (3 - len(picks))
        self.update_choice_button_states()

    def update_choice_button_states(self) -> None:
        slots_used = len(self.buckets) + len(self.pending_colors)
        can_add = self.picture.loaded and slots_used < MAX_BUCKETS
        for button, color in zip(self.color_buttons, self.choice_colors):
            button.color = color
            button.enabled = can_add and color is not None

    def bucket_size(self) -> tuple[int, int]:
        picture = self.picture.pixel_rect
        return max(86, min(116, picture.width // 7)), 48

    def make_bucket(self, color: Color) -> Bucket:
        bucket_w, bucket_h = self.bucket_size()
        matches = self.picture.matching_count(color, self.tolerance)
        if matches < 8:
            capacity = max(1, matches)
        else:
            capacity = min(220, max(8, int(matches * 0.35)))

        return Bucket(
            x=float(TRACK_RECT.left),
            y=TRACK_RECT.centery - bucket_h // 2,
            width=bucket_w,
            height=bucket_h,
            capacity=capacity,
            target_color=color,
        )

    def spawn_area_clear(self, width: int, height: int, ignore: Optional[Bucket] = None) -> bool:
        spawn = pygame.Rect(
            TRACK_RECT.left,
            TRACK_RECT.centery - height // 2,
            width + BUCKET_GAP,
            height,
        )
        for bucket in self.buckets:
            if bucket is ignore:
                continue
            if spawn.colliderect(bucket.rect.inflate(BUCKET_GAP, 0)):
                return False
        return True

    def request_bucket(self, color: Color) -> None:
        if len(self.buckets) + len(self.pending_colors) >= MAX_BUCKETS:
            self.status = "Three buckets are already active or queued."
            return

        bucket = self.make_bucket(color)
        if self.spawn_area_clear(bucket.width, bucket.height):
            self.buckets.append(bucket)
            self.picture.physics_active = True
            self.status = "Bucket spawned. It only eats colors inside the tolerance."
        else:
            self.pending_colors.append(color)
            self.queue_timer = 0.0
            self.status = "Spawn is busy - bucket added to the short queue."

        self.refresh_color_choices()

    def process_spawn_queue(self, dt: float) -> None:
        if not self.pending_colors or len(self.buckets) >= MAX_BUCKETS:
            return

        self.queue_timer += dt
        if self.queue_timer < 0.22:
            return

        bucket = self.make_bucket(self.pending_colors[0])
        if not self.spawn_area_clear(bucket.width, bucket.height):
            return

        self.pending_colors.pop(0)
        self.buckets.append(bucket)
        self.picture.physics_active = True
        self.queue_timer = 0.0
        self.status = "Queued bucket entered the track."
        self.update_choice_button_states()

    def bucket_can_move_to(self, bucket: Bucket, new_x: float) -> bool:
        proposed = pygame.Rect(round(new_x), bucket.y, bucket.width, bucket.height)
        for other in self.buckets:
            if other is bucket:
                continue
            if proposed.colliderect(other.rect.inflate(BUCKET_GAP, 0)):
                return False
        return True

    def update_bucket_motion(self, bucket: Bucket, dt: float) -> bool:
        """Move one bucket. Return False when it should disappear."""
        right_x = TRACK_RECT.right - bucket.width

        if bucket.waiting_for_wrap:
            if self.spawn_area_clear(bucket.width, bucket.height, ignore=bucket):
                bucket.x = float(TRACK_RECT.left)
                bucket.waiting_for_wrap = False
            return True

        new_x = bucket.x + bucket.speed * dt
        if new_x >= right_x:
            bucket.x = float(right_x)
            bucket.loops += 1
            if bucket.loops >= 3:
                return False

            if self.spawn_area_clear(bucket.width, bucket.height, ignore=bucket):
                bucket.x = float(TRACK_RECT.left)
            else:
                bucket.waiting_for_wrap = True
            return True

        if self.bucket_can_move_to(bucket, new_x):
            bucket.x = new_x
        return True

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.DROPFILE:
            self.load_image(event.file)
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return True

        pos = event.pos
        if self.upload_button.hit(pos):
            path = self.choose_file()
            if path:
                self.load_image(path)
        elif self.reset_button.hit(pos):
            self.reset()
        elif self.tolerance_minus.hit(pos):
            self.tolerance = max(MIN_TOLERANCE, self.tolerance - TOLERANCE_STEP)
            self.refresh_color_choices()
            self.status = f"Color tolerance: {self.tolerance}"
        elif self.tolerance_plus.hit(pos):
            self.tolerance = min(MAX_TOLERANCE, self.tolerance + TOLERANCE_STEP)
            self.refresh_color_choices()
            self.status = f"Color tolerance: {self.tolerance}"
        else:
            for button in self.color_buttons:
                if button.hit(pos) and button.color is not None:
                    self.request_bucket(button.color)
                    break
        return True

    def update(self, dt: float) -> None:
        self.process_spawn_queue(dt)

        expired = 0
        survivors: list[Bucket] = []
        for bucket in self.buckets:
            if self.update_bucket_motion(bucket, dt):
                survivors.append(bucket)
            else:
                expired += 1
        if expired:
            self.status = f"{expired} bucket{'s' if expired != 1 else ''} expired after 3 loops."
        self.buckets = survivors

        self.scoop_accum += dt
        while self.scoop_accum >= SCOOP_INTERVAL:
            self.scoop_accum -= SCOOP_INTERVAL
            for bucket in self.buckets:
                self.picture.scoop(bucket, self.tolerance, max_grains=5)

        full_count = sum(bucket.full for bucket in self.buckets)
        if full_count:
            self.buckets = [bucket for bucket in self.buckets if not bucket.full]
            self.status = f"{full_count} bucket{'s' if full_count != 1 else ''} filled!"
            self.refresh_color_choices()
        else:
            self.update_choice_button_states()

        self.physics_accum += dt
        step_dt = 1.0 / PHYSICS_HZ
        while self.physics_accum >= step_dt:
            self.physics_accum -= step_dt
            self.picture.step()

    def draw_empty_canvas(self) -> None:
        pygame.draw.rect(self.screen, PANEL, CANVAS_RECT, border_radius=18)
        pygame.draw.rect(self.screen, (57, 63, 75), CANVAS_RECT, 2, border_radius=18)
        prompt = self.title_font.render("Drop an image here", True, MUTED)
        helper = self.small_font.render("PNG, JPG, BMP, GIF or WEBP", True, MUTED)
        self.screen.blit(prompt, prompt.get_rect(center=(CANVAS_RECT.centerx, CANVAS_RECT.centery - 12)))
        self.screen.blit(helper, helper.get_rect(center=(CANVAS_RECT.centerx, CANVAS_RECT.centery + 28)))

    def draw_track(self) -> None:
        pygame.draw.rect(self.screen, PANEL, TRACK_RECT, border_radius=16)
        y = TRACK_RECT.centery
        pygame.draw.line(self.screen, TRACK, (TRACK_RECT.left + 18, y), (TRACK_RECT.right - 18, y), 4)
        for x in range(TRACK_RECT.left + 25, TRACK_RECT.right - 10, 55):
            pygame.draw.circle(self.screen, TRACK, (x, y), 5)

    def draw_hud(self) -> None:
        self.upload_button.draw(self.screen, self.font)
        self.reset_button.draw(self.screen, self.font)

        title = self.title_font.render("Sand Picture", True, TEXT)
        self.screen.blit(title, (965, 37))

        if self.picture.loaded:
            stats = (
                f"Sand: {self.picture.particle_count:,}/{self.picture.initial_particles:,}   "
                f"Buckets: {len(self.buckets)}/{MAX_BUCKETS}   Queue: {len(self.pending_colors)}"
            )
            stat_surf = self.small_font.render(stats, True, TEXT)
            self.screen.blit(stat_surf, (430, 48))

        choice_label = self.small_font.render(
            f"Choose a bucket color (samples bottom {SCOOP_ROWS} rows)",
            True,
            MUTED if self.picture.loaded else (92, 98, 111),
        )
        self.screen.blit(choice_label, choice_label.get_rect(center=(535, 786)))

        for button in self.color_buttons:
            button.draw(self.screen)

        self.tolerance_minus.enabled = self.picture.loaded and self.tolerance > MIN_TOLERANCE
        self.tolerance_plus.enabled = self.picture.loaded and self.tolerance < MAX_TOLERANCE
        self.tolerance_minus.draw(self.screen, self.font)
        self.tolerance_plus.draw(self.screen, self.font)

        tol_label = self.font.render(f"Tolerance  {self.tolerance}", True, TEXT if self.picture.loaded else MUTED)
        self.screen.blit(tol_label, tol_label.get_rect(center=(942, 841)))
        tol_help = self.tiny_font.render("RGB distance", True, MUTED)
        self.screen.blit(tol_help, tol_help.get_rect(center=(942, 869)))

        status = self.small_font.render(self.status, True, MUTED)
        self.screen.blit(status, (50, 895))

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        if self.picture.loaded:
            pygame.draw.rect(self.screen, PANEL, CANVAS_RECT, border_radius=18)
            pygame.draw.rect(self.screen, (57, 63, 75), CANVAS_RECT, 2, border_radius=18)
            self.picture.draw(self.screen)
        else:
            self.draw_empty_canvas()

        self.draw_track()
        for bucket in self.buckets:
            bucket.draw(self.screen, self.tiny_font)
        self.draw_hud()
        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
            for event in pygame.event.get():
                running = self.handle_event(event)
                if not running:
                    break
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    SandGame().run()
