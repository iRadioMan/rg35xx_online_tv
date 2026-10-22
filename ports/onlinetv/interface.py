"""Interface rendering (pygame.draw, screen blit, etc). No application logic here."""
import math, base64, io

import pygame

W, H = 640, 480

# --- palette -----------------------------------------------------------------
BG = (0x11, 0x17, 0x22)
PANEL = (28, 37, 54)
PANEL_ALT = (22, 30, 45)
OUTLINE = (46, 58, 84)
WHITE = (255, 255, 255)
GRAY = (176, 184, 200)
MUTED = (110, 120, 140)
BLUE = (59, 130, 246)
TEAL = (45, 212, 191)
YELLOW = (250, 204, 21)
PURPLE = (167, 139, 250)
RED = (248, 113, 113)
BLUE_TOP = (82, 150, 255)
BLUE_BOT = (37, 99, 235)

# --- layout (from PROJECT.md) --------------------------------------------------
PREVIEW = pygame.Rect(39, 19, 450, 360)

BUTTONS = {
    "prev":     pygame.Rect(142, 397, 64, 64),
    "play":     pygame.Rect(233, 397, 64, 64),
    "next":     pygame.Rect(324, 397, 64, 64),
    "list":     pygame.Rect(530, 397, 64, 64),
    # "settings": pygame.Rect(531, 100, 64, 64),
    "info":     pygame.Rect(531, 100, 64, 64),
    "exit":     pygame.Rect(531, 20, 64, 64),
}
ICON_COLORS = {
    "prev": BLUE, "play": TEAL, "next": BLUE,
    "list": PURPLE, "settings": YELLOW,
    "info": WHITE, "exit": RED,
}

# --- logo ----------------------------------------------------

LOGO_VIEW = pygame.Rect(175, 45, 180, 180)
LOGO_PLACEHOLDER = "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"


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_rrect(size, top, bottom, radius):
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(h):
        pygame.draw.line(surf, _lerp(top, bottom, y / max(1, h - 1)), (0, y), (w, y))
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return surf


class Interface:
    def __init__(self, screen, font_path):
        self.screen = screen
        self._grad_cache = {}
        self.f_title = self._font(font_path, 30, bold=True)
        self.f_body = self._font(font_path, 22)
        self.f_small = self._font(font_path, 16)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _font(path, size, bold=False):
        try:
            f = pygame.font.Font(path, size)
        except (FileNotFoundError, OSError):
            f = pygame.font.Font(None, size + 6)   # fallback: pygame default
        f.set_bold(bold)
        return f

    def _grad(self, size, top, bottom, radius):
        key = (size, top, bottom, radius)
        if key not in self._grad_cache:
            self._grad_cache[key] = gradient_rrect(size, top, bottom, radius)
        return self._grad_cache[key]

    @staticmethod
    def _fit(font, text, max_w):
        if font.size(text)[0] <= max_w:
            return text
        while text and font.size(text + "…")[0] > max_w:
            text = text[:-1]
        return text + "…"

    def _text(self, font, text, pos, color=WHITE, center=False, max_w=None):
        if max_w:
            text = self._fit(font, text, max_w)
        img = font.render(text, True, color)
        rect = img.get_rect(center=pos) if center else img.get_rect(topleft=pos)
        self.screen.blit(img, rect)
        return rect

    # ------------------------------------------------------------------ icons
    def _icon(self, name, rect, color, playing=False):
        s, cx, cy = self.screen, rect.centerx, rect.centery
        d = pygame.draw
        if name == "prev":
            d.polygon(s, color, [(cx + 9, cy - 12), (cx + 9, cy + 12), (cx - 7, cy)])
            d.rect(s, color, (cx - 13, cy - 12, 4, 24), border_radius=2)
        elif name == "next":
            d.polygon(s, color, [(cx - 9, cy - 12), (cx - 9, cy + 12), (cx + 7, cy)])
            d.rect(s, color, (cx + 9, cy - 12, 4, 24), border_radius=2)
        elif name == "play":
            if playing:   # show pause glyph while playing
                d.rect(s, color, (cx - 11, cy - 12, 7, 24), border_radius=3)
                d.rect(s, color, (cx + 4, cy - 12, 7, 24), border_radius=3)
            else:
                d.polygon(s, color, [(cx - 8, cy - 13), (cx - 8, cy + 13), (cx + 13, cy)])
        elif name == "list":
            for i in (-1, 0, 1):
                y = cy + i * 10
                d.circle(s, color, (cx - 13, y), 2)
                d.line(s, color, (cx - 6, y), (cx + 14, y), 3)
        elif name == "settings":
            for i, kx in zip((-1, 0, 1), (-5, 6, -2)):
                y = cy + i * 10
                d.line(s, color, (cx - 14, y), (cx + 14, y), 2)
                d.circle(s, color, (cx + kx, y), 5, 3)
        elif name == "info":
                d.circle(s, color, (cx, cy - 16), 3, 3)
                d.line(s, color, (cx, cy - 8), (cx, cy + 12), 3)
                # d.line(s, color, (cx - 6, cy + 14), (cx + 6, cy + 14), 3)
        elif name == "exit":
            d.arc(s, color, pygame.Rect(cx - 11, cy - 10, 24, 24),
                math.radians(130), math.radians(410), 2)
            d.line(s, color, (cx, cy - 14), (cx, cy - 1), 3)

    def _button(self, name, focused, playing=False):
        r = BUTTONS[name]
        if focused:
            self.screen.blit(self._grad(r.size, BLUE_TOP, BLUE_BOT, 18), r)
            pygame.draw.rect(self.screen, (170, 205, 255), r, 2, border_radius=18)
            color = WHITE
        else:
            pygame.draw.rect(self.screen, PANEL, r, border_radius=18)
            pygame.draw.rect(self.screen, OUTLINE, r, 1, border_radius=18)
            color = ICON_COLORS[name]
        self._icon(name, r, color, playing)

    def _logo(self, logo):
        if logo:
            png_bytes = base64.b64decode(logo)
        else:
            png_bytes = base64.b64decode(LOGO_PLACEHOLDER)
        image = pygame.image.load(io.BytesIO(png_bytes)).convert_alpha()
        img_rect = image.get_rect(center=LOGO_VIEW.center)
        self.screen.blit(image, img_rect)

    # ------------------------------------------------------------ main window
    def draw_main(self, focus, status, channel_name, channel_logo, index, total):
        self.screen.fill(BG)
        # preview placeholder (MPV draws over this area while a stream is on)
        pygame.draw.rect(self.screen, (9, 13, 21), PREVIEW, border_radius=14)
        pygame.draw.rect(self.screen, OUTLINE, PREVIEW, 1, border_radius=14)
        c = PREVIEW.center
        labels = {
            "stopped": "Press Play to start",
            "playing": "Loading…",
            "paused": "Paused",
            "error": "Stream stopped unexpectedly",
            "empty": "No channels in channels.json",
        }

        self._logo(channel_logo)
        self._text(self.f_title, channel_name or "OnlineTV", (c[0], c[1] + 65),
                   WHITE, True, PREVIEW.w - 40)
        self._text(self.f_body, labels.get(status, ""), (c[0], c[1] + 110),
                   RED if status in ("error", "empty") else GRAY, True)
        if total:
            self._text(self.f_small, f"{index + 1} / {total}",
                       (c[0], PREVIEW.bottom - 24), MUTED, True)

        for name in BUTTONS:
            self._button(name, focus == name, playing=(status == "playing"))
        pygame.display.flip()

    # ----------------------------------------------------------- channel list
    ROW_H = 40
    ROW_TOP = 100

    def list_capacity(self):
        return (H - 40 - self.ROW_TOP) // self.ROW_H

    def draw_list(self, channels, selected, playing_index):
        self.screen.fill(BG)
        self._text(self.f_title, "Channels", (32, 20))
        self.screen.blit(self.f_small.render(f"{len(channels)} total", True, MUTED),
                         (W - 32 - self.f_small.size(f"{len(channels)} total")[0], 30))
        # table header
        self._text(self.f_small, "#", (52, 72), MUTED)
        self._text(self.f_small, "CHANNEL", (110, 72), MUTED)
        pygame.draw.line(self.screen, OUTLINE, (32, 94), (W - 32, 94), 1)

        cap = self.list_capacity()
        top = max(0, min(selected - cap // 2, len(channels) - cap))
        for row, i in enumerate(range(top, min(top + cap, len(channels)))):
            y = self.ROW_TOP + row * self.ROW_H
            rect = pygame.Rect(32, y, W - 64 - 14, self.ROW_H - 4)
            if i == selected:
                self.screen.blit(self._grad(rect.size, BLUE_TOP, BLUE_BOT, 12), rect)
                fg, num = WHITE, WHITE
            else:
                if row % 2 == 0:
                    pygame.draw.rect(self.screen, PANEL_ALT, rect, border_radius=12)
                fg, num = GRAY, MUTED
            img = self.f_body.render(str(i + 1), True, num)
            self.screen.blit(img, img.get_rect(midleft=(48, rect.centery)))
            img = self.f_body.render(self._fit(self.f_body, channels[i]["name"], 420), True, fg)
            self.screen.blit(img, img.get_rect(midleft=(110, rect.centery)))
            if i == playing_index:
                pygame.draw.circle(self.screen, TEAL, (rect.right - 20, rect.centery), 5)

        # scrollbar
        if len(channels) > cap:
            track = pygame.Rect(W - 40, self.ROW_TOP, 6, cap * self.ROW_H - 4)
            pygame.draw.rect(self.screen, PANEL, track, border_radius=3)
            th = max(24, int(track.h * cap / len(channels)))
            ty = track.y + int((track.h - th) * top / (len(channels) - cap))
            pygame.draw.rect(self.screen, BLUE, (track.x, ty, track.w, th), border_radius=3)

        self._hint("A  Play     B  Back     Left/Right  Page")
        pygame.display.flip()

    # --------------------------------------------------------------- info
    def draw_info(self, rows):
        self.screen.fill(BG)
        self._text(self.f_title, "Technical information", (32, 20))
        panel = pygame.Rect(32, 76, W - 64, H - 76 - 52)
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=18)
        pygame.draw.rect(self.screen, OUTLINE, panel, 1, border_radius=18)
        y = panel.y + 14
        for label, value in rows:
            self._text(self.f_small, label.upper(), (panel.x + 22, y + 5), MUTED)
            self._text(self.f_body, value, (panel.x + 190, y), WHITE, False,
                       panel.right - panel.x - 190 - 22)
            y += 33
        self._hint("B  Back")
        pygame.display.flip()

    def _hint(self, text):
        self._text(self.f_small, text, (W // 2, H - 24), MUTED, True)
