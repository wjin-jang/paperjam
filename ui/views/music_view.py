"""
Music player view rendering.
"""
import math
from PIL import ImageOps
import config as cfg
from ui.views.common import RenderBase
from ui.graphics import create_dithered_strip, UI_ICONS
from core.metadata import sanitize_text


class MusicViewRenderer(RenderBase):
    """Renderer for music player view."""

    def render_header_icons(self, y_pos, state):
        """Render the header icon bar."""
        self.draw.rectangle(
            (cfg.PANEL_X, y_pos, cfg.PANEL_X + cfg.PANEL_W, y_pos + cfg.ROW_HEIGHT),
            fill=cfg.WHITE
        )
        btn_w = 33
        icon_keys = ['back', 'shuffle', 'loop', 'fav']

        for b_i, key in enumerate(icon_keys):
            bx = cfg.PANEL_X + (b_i * btn_w)
            is_active = False

            if key == 'shuffle' and state.shuffle_active:
                is_active = True
            if key == 'loop' and state.loop_mode > 0:
                is_active = True
            if key == 'fav' and state.album in state.fav_albums:
                is_active = True

            is_focused = (state.selection_index == state.view_start_index) and (state.top_bar_index == b_i)

            draw_inner_box = False
            icon_inverted = False

            if is_active:
                icon_inverted = True
                if is_focused:
                    draw_inner_box = True
            else:
                if is_focused:
                    icon_inverted = True

            icon = UI_ICONS[key]
            if icon_inverted:
                icon = ImageOps.invert(icon.convert('L')).convert('1')

            ix = bx + (btn_w - icon.width) // 2
            iy = y_pos + (12 - icon.height) // 2
            self.canvas.paste(icon, (ix, iy), mask=icon if not icon_inverted else None)

            if key == 'loop' and state.loop_mode == 2:
                txt_col = cfg.BLACK if not icon_inverted else cfg.WHITE
                self.draw.text((bx + 2, y_pos + 1), "1", font=cfg.FONT_MAIN, fill=txt_col)

            if draw_inner_box:
                self.draw.rectangle(
                    (bx + 2, y_pos + 2, bx + btn_w - 1, y_pos + cfg.ROW_HEIGHT - 1),
                    outline=cfg.WHITE
                )
            self.draw.rectangle(
                (bx + btn_w, y_pos, bx + btn_w + 8, y_pos + cfg.ROW_HEIGHT),
                outline=cfg.BLACK
            )

    def render_scrollbar(self, total, current, page_size, x, y, h):
        """Render scrollbar."""
        if total <= page_size:
            return

        self.canvas.paste(create_dithered_strip(9, h), (x, y))

        total_pages = math.ceil(total / page_size)
        current_page = current // page_size

        handle_h = max(6, int(h / total_pages))

        if total_pages > 1:
            pct = current_page / (total_pages - 1)
        else:
            pct = 0

        handle_y = y + int((h - handle_h) * pct)

        self.draw.rectangle(
            (x, handle_y, x + 8, handle_y + handle_h - 1),
            fill=cfg.WHITE, outline=cfg.BLACK
        )

    def render(self, state, view_items):
        """Render the full music view."""
        self.clear()

        # Album art
        art = state.playing_cover_s if (state.playing_path and state.is_playing) else state.browsing_cover_s
        art_size = 84
        art_x, art_y = 8, 8
        self.draw_panel(art_x, art_y, art_size, art_size)
        if art:
            self.canvas.paste(art, (art_x + 1, art_y + 1))
        else:
            self.draw_text_box("NO IMAGE", art_x + 1, art_y + 35, 82, 12, invert=True, center=True)

        # Status bar
        status_text = "¦ PLAYING" if state.is_playing else ("¥ PAUSED" if state.playing_path else "¤ IDLE")
        self.draw_panel(8, 100, art_size, cfg.ROW_HEIGHT)
        self.draw_text_box(
            status_text, 8, 100, art_size, cfg.ROW_HEIGHT,
            invert=False, padding=(0, 0), center=True, font=cfg.FONT_HEADER
        )

        # Main panel
        header_text = "Scanning..." if state.is_scanning else state.album
        self.draw_panel(cfg.PANEL_X, cfg.PANEL_Y, cfg.PANEL_W, cfg.PANEL_H, header=header_text)

        info_y = cfg.PANEL_Y + cfg.ROW_HEIGHT
        if state.artist:
            self.draw_text_box(state.artist, cfg.PANEL_X, info_y, 112, 12)
            self.draw_text_box(state.year, cfg.PANEL_X + 112, info_y, 28, 12, center=True)
            list_start_y = info_y + cfg.ROW_HEIGHT
        else:
            list_start_y = info_y

        avail_h = (cfg.PANEL_Y + cfg.PANEL_H) - list_start_y
        has_scrollbar = state.total_items * cfg.ROW_HEIGHT > avail_h
        item_w = 120 if has_scrollbar else 128

        for i, item in enumerate(view_items):
            y_pos = list_start_y + (i * cfg.ROW_HEIGHT)
            remaining_h = (cfg.PANEL_Y + cfg.PANEL_H) - y_pos
            if remaining_h <= 0:
                break
            draw_h = min(cfg.ROW_HEIGHT, remaining_h)

            abs_idx = state.view_start_index + i
            is_selected = (abs_idx == state.selection_index)

            if item.get('type') == 'header':
                self.render_header_icons(y_pos, state)
                continue

            # Determine icon
            if 'icon' in item and item.get('type') != 'file':
                icon_str = item['icon']
            else:
                itype = item.get('type')
                if itype == 'dir':
                    icon_str = "Ⓕ"
                elif itype == 'artist':
                    icon_str = "Ⓐ"
                elif itype == 'album':
                    icon_str = "Ⓑ"
                elif itype == 'recent':
                    icon_str = "Ⓡ"
                elif itype == 'playlist':
                    icon_str = "Ⓛ"
                    if "Fav" in item.get('name', ""):
                        icon_str = "Ⓗ"
                elif itype == 'file':
                    if 'icon' in item and item['icon'] == 'P':
                        icon_str = "Ⓟ"
                    else:
                        icon_str = f"{abs_idx}."
                else:
                    icon_str = item.get('icon', '★')

            self.draw_text_box(icon_str, cfg.PANEL_X, y_pos, 12, draw_h, invert=is_selected, center=True)
            name_str = sanitize_text(item.get('title', item.get('name', '')))
            self.draw_text_box(name_str, cfg.PANEL_X + 12, y_pos, item_w, draw_h, invert=is_selected)

        if has_scrollbar:
            self.render_scrollbar(
                state.total_items, state.selection_index, state.page_size,
                cfg.PANEL_X + cfg.PANEL_W - 8, list_start_y, avail_h + 1
            )

        # Context menu overlay
        if state.context_menu_active:
            self.render_context_menu(state)

        return self.canvas

    def render_context_menu(self, state):
        """Render context menu overlay."""
        w = 120
        max_h = 96
        item_h = cfg.ROW_HEIGHT
        header_h = cfg.ROW_HEIGHT
        padding = 4

        num_opts = len(state.context_options)
        needed_h = header_h + (num_opts * item_h) + padding
        menu_h = min(needed_h, max_h)

        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - menu_h) // 2

        self.draw_panel(x, y, w, menu_h, header="OPTIONS")

        list_y = y + header_h
        visible_count = (menu_h - header_h) // item_h

        start_idx = 0
        if state.context_index >= visible_count:
            start_idx = state.context_index - visible_count + 1

        for i in range(visible_count):
            idx = start_idx + i
            if idx >= num_opts:
                break

            opt = state.context_options[idx]
            opt_y = list_y + (i * item_h)
            is_sel = (idx == state.context_index)

            self.draw_text_box(opt, x, opt_y, w, item_h, invert=is_sel)
