from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 820
FPS = 60
PHYSICS_HZ = 30

BACKGROUND = (21, 24, 31)
PANEL = (33, 37, 47)
PANEL_LIGHT = (46, 51, 63)
TEXT = (237, 240, 246)
MUTED = (161, 169, 184)
ACCENT = (83, 152, 255)
TRACK = (107, 114, 128)
BUCKET_BODY = (92, 102, 118)
BUCKET_RIM = (177, 186, 201)

CANVAS_RECT = pygame.Rect(50, 110, 1000, 555)
TRACK_RECT = pygame.Rect(105, 685, 890, 72)

# The source image is merged into at most this many simulation cells.
MAX_GRID_W = 190
MAX_GRID_H = 120
MIN_CELL_SIZE = 3
MAX_CELL_SIZE = 6


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    enabled: bool = True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, active: bool = False) -> None:
        if not self.enabled:
            fill = (54, 58, 68)
            color = (112, 119, 132)
        elif active:
            fill = ACCENT
            color = (255, 255, 255)
        else:
            fill = PANEL_LIGHT
            color = TEXT

        pygame.draw.rect(surface, fill, self.rect, border_radius=10)
        if self.enabled and not active:
            pygame.draw.rect(surface, (66, 73, 88), self.rect, 1, border_radius=10)
        label = font.render(self.label, True, color)
        surface.blit(label, label.get_rect(center=self.rect.center))

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.enabled and self.rect.collidepoint(pos)


@dataclass
class Bucket:
    x: float
    y: int
    width: int
    height: int
    capacity: int
    scoop_depth: int
    speed: float = 52.0
    fill: int = 0
    moving: bool = True

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.x), self.y, self.width, self.height)

    @property
    def full(self) -> bool:
        return self.fill >= self.capacity

    def update(self, dt: float, left: int, right: int) -> None:
        if not self.moving or self.full:
            return
        self.x += self.speed * dt
        if self.x + self.width >= right:
            self.x = right - self.width
            self.moving = False

    def draw(self, surface: pygame.Surface) -> None:
        rect = self.rect
        rim = pygame.Rect(rect.x - 5, rect.y, rect.width + 10, 10)
        pygame.draw.rect(surface, BUCKET_RIM, rim, border_radius=5)
        pygame.draw.rect(surface, BUCKET_BODY, rect, border_radius=8)
        pygame.draw.rect(surface, (42, 47, 57), rect, 2, border_radius=8)

        inner = rect.inflate(-12, -16)
        inner.y += 5
        pygame.draw.rect(surface, (34, 38, 47), inner, border_radius=5)
        if self.capacity > 0 and self.fill > 0:
            ratio = min(1.0, self.fill / self.capacity)
            fill_h = max(2, int(inner.height * ratio))
            fill_rect = pygame.Rect(inner.x, inner.bottom - fill_h, inner.width, fill_h)
            pygame.draw.rect(surface, (211, 174, 111), fill_rect, border_radius=4)


class SandPicture:
    def __init__(self) -> None:
        self.grid: list[list[Optional[tuple[int, int, int]]]] = []
        self.original_grid: list[list[Optional[tuple[int, int, int]]]] = []
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

        grid: list[list[Optional[tuple[int, int, int]]]] = []
        for y in range(grid_h):
            row: list[Optional[tuple[int, int, int]]] = []
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

    def scoop(self, bucket: Bucket, max_grains: int = 6) -> int:
        if not self.loaded or bucket.full:
            return 0

        # Map the bucket mouth from screen pixels to sand-grid columns.
        bx0 = max(bucket.rect.left, self.pixel_rect.left)
        bx1 = min(bucket.rect.right, self.pixel_rect.right)
        if bx0 >= bx1:
            return 0

        x0 = max(0, (bx0 - self.pixel_rect.left) // self.cell_size)
        x1 = min(self.grid_w - 1, (bx1 - 1 - self.pixel_rect.left) // self.cell_size)
        y0 = max(0, self.grid_h - bucket.scoop_depth)

        candidates: list[tuple[int, int]] = []
        for y in range(self.grid_h - 1, y0 - 1, -1):
            for x in range(x0, x1 + 1):
                if self.grid[y][x] is not None:
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
        self.title_font = pygame.font.SysFont("arial", 30, bold=True)

        self.picture = SandPicture()
        self.bucket: Optional[Bucket] = None
        self.place_mode = False
        self.status = "Upload or drag-and-drop an image to begin."
        self.physics_accum = 0.0
        self.scoop_accum = 0.0

        self.upload_button = Button(pygame.Rect(50, 30, 170, 50), "Upload image")
        self.bucket_button = Button(pygame.Rect(235, 30, 170, 50), "Place bucket", enabled=False)
        self.reset_button = Button(pygame.Rect(420, 30, 120, 50), "Reset", enabled=False)

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
            self.bucket = None
            self.place_mode = False
            self.bucket_button.enabled = True
            self.reset_button.enabled = True
            self.status = (
                f"{self.picture.source_name}: {self.picture.grid_w}x{self.picture.grid_h} sand cells. "
                "Press Place bucket."
            )
        except Exception as exc:
            self.status = f"Could not load image: {exc}"

    def place_bucket(self) -> None:
        picture = self.picture.pixel_rect
        bucket_w = max(72, min(130, picture.width // 6))
        bucket_h = 48
        scoop_depth = random.randint(5, 15)
        capacity = max(180, min(1200, int(self.picture.initial_particles * 0.12)))
        self.bucket = Bucket(
            x=picture.left,
            y=TRACK_RECT.centery - bucket_h // 2,
            width=bucket_w,
            height=bucket_h,
            capacity=capacity,
            scoop_depth=scoop_depth,
        )
        self.picture.physics_active = True
        self.place_mode = False
        self.status = f"Bucket placed. Scooping the bottom {scoop_depth} rows."

    def reset(self) -> None:
        self.picture.reset()
        self.bucket = None
        self.place_mode = False
        if self.picture.loaded:
            self.status = "Picture reset. Press Place bucket for another run."

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.DROPFILE:
            self.load_image(event.file)
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.place_mode = False
            self.status = "Bucket placement cancelled."
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return True

        pos = event.pos
        if self.upload_button.hit(pos):
            path = self.choose_file()
            if path:
                self.load_image(path)
        elif self.bucket_button.hit(pos):
            self.place_mode = True
            self.status = "Click the track under the picture to place the bucket."
        elif self.reset_button.hit(pos):
            self.reset()
        elif self.place_mode and TRACK_RECT.collidepoint(pos):
            self.place_bucket()
        return True

    def update(self, dt: float) -> None:
        if self.bucket is not None:
            self.bucket.update(dt, self.picture.pixel_rect.left, self.picture.pixel_rect.right)

            # Scoop gradually so the erosion is visible instead of deleting a
            # whole stripe in one frame.
            self.scoop_accum += dt
            while self.scoop_accum >= 0.045:
                self.scoop_accum -= 0.045
                captured = self.picture.scoop(self.bucket, max_grains=5)
                if captured == 0 and not self.bucket.moving:
                    break

            if self.bucket.full:
                self.bucket.moving = False
                self.status = "Bucket full! Reset or upload another image."
            elif not self.bucket.moving:
                self.status = "Bucket reached the right edge. Reset to try another pass."

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
        if self.place_mode:
            pygame.draw.rect(self.screen, ACCENT, TRACK_RECT, 3, border_radius=16)

    def draw_hud(self) -> None:
        self.upload_button.draw(self.screen, self.font)
        self.bucket_button.draw(self.screen, self.font, active=self.place_mode)
        self.reset_button.draw(self.screen, self.font)

        title = self.title_font.render("Sand Picture", True, TEXT)
        self.screen.blit(title, (720, 37))

        status = self.small_font.render(self.status, True, MUTED)
        self.screen.blit(status, (50, 785))

        if self.picture.loaded:
            stats = f"Sand: {self.picture.particle_count:,}/{self.picture.initial_particles:,}"
            if self.bucket is not None:
                stats += f"   Bucket: {self.bucket.fill}/{self.bucket.capacity}   Depth: {self.bucket.scoop_depth} rows"
            stat_surf = self.small_font.render(stats, True, TEXT)
            self.screen.blit(stat_surf, (560, 54))

    def draw(self) -> None:
        self.screen.fill(BACKGROUND)
        if self.picture.loaded:
            pygame.draw.rect(self.screen, PANEL, CANVAS_RECT, border_radius=18)
            pygame.draw.rect(self.screen, (57, 63, 75), CANVAS_RECT, 2, border_radius=18)
            self.picture.draw(self.screen)
        else:
            self.draw_empty_canvas()

        self.draw_track()
        if self.bucket is not None:
            self.bucket.draw(self.screen)
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
