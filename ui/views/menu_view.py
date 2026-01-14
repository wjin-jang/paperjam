"""
Menu view rendering for settings and navigation menus.
"""
import math
import config as cfg
from ui.views.common import RenderBase
from ui.graphics import create_dithered_strip


class MenuViewRenderer(RenderBase):
    """Renderer for menu views."""

    def render_menu(self, title, items, sel_idx, scroll_idx):
        """Render a menu with title and items."""
        self.clear()

        box_w = 160
        full_content_h = (len(items) * cfg.ROW_HEIGHT) + cfg.ROW_HEIGHT
        box_h = min(cfg.PANEL_H, full_content_h)
        box_x = (cfg.SCREEN_WIDTH - box_w) // 2
        box_y = (cfg.SCREEN_HEIGHT - box_h) // 2

        self.draw_panel(box_x, box_y, box_w, box_h, header=title)

        list_y = box_y + cfg.ROW_HEIGHT
        avail_list_h = box_h - cfg.ROW_HEIGHT
        needs_scrollbar = len(items) * cfg.ROW_HEIGHT > avail_list_h
        item_draw_w = box_w

        limit = math.ceil(avail_list_h / cfg.ROW_HEIGHT)
        visible_items = items[scroll_idx: scroll_idx + limit]

        for i, item_obj in enumerate(visible_items):
            y_pos = list_y + (i * cfg.ROW_HEIGHT)
            remaining_h = (box_y + box_h) - y_pos
            if remaining_h <= 0:
                break
            draw_h = min(cfg.ROW_HEIGHT, remaining_h)

            is_selected = (sel_idx == scroll_idx + i)
            text = item_obj if isinstance(item_obj, str) else item_obj.get('name', str(item_obj))

            self.draw_text_box(text, box_x, y_pos, item_draw_w, draw_h, invert=is_selected, center=False)

        if needs_scrollbar:
            sb_h = avail_list_h
            self.canvas.paste(create_dithered_strip(8, sb_h), (box_x + box_w - 8, list_y))
            if len(items) > 0:
                handle_h = max(4, int(sb_h * (limit / len(items))))
                handle_y = list_y + int((sb_h - handle_h) * (scroll_idx / len(items)))
                self.draw.rectangle(
                    (box_x + box_w - 8, handle_y, box_x + box_w, handle_y + handle_h),
                    fill=cfg.WHITE, outline=cfg.BLACK
                )

        return self.canvas

    def render_volume(self, title, volume_level):
        """Render volume control view."""
        self.clear()

        panel_w = 160
        panel_h = cfg.ROW_HEIGHT * 2
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2

        self.draw_panel(x, y, panel_w, panel_h, header=f"{title} {int(volume_level)}%")
        self.draw_text_box('-', x, y + cfg.ROW_HEIGHT, cfg.ROW_HEIGHT, cfg.ROW_HEIGHT,
                          padding=(4, 0), font=cfg.FONT_HEADER)
        self.draw_text_box('+', x + panel_w - cfg.ROW_HEIGHT, y + cfg.ROW_HEIGHT,
                          cfg.ROW_HEIGHT, cfg.ROW_HEIGHT, padding=(4, 0), font=cfg.FONT_HEADER)

        # Draw volume bar fill
        bar_w = panel_w - (cfg.ROW_HEIGHT * 2)
        fill_w = int(bar_w * (volume_level / 100.0))
        bar_x = x + cfg.ROW_HEIGHT
        bar_y = y + cfg.ROW_HEIGHT
        bar_h = cfg.ROW_HEIGHT

        if fill_w > 0:
            self.draw.rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=cfg.BLACK)

        return self.canvas
