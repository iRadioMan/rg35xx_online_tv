"""Interface rendering (pygame.draw, screen blit, etc). No application logic here."""
import math
import os

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
    "next":     pygame.Rect(321, 397, 64, 64),
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

    def _logo(self):
        pygame.draw.rect(self.screen, WHITE, (175, 45, 180, 180))
        # TODO: draw channel logo

    # ------------------------------------------------------------ main window
    def draw_main(self, focus, status, channel_name, index, total):
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

        self._logo()
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
