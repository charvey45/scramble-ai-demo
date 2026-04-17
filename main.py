import json
import math
import random
from array import array
from dataclasses import dataclass
from pathlib import Path

import pygame


WIDTH = 1100
HEIGHT = 720
FPS = 60

BACKGROUND = (5, 8, 16)
STAR_COLOR = (170, 190, 215)
FOREGROUND = (234, 243, 255)
ACCENT = (255, 198, 92)
WARNING = (255, 100, 100)
GOOD = (128, 230, 160)
MUTED = (138, 154, 180)
GROUND_COLOR = (36, 132, 83)
GROUND_SHADE = (21, 80, 52)
CEILING_COLOR = (41, 73, 118)
CEILING_SHADE = (27, 48, 80)

SAVE_PATH = Path(__file__).with_name(".scramble-save.json")
WORLD_LENGTH = 9000
SCROLL_SPEED = 225
PLAYER_X = 235
PLAYER_SPEED_X = 160
PLAYER_SPEED_Y = 235
PLAYER_WOBBLE = 7
MAX_FUEL = 100.0
FUEL_DRAIN = 7.2
FUEL_GAIN = 36.0
BULLET_SPEED = 760
BULLET_COOLDOWN = 0.16
BOMB_SPEED_X = 140
BOMB_SPEED_Y = -25
BOMB_GRAVITY = 620
BOMB_COOLDOWN = 0.42
RESPAWN_INVULN = 2.1
PLAYER_RADIUS = 14
MISSILE_SPEED = 240
MISSILE_COOLDOWN = 2.2
DEFAULT_VOLUME = 0.12
VOLUME_STEP = 0.05
MIN_VOLUME = 0.0
MAX_VOLUME = 1.0

TARGET_SCORES = {
    "fuel": 180,
    "base": 120,
    "turret": 150,
}
ENEMY_SCORE = 90
LEVEL_CLEAR_BONUS = 500


@dataclass
class Bullet:
    position: pygame.Vector2
    velocity: pygame.Vector2
    ttl: float = 1.35


@dataclass
class Bomb:
    position: pygame.Vector2
    velocity: pygame.Vector2
    ttl: float = 3.0


@dataclass
class Particle:
    position: pygame.Vector2
    velocity: pygame.Vector2
    ttl: float
    max_ttl: float
    color: tuple[int, int, int]
    radius: float


@dataclass
class Player:
    position: pygame.Vector2
    velocity: pygame.Vector2
    lives: int = 3
    fuel: float = MAX_FUEL
    bullet_cooldown: float = 0.0
    bomb_cooldown: float = 0.0
    invulnerability: float = RESPAWN_INVULN


@dataclass
class Target:
    kind: str
    world_x: float
    width: float
    height: float
    y: float
    alive: bool = True
    cooldown: float = 0.0


@dataclass
class Enemy:
    world_x: float
    y: float
    vx: float
    wobble: float
    seed: float
    alive: bool = True


@dataclass
class Missile:
    position: pygame.Vector2
    velocity: pygame.Vector2
    ttl: float = 4.0


@dataclass
class SoundSettings:
    enabled: bool = True
    volume: float = DEFAULT_VOLUME


@dataclass
class SoundBank:
    shoot: pygame.mixer.Sound | None
    bomb: pygame.mixer.Sound | None
    hit: pygame.mixer.Sound | None
    fuel: pygame.mixer.Sound | None
    ship_hit: pygame.mixer.Sound | None
    level_up: pygame.mixer.Sound | None


@dataclass
class Session:
    player: Player
    bullets: list[Bullet]
    bombs: list[Bomb]
    particles: list[Particle]
    targets: list[Target]
    enemies: list[Enemy]
    missiles: list[Missile]
    progress: float
    score: int
    best_score: int
    level: int
    state: str
    level_flash: float = 0.0
    new_high_score: bool = False


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def world_seed(level: int) -> int:
    return 4086 + (level * 97)


def sector_name(level_progress: float) -> str:
    markers = (
        (0.18, "Launch Zone"),
        (0.36, "Fuel Depot"),
        (0.56, "Mountain Belt"),
        (0.76, "Cave Run"),
        (1.01, "Final Battery"),
    )
    for cutoff, label in markers:
        if level_progress < cutoff:
            return label
    return "Final Battery"


def make_stars() -> list[tuple[int, int, int]]:
    rng = random.Random(17)
    stars: list[tuple[int, int, int]] = []
    for _ in range(90):
        stars.append(
            (
                rng.randint(0, WORLD_LENGTH - 1),
                rng.randint(18, HEIGHT - 18),
                rng.randint(1, 3),
            )
        )
    return stars


STARS = make_stars()


def heading(angle: float) -> pygame.Vector2:
    radians = math.radians(angle)
    return pygame.Vector2(math.cos(radians), math.sin(radians))


def terrain_noise(x: float, seed: int, scale: float) -> float:
    return (
        math.sin((x + seed * 19) / scale)
        + 0.55 * math.sin((x + seed * 37) / (scale * 0.47))
        + 0.28 * math.sin((x + seed * 73) / (scale * 0.21))
    )


def floor_height(world_x: float, level: int) -> float:
    seed = world_seed(level)
    progress = world_x / WORLD_LENGTH
    base = HEIGHT - 150
    if progress < 0.20:
        base += 28
        amplitude = 22
        scale = 370
    elif progress < 0.42:
        base += 8
        amplitude = 45
        scale = 280
    elif progress < 0.66:
        base -= 18
        amplitude = 78
        scale = 220
    elif progress < 0.82:
        base -= 6
        amplitude = 36
        scale = 300
    else:
        base += 18
        amplitude = 58
        scale = 205
    value = base + (terrain_noise(world_x, seed, scale) * amplitude)
    return clamp(value, HEIGHT * 0.48, HEIGHT - 82)


def ceiling_height(world_x: float, level: int) -> float:
    progress = world_x / WORLD_LENGTH
    if progress < 0.58:
        return 0.0
    seed = world_seed(level) + 121
    if progress < 0.82:
        base = 110
        amplitude = 44
        scale = 255
    else:
        base = 84
        amplitude = 54
        scale = 200
    value = base + (terrain_noise(world_x, seed, scale) * amplitude)
    return clamp(value, 36, HEIGHT * 0.42)


def corridor_ok(y: float, world_x: float, level: int, radius: float = PLAYER_RADIUS) -> bool:
    top = ceiling_height(world_x, level)
    bottom = floor_height(world_x, level)
    return top + radius + 4 < y < bottom - radius - 4


def target_color(kind: str) -> tuple[int, int, int]:
    if kind == "fuel":
        return GOOD
    if kind == "turret":
        return WARNING
    return ACCENT


def spawn_targets(level: int) -> list[Target]:
    rng = random.Random(world_seed(level) + 900)
    targets: list[Target] = []
    x = 620.0
    while x < WORLD_LENGTH - 260:
        progress = x / WORLD_LENGTH
        floor_y = floor_height(x, level)
        kind_roll = rng.random()
        if progress < 0.24 and kind_roll < 0.40:
            kind = "fuel"
        elif progress > 0.74 and kind_roll < 0.28:
            kind = "turret"
        else:
            kind = "base"

        if kind == "fuel":
            width = 28
            height = 34
        elif kind == "turret":
            width = 32
            height = 24
        else:
            width = 42
            height = 22

        targets.append(
            Target(
                kind=kind,
                world_x=x,
                width=width,
                height=height,
                y=floor_y - height,
                cooldown=rng.uniform(0.4, 1.8),
            )
        )
        x += rng.uniform(180, 360)
    return targets


def spawn_enemies(level: int) -> list[Enemy]:
    rng = random.Random(world_seed(level) + 1700)
    enemies: list[Enemy] = []
    x = 880.0
    while x < WORLD_LENGTH - 340:
        floor_y = floor_height(x, level)
        ceiling_y = ceiling_height(x, level)
        y = rng.uniform(ceiling_y + 110, floor_y - 95)
        enemies.append(
            Enemy(
                world_x=x,
                y=y,
                vx=rng.uniform(-50, 65),
                wobble=rng.uniform(10, 25),
                seed=rng.uniform(0, math.pi * 2),
            )
        )
        x += rng.uniform(420, 760)
    return enemies


def reset_player() -> Player:
    return Player(
        position=pygame.Vector2(PLAYER_X, HEIGHT * 0.38),
        velocity=pygame.Vector2(),
    )


def load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_sound_settings(payload: dict[str, object]) -> SoundSettings:
    raw = payload.get("sound", {})
    if not isinstance(raw, dict):
        return SoundSettings()
    enabled = raw.get("enabled", True)
    volume = raw.get("volume", DEFAULT_VOLUME)
    if not isinstance(enabled, bool):
        enabled = True
    if not isinstance(volume, (int, float)):
        volume = DEFAULT_VOLUME
    return SoundSettings(enabled=enabled, volume=clamp(float(volume), MIN_VOLUME, MAX_VOLUME))


def load_best_score(payload: dict[str, object]) -> int:
    best_score = payload.get("best_score", 0)
    return best_score if isinstance(best_score, int) and best_score >= 0 else 0


def save_progress(best_score: int, sound_settings: SoundSettings) -> None:
    payload = {
        "best_score": max(0, int(best_score)),
        "sound": {
            "enabled": sound_settings.enabled,
            "volume": round(clamp(sound_settings.volume, MIN_VOLUME, MAX_VOLUME), 2),
        },
    }
    try:
        SAVE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def create_session(level: int, best_score: int) -> Session:
    return Session(
        player=reset_player(),
        bullets=[],
        bombs=[],
        particles=[],
        targets=spawn_targets(level),
        enemies=spawn_enemies(level),
        missiles=[],
        progress=0.0,
        score=0,
        best_score=best_score,
        level=level,
        state="title",
    )


def build_tone(
    frequency: float,
    duration: float,
    *,
    volume: float,
    waveform: str = "sine",
    sweep: float = 0.0,
    noise_mix: float = 0.0,
) -> pygame.mixer.Sound | None:
    mixer_settings = pygame.mixer.get_init()
    if mixer_settings is None:
        return None

    sample_rate, _, channels = mixer_settings
    sample_count = max(1, int(duration * sample_rate))
    samples = array("h")
    phase = 0.0

    for index in range(sample_count):
        progress = index / sample_count
        current_frequency = max(35.0, frequency + (sweep * progress))
        phase += (2 * math.pi * current_frequency) / sample_rate

        if waveform == "square":
            tone = 1.0 if math.sin(phase) >= 0 else -1.0
        elif waveform == "triangle":
            tone = (2.0 / math.pi) * math.asin(math.sin(phase))
        elif waveform == "noise":
            tone = random.uniform(-1.0, 1.0)
        else:
            tone = math.sin(phase)

        if noise_mix:
            tone = (tone * (1.0 - noise_mix)) + (random.uniform(-1.0, 1.0) * noise_mix)

        envelope = (1.0 - progress) ** 1.7
        sample = int(clamp(tone * volume * envelope, -1.0, 1.0) * 32767)
        samples.append(sample)

    if channels == 2:
        stereo = array("h")
        for sample in samples:
            stereo.append(sample)
            stereo.append(sample)
        return pygame.mixer.Sound(buffer=stereo.tobytes())
    return pygame.mixer.Sound(buffer=samples.tobytes())


def build_sound_bank() -> SoundBank:
    return SoundBank(
        shoot=build_tone(780, 0.08, volume=0.18, waveform="square", sweep=-210),
        bomb=build_tone(190, 0.2, volume=0.22, waveform="triangle", sweep=-90),
        hit=build_tone(155, 0.24, volume=0.28, waveform="noise", sweep=-45, noise_mix=0.35),
        fuel=build_tone(510, 0.18, volume=0.18, waveform="triangle", sweep=180),
        ship_hit=build_tone(96, 0.46, volume=0.32, waveform="noise", sweep=-60, noise_mix=0.58),
        level_up=build_tone(430, 0.35, volume=0.16, waveform="square", sweep=280),
    )


def apply_sound_settings(sound_bank: SoundBank, settings: SoundSettings) -> None:
    volume = settings.volume if settings.enabled else 0.0
    for sound in (
        sound_bank.shoot,
        sound_bank.bomb,
        sound_bank.hit,
        sound_bank.fuel,
        sound_bank.ship_hit,
        sound_bank.level_up,
    ):
        if sound is not None:
            sound.set_volume(volume)


def play_sound(sound: pygame.mixer.Sound | None) -> None:
    if sound is not None:
        sound.play()


def toggle_sound(sound_bank: SoundBank, sound_settings: SoundSettings) -> None:
    sound_settings.enabled = not sound_settings.enabled
    apply_sound_settings(sound_bank, sound_settings)


def adjust_volume(sound_bank: SoundBank, sound_settings: SoundSettings, delta: float) -> None:
    sound_settings.volume = clamp(sound_settings.volume + delta, MIN_VOLUME, MAX_VOLUME)
    apply_sound_settings(sound_bank, sound_settings)


def sound_status_text(settings: SoundSettings) -> str:
    if not settings.enabled:
        return f"Sound Off ({round(settings.volume * 100):d}%)"
    return f"Sound On ({round(settings.volume * 100):d}%)"


def emit_particles(
    position: pygame.Vector2,
    count: int,
    color: tuple[int, int, int],
    *,
    speed_range: tuple[float, float],
    ttl_range: tuple[float, float],
    radius_range: tuple[float, float],
) -> list[Particle]:
    particles: list[Particle] = []
    for _ in range(count):
        lifetime = random.uniform(*ttl_range)
        particles.append(
            Particle(
                position=position.copy(),
                velocity=heading(random.uniform(0, 360)) * random.uniform(*speed_range),
                ttl=lifetime,
                max_ttl=lifetime,
                color=color,
                radius=random.uniform(*radius_range),
            )
        )
    return particles


def update_particles(particles: list[Particle], dt: float) -> None:
    for particle in particles[:]:
        particle.position += particle.velocity * dt
        particle.velocity *= 0.96
        particle.ttl -= dt
        if particle.ttl <= 0:
            particles.remove(particle)


def draw_particles(surface: pygame.Surface, particles: list[Particle]) -> None:
    for particle in particles:
        ratio = particle.ttl / particle.max_ttl
        radius = max(1, int(particle.radius * (0.45 + ratio)))
        color = tuple(int(channel * (0.30 + (0.70 * ratio))) for channel in particle.color)
        pygame.draw.circle(surface, color, particle.position, radius)


def player_polygon(player: Player, ticks: int) -> list[tuple[float, float]]:
    center = player.position
    wobble = math.sin(ticks * 0.01) * PLAYER_WOBBLE
    return [
        (center.x - 18, center.y),
        (center.x - 6, center.y - 11),
        (center.x + 15, center.y - 8),
        (center.x + 21, center.y),
        (center.x + 15, center.y + 8),
        (center.x - 6, center.y + 11),
        (center.x - 12, center.y + wobble * 0.18),
    ]


def bullet_hits_target(bullet: Bullet, target: Target, scroll_x: float) -> bool:
    screen_x = target.world_x - scroll_x
    rect = pygame.Rect(screen_x, target.y, target.width, target.height)
    return rect.inflate(8, 8).collidepoint(bullet.position.x, bullet.position.y)


def bomb_hits_target(bomb: Bomb, target: Target, scroll_x: float) -> bool:
    screen_x = target.world_x - scroll_x
    rect = pygame.Rect(screen_x, target.y, target.width, target.height)
    return rect.inflate(10, 10).collidepoint(bomb.position.x, bomb.position.y)


def bullet_hits_enemy(bullet: Bullet, enemy: Enemy, scroll_x: float) -> bool:
    screen_x = enemy.world_x - scroll_x
    return pygame.Vector2(screen_x, enemy.y).distance_to(bullet.position) < 18


def bomb_hits_enemy(bomb: Bomb, enemy: Enemy, scroll_x: float) -> bool:
    screen_x = enemy.world_x - scroll_x
    return pygame.Vector2(screen_x, enemy.y).distance_to(bomb.position) < 20


def missile_hits_player(missile: Missile, player: Player) -> bool:
    return missile.position.distance_to(player.position) < 16 + PLAYER_RADIUS


def enemy_hits_player(enemy: Enemy, player: Player, scroll_x: float) -> bool:
    return pygame.Vector2(enemy.world_x - scroll_x, enemy.y).distance_to(player.position) < 22 + PLAYER_RADIUS


def target_hits_player(target: Target, player: Player, scroll_x: float) -> bool:
    screen_x = target.world_x - scroll_x
    rect = pygame.Rect(screen_x, target.y, target.width, target.height)
    return rect.inflate(8, 8).collidepoint(player.position.x, player.position.y)


def respawn_player(player: Player, level: int, progress: float) -> None:
    player.position = pygame.Vector2(PLAYER_X, HEIGHT * 0.34)
    player.velocity = pygame.Vector2()
    player.invulnerability = RESPAWN_INVULN
    player.bullet_cooldown = 0.0
    player.bomb_cooldown = 0.0

    for offset in range(0, 220, 20):
        sample_x = progress + offset
        top = ceiling_height(sample_x, level)
        bottom = floor_height(sample_x, level)
        safe_y = clamp((top + bottom) * 0.5, top + 70, bottom - 70)
        if corridor_ok(safe_y, sample_x, level, radius=PLAYER_RADIUS + 6):
            player.position.y = safe_y
            return


def crash_player(
    session: Session,
    sound_bank: SoundBank,
    sound_settings: SoundSettings,
    *,
    preserve_progress: bool = True,
) -> None:
    session.particles.extend(
        emit_particles(
            session.player.position,
            18,
            WARNING,
            speed_range=(80, 230),
            ttl_range=(0.35, 0.9),
            radius_range=(2.0, 4.2),
        )
    )
    session.particles.extend(
        emit_particles(
            session.player.position,
            12,
            ACCENT,
            speed_range=(50, 170),
            ttl_range=(0.25, 0.7),
            radius_range=(1.3, 3.4),
        )
    )
    play_sound(sound_bank.ship_hit)
    session.player.lives -= 1
    session.bullets.clear()
    session.bombs.clear()
    session.missiles.clear()

    if session.player.lives <= 0:
        session.state = "game_over"
        if session.score > session.best_score:
            session.best_score = session.score
            session.new_high_score = True
            save_progress(session.best_score, sound_settings)
        else:
            session.new_high_score = False
        return

    if not preserve_progress:
        session.progress = 0.0
    respawn_player(session.player, session.level, session.progress)


def draw_stars(surface: pygame.Surface, scroll_x: float) -> None:
    for star_world_x, star_y, radius in STARS:
        parallax = (scroll_x * (0.15 + (radius * 0.04))) % WIDTH
        screen_x = (star_world_x - parallax) % WIDTH
        pygame.draw.circle(surface, STAR_COLOR, (screen_x, star_y), radius)


def draw_terrain(surface: pygame.Surface, scroll_x: float, level: int) -> None:
    top_points = [(0, 0)]
    bottom_points = [(0, HEIGHT)]
    for screen_x in range(0, WIDTH + 24, 24):
        world_x = scroll_x + screen_x
        top_points.append((screen_x, ceiling_height(world_x, level)))
        bottom_points.append((screen_x, floor_height(world_x, level)))
    top_points.append((WIDTH, 0))
    bottom_points.append((WIDTH, HEIGHT))
    pygame.draw.polygon(surface, CEILING_SHADE, top_points)
    pygame.draw.polygon(surface, CEILING_COLOR, top_points, width=3)
    pygame.draw.polygon(surface, GROUND_SHADE, bottom_points)
    pygame.draw.polygon(surface, GROUND_COLOR, bottom_points, width=3)


def draw_target(surface: pygame.Surface, target: Target, scroll_x: float) -> None:
    if not target.alive:
        return
    x = target.world_x - scroll_x
    if x < -target.width - 24 or x > WIDTH + 24:
        return
    rect = pygame.Rect(int(x), int(target.y), int(target.width), int(target.height))
    pygame.draw.rect(surface, target_color(target.kind), rect, width=2, border_radius=2)
    if target.kind == "fuel":
        inner = rect.inflate(-8, -6)
        pygame.draw.rect(surface, GOOD, inner, width=1)
        cap = pygame.Rect(rect.centerx - 5, rect.y - 6, 10, 6)
        pygame.draw.rect(surface, GOOD, cap, width=1)
    elif target.kind == "turret":
        pygame.draw.line(surface, WARNING, rect.midtop, (rect.centerx + 10, rect.y - 10), width=2)
    else:
        pad = pygame.Rect(rect.x + 6, rect.y + 5, rect.width - 12, rect.height - 10)
        pygame.draw.rect(surface, ACCENT, pad, width=1)


def draw_enemy(surface: pygame.Surface, enemy: Enemy, scroll_x: float) -> None:
    if not enemy.alive:
        return
    x = enemy.world_x - scroll_x
    if x < -40 or x > WIDTH + 40:
        return
    points = [
        (x - 18, enemy.y),
        (x - 6, enemy.y - 9),
        (x + 10, enemy.y - 7),
        (x + 18, enemy.y),
        (x + 10, enemy.y + 7),
        (x - 6, enemy.y + 9),
    ]
    pygame.draw.polygon(surface, FOREGROUND, points, width=2)
    pygame.draw.line(surface, ACCENT, (x - 5, enemy.y), (x + 9, enemy.y), width=2)


def draw_player(surface: pygame.Surface, player: Player, ticks: int) -> None:
    flicker = player.invulnerability > 0 and (ticks // 120) % 2 == 0
    if flicker:
        return
    points = player_polygon(player, ticks)
    pygame.draw.polygon(surface, FOREGROUND, points, width=2)
    engine = [
        (player.position.x - 18, player.position.y),
        (player.position.x - 30, player.position.y + math.sin(ticks * 0.025) * 5),
        (player.position.x - 18, player.position.y + 6),
    ]
    pygame.draw.polygon(surface, ACCENT, engine, width=2)


def draw_hud(surface: pygame.Surface, session: Session, sound_settings: SoundSettings, hud_font: pygame.font.Font, small_font: pygame.font.Font) -> None:
    fuel_ratio = clamp(session.player.fuel / MAX_FUEL, 0.0, 1.0)
    section = sector_name(session.progress / WORLD_LENGTH)
    score_text = hud_font.render(f"Score {session.score:05d}", True, FOREGROUND)
    best_text = hud_font.render(f"Best {session.best_score:05d}", True, FOREGROUND)
    lives_text = hud_font.render(f"Ships {session.player.lives}", True, FOREGROUND)
    level_text = hud_font.render(f"Wave {session.level}", True, FOREGROUND)
    section_text = hud_font.render(section, True, ACCENT)
    sound_text = small_font.render(sound_status_text(sound_settings), True, MUTED)
    help_text = small_font.render("Arrows move   Space fire   X drop bomb   M toggle sound   +/- volume", True, MUTED)

    surface.blit(score_text, (24, 20))
    surface.blit(best_text, (24, 50))
    surface.blit(lives_text, (24, 80))
    surface.blit(level_text, (24, 110))
    surface.blit(section_text, (24, 140))
    surface.blit(sound_text, (24, HEIGHT - 64))
    surface.blit(help_text, (24, HEIGHT - 36))

    bar_rect = pygame.Rect(WIDTH - 244, 24, 200, 18)
    pygame.draw.rect(surface, MUTED, bar_rect, width=2)
    pygame.draw.rect(surface, GOOD if fuel_ratio > 0.35 else WARNING, (bar_rect.x + 3, bar_rect.y + 3, int((bar_rect.width - 6) * fuel_ratio), bar_rect.height - 6))
    label = small_font.render("Fuel", True, FOREGROUND)
    surface.blit(label, (WIDTH - 290, 21))


def advance_level(session: Session, sound_bank: SoundBank, sound_settings: SoundSettings) -> None:
    session.score += LEVEL_CLEAR_BONUS
    session.level += 1
    session.progress = 0.0
    session.targets = spawn_targets(session.level)
    session.enemies = spawn_enemies(session.level)
    session.missiles.clear()
    session.bullets.clear()
    session.bombs.clear()
    session.player.fuel = MAX_FUEL
    session.player.position = pygame.Vector2(PLAYER_X, HEIGHT * 0.38)
    session.player.velocity = pygame.Vector2()
    session.player.invulnerability = RESPAWN_INVULN
    session.level_flash = 1.2
    play_sound(sound_bank.level_up)
    if session.score > session.best_score:
        session.best_score = session.score
        save_progress(session.best_score, sound_settings)


def draw_message_overlay(
    surface: pygame.Surface,
    lines: list[tuple[str, pygame.font.Font, tuple[int, int, int]]],
    start_y: float,
) -> None:
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((2, 4, 8, 160))
    surface.blit(overlay, (0, 0))
    y = start_y
    for text, font, color in lines:
        render = font.render(text, True, color)
        surface.blit(render, render.get_rect(center=(WIDTH / 2, y)))
        y += render.get_height() + 14


def update_game(session: Session, sound_bank: SoundBank, sound_settings: SoundSettings, dt: float, keys: pygame.key.ScancodeWrapper) -> None:
    player = session.player
    player.velocity.update(0, 0)
    if keys[pygame.K_LEFT]:
        player.velocity.x = -PLAYER_SPEED_X
    if keys[pygame.K_RIGHT]:
        player.velocity.x = PLAYER_SPEED_X
    if keys[pygame.K_UP]:
        player.velocity.y = -PLAYER_SPEED_Y
    if keys[pygame.K_DOWN]:
        player.velocity.y = PLAYER_SPEED_Y

    session.progress += SCROLL_SPEED * dt
    player.position += player.velocity * dt
    player.position.x = clamp(player.position.x, 110, WIDTH - 150)
    player.position.y = clamp(player.position.y, 42, HEIGHT - 42)
    player.fuel = clamp(player.fuel - (FUEL_DRAIN * dt), 0.0, MAX_FUEL)
    player.bullet_cooldown = max(0.0, player.bullet_cooldown - dt)
    player.bomb_cooldown = max(0.0, player.bomb_cooldown - dt)
    player.invulnerability = max(0.0, player.invulnerability - dt)
    session.level_flash = max(0.0, session.level_flash - dt)

    if player.fuel <= 0.0 and session.state == "playing":
        crash_player(session, sound_bank, sound_settings)
        return

    if keys[pygame.K_SPACE] and player.bullet_cooldown == 0.0:
        session.bullets.append(
            Bullet(
                position=pygame.Vector2(player.position.x + 22, player.position.y),
                velocity=pygame.Vector2(BULLET_SPEED, 0),
            )
        )
        player.bullet_cooldown = BULLET_COOLDOWN
        play_sound(sound_bank.shoot)

    if keys[pygame.K_x] and player.bomb_cooldown == 0.0:
        session.bombs.append(
            Bomb(
                position=pygame.Vector2(player.position.x + 8, player.position.y + 12),
                velocity=pygame.Vector2(BOMB_SPEED_X, BOMB_SPEED_Y),
            )
        )
        player.bomb_cooldown = BOMB_COOLDOWN
        play_sound(sound_bank.bomb)

    scroll_x = session.progress

    floor_now = floor_height(scroll_x + player.position.x, session.level)
    ceiling_now = ceiling_height(scroll_x + player.position.x, session.level)
    if player.invulnerability == 0.0:
        if player.position.y + PLAYER_RADIUS >= floor_now or player.position.y - PLAYER_RADIUS <= ceiling_now:
            crash_player(session, sound_bank, sound_settings)
            return

    for bullet in session.bullets[:]:
        bullet.position += bullet.velocity * dt
        bullet.ttl -= dt
        bullet_world_x = scroll_x + bullet.position.x
        floor_y = floor_height(bullet_world_x, session.level)
        ceiling_y = ceiling_height(bullet_world_x, session.level)
        if bullet.ttl <= 0 or bullet.position.x > WIDTH + 40 or bullet.position.y >= floor_y or bullet.position.y <= ceiling_y:
            session.bullets.remove(bullet)

    for bomb in session.bombs[:]:
        bomb.velocity.y += BOMB_GRAVITY * dt
        bomb.position += bomb.velocity * dt
        bomb.ttl -= dt
        bomb_world_x = scroll_x + bomb.position.x
        floor_y = floor_height(bomb_world_x, session.level)
        ceiling_y = ceiling_height(bomb_world_x, session.level)
        if bomb.ttl <= 0 or bomb.position.x > WIDTH + 60 or bomb.position.y >= floor_y or bomb.position.y <= ceiling_y:
            session.particles.extend(
                emit_particles(
                    bomb.position,
                    7,
                    ACCENT,
                    speed_range=(30, 140),
                    ttl_range=(0.18, 0.5),
                    radius_range=(1.1, 2.6),
                )
            )
            session.bombs.remove(bomb)

    for target in session.targets:
        if not target.alive:
            continue
        if target.kind == "turret":
            target.cooldown = max(0.0, target.cooldown - dt)
            target_screen_x = target.world_x - scroll_x
            if -30 < target_screen_x < WIDTH + 30 and target.cooldown == 0.0:
                target.cooldown = MISSILE_COOLDOWN + random.uniform(-0.45, 0.45)
                missile_start = pygame.Vector2(target_screen_x + (target.width * 0.5), target.y - 6)
                direction = (player.position - missile_start)
                if direction.length_squared() > 0:
                    direction = direction.normalize()
                else:
                    direction = pygame.Vector2(-1, -1)
                session.missiles.append(
                    Missile(
                        position=missile_start,
                        velocity=direction * MISSILE_SPEED,
                    )
                )

    for enemy in session.enemies:
        if not enemy.alive:
            continue
        enemy.world_x += enemy.vx * dt
        enemy.y += math.sin((session.progress * 0.014) + enemy.seed) * enemy.wobble * dt
        bottom = floor_height(enemy.world_x, session.level) - 46
        top = ceiling_height(enemy.world_x, session.level) + 46
        enemy.y = clamp(enemy.y, top, bottom)

    for missile in session.missiles[:]:
        missile.position += missile.velocity * dt
        missile.position.x -= SCROLL_SPEED * dt
        missile.ttl -= dt
        missile_world_x = scroll_x + missile.position.x
        floor_y = floor_height(missile_world_x, session.level)
        ceiling_y = ceiling_height(missile_world_x, session.level)
        if missile.ttl <= 0 or missile.position.x < -40 or missile.position.y >= floor_y or missile.position.y <= ceiling_y:
            session.missiles.remove(missile)
            continue
        if player.invulnerability == 0.0 and missile_hits_player(missile, player):
            session.missiles.remove(missile)
            crash_player(session, sound_bank, sound_settings)
            return

    for bullet in session.bullets[:]:
        for target in session.targets:
            if target.alive and bullet_hits_target(bullet, target, scroll_x):
                target.alive = False
                session.score += TARGET_SCORES[target.kind]
                if target.kind == "fuel":
                    player.fuel = clamp(player.fuel + FUEL_GAIN, 0.0, MAX_FUEL)
                    play_sound(sound_bank.fuel)
                else:
                    play_sound(sound_bank.hit)
                session.particles.extend(
                    emit_particles(
                        bullet.position,
                        10,
                        target_color(target.kind),
                        speed_range=(40, 150),
                        ttl_range=(0.2, 0.55),
                        radius_range=(1.2, 3.0),
                    )
                )
                session.bullets.remove(bullet)
                break
        else:
            for enemy in session.enemies:
                if enemy.alive and bullet_hits_enemy(bullet, enemy, scroll_x):
                    enemy.alive = False
                    session.score += ENEMY_SCORE
                    play_sound(sound_bank.hit)
                    session.particles.extend(
                        emit_particles(
                            bullet.position,
                            12,
                            FOREGROUND,
                            speed_range=(50, 170),
                            ttl_range=(0.18, 0.48),
                            radius_range=(1.2, 2.8),
                        )
                    )
                    session.bullets.remove(bullet)
                    break

    for bomb in session.bombs[:]:
        for target in session.targets:
            if target.alive and bomb_hits_target(bomb, target, scroll_x):
                target.alive = False
                session.score += TARGET_SCORES[target.kind]
                if target.kind == "fuel":
                    player.fuel = clamp(player.fuel + FUEL_GAIN, 0.0, MAX_FUEL)
                    play_sound(sound_bank.fuel)
                else:
                    play_sound(sound_bank.hit)
                session.particles.extend(
                    emit_particles(
                        bomb.position,
                        14,
                        target_color(target.kind),
                        speed_range=(55, 180),
                        ttl_range=(0.22, 0.6),
                        radius_range=(1.3, 3.2),
                    )
                )
                session.bombs.remove(bomb)
                break
        else:
            for enemy in session.enemies:
                if enemy.alive and bomb_hits_enemy(bomb, enemy, scroll_x):
                    enemy.alive = False
                    session.score += ENEMY_SCORE
                    play_sound(sound_bank.hit)
                    session.particles.extend(
                        emit_particles(
                            bomb.position,
                            14,
                            ACCENT,
                            speed_range=(60, 185),
                            ttl_range=(0.22, 0.6),
                            radius_range=(1.4, 3.4),
                        )
                    )
                    session.bombs.remove(bomb)
                    break

    if player.invulnerability == 0.0:
        for enemy in session.enemies:
            if enemy.alive and enemy_hits_player(enemy, player, scroll_x):
                crash_player(session, sound_bank, sound_settings)
                return
        for target in session.targets:
            if target.alive and target_hits_player(target, player, scroll_x):
                crash_player(session, sound_bank, sound_settings)
                return

    if session.score > session.best_score:
        session.best_score = session.score

    if session.progress >= WORLD_LENGTH:
        advance_level(session, sound_bank, sound_settings)


def draw_game(surface: pygame.Surface, session: Session, sound_settings: SoundSettings, hud_font: pygame.font.Font, title_font: pygame.font.Font, hero_font: pygame.font.Font, small_font: pygame.font.Font) -> None:
    surface.fill(BACKGROUND)
    draw_stars(surface, session.progress)
    draw_terrain(surface, session.progress, session.level)

    for target in session.targets:
        draw_target(surface, target, session.progress)
    for enemy in session.enemies:
        draw_enemy(surface, enemy, session.progress)
    for missile in session.missiles:
        pygame.draw.line(surface, WARNING, missile.position, missile.position - (missile.velocity.normalize() * 12), width=2)
    for bullet in session.bullets:
        pygame.draw.circle(surface, FOREGROUND, bullet.position, 3)
    for bomb in session.bombs:
        pygame.draw.circle(surface, ACCENT, bomb.position, 4, width=2)

    draw_particles(surface, session.particles)
    if session.state != "title":
        draw_player(surface, session.player, pygame.time.get_ticks())
        draw_hud(surface, session, sound_settings, hud_font, small_font)

    if session.level_flash > 0.0 and session.state == "playing":
        alpha = int(110 * (session.level_flash / 1.2))
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash.fill((255, 210, 90, alpha))
        surface.blit(flash, (0, 0))

    if session.state == "title":
        lines = [
            ("SCRAMBLE", hero_font, FOREGROUND),
            ("A compact side-scrolling arcade run built with Python and pygame", hud_font, ACCENT),
            (f"Best Score {session.best_score:05d}", title_font, FOREGROUND),
            ("Press Enter or Space to launch", hud_font, FOREGROUND),
            ("Arrows move   Space fire   X drops bombs   M toggles sound   +/- volume", small_font, MUTED),
            (sound_status_text(sound_settings), small_font, FOREGROUND),
        ]
        draw_message_overlay(surface, lines, HEIGHT * 0.24)

    if session.state == "game_over":
        banner = "New high score!" if session.new_high_score else "Fuel management matters."
        lines = [
            ("Mission Failed", title_font, WARNING),
            (f"Final Score {session.score:05d}", hud_font, FOREGROUND),
            (f"Best Score {session.best_score:05d}", hud_font, FOREGROUND),
            (banner, hud_font, ACCENT),
            ("Press Enter, Space, or R to fly again", hud_font, FOREGROUND),
        ]
        draw_message_overlay(surface, lines, HEIGHT * 0.30)


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("Scramble")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    hud_font = pygame.font.SysFont("consolas", 24)
    title_font = pygame.font.SysFont("consolas", 38, bold=True)
    hero_font = pygame.font.SysFont("consolas", 80, bold=True)
    small_font = pygame.font.SysFont("consolas", 18)

    save_payload = load_json(SAVE_PATH)
    sound_settings = load_sound_settings(save_payload)
    sound_bank = build_sound_bank()
    apply_sound_settings(sound_bank, sound_settings)

    session = create_session(level=1, best_score=load_best_score(save_payload))
    running = True

    while running:
        dt = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                toggle_sound(sound_bank, sound_settings)
                save_progress(session.best_score, sound_settings)
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                adjust_volume(sound_bank, sound_settings, -VOLUME_STEP)
                save_progress(session.best_score, sound_settings)
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                adjust_volume(sound_bank, sound_settings, VOLUME_STEP)
                save_progress(session.best_score, sound_settings)
            elif event.type == pygame.KEYDOWN and session.state == "title" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                session = create_session(level=1, best_score=session.best_score)
                session.state = "playing"
            elif event.type == pygame.KEYDOWN and session.state == "game_over" and event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                session = create_session(level=1, best_score=session.best_score)
                session.state = "playing"

        keys = pygame.key.get_pressed()
        if session.state == "playing":
            update_game(session, sound_bank, sound_settings, dt, keys)

        update_particles(session.particles, dt)
        draw_game(screen, session, sound_settings, hud_font, title_font, hero_font, small_font)
        pygame.display.flip()

    if session.best_score < session.score:
        session.best_score = session.score
    save_progress(session.best_score, sound_settings)
    pygame.quit()


if __name__ == "__main__":
    main()
