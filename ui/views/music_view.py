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

    def render_controls(self, y_pos, w, state, is_selected):
        """Render the controls bar with icons.

        Args:
            y_pos: Y position to render at
            w: Width of the controls bar
            state: Player state
            is_selected: Whether this item is currently selected
        """
        self.draw.rectangle(
            (cfg.PANEL_X, y_pos, cfg.PANEL_X + w, y_pos + cfg.ROW_HEIGHT),
            fill=cfg.WHITE,
            outline=cfg.BLACK
        )
        btn_w = w // 4
        icon_keys = ['back', 'shuffle', 'loop', 'fav']

        for b_i, key in enumerate(icon_keys):
            bx = cfg.PANEL_X + (b_i * btn_w)
            is_active = False

            if key == 'shuffle' and state.shuffle_active:
                is_active = True
            if key == 'loop' and state.loop_mode > 0:
                is_active = True
            if key == 'fav':
                if state.browse_mode == 'ARTIST_VIEW' and state.fav_artists and state.album in state.fav_artists:
                    is_active = True
                elif state.fav_albums and state.album in state.fav_albums:
                    is_active = True

            # Button is focused when controls bar is selected AND this button is active
            is_focused = is_selected and (state.controls_index == b_i)

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

            self.draw.rectangle(
                (bx, y_pos, bx + btn_w, y_pos + cfg.ROW_HEIGHT),
                fill=cfg.BLACK if icon_inverted else cfg.WHITE  
            )

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
            # Draw separator between buttons (except last)
            if b_i < 3:
                self.draw.line(
                    (bx + btn_w, y_pos + 2, bx + btn_w, y_pos + cfg.ROW_HEIGHT - 2),
                    fill=cfg.BLACK
                )

    def _render_info_columns(self, item, x, y, w, h):
        """Render an info item with multiple columns.

        Columns are sized to fit their content, with the first column
        taking remaining space. Right columns are right-aligned.
        """
        columns = item.get('columns', [])
        if not columns:
            # Single text info item
            name_str = sanitize_text(item.get('name', ''))
            self.draw_text_box(name_str, x, y, w, h)
            return

        # Calculate width needed for each right column (all except first)
        right_widths = []
        for col_text in columns[1:]:
            text = sanitize_text(str(col_text))
            # ~6px per char + padding, minimum 20px
            col_w = max(20, len(text) * 6 + 8)
            right_widths.append(col_w)

        # First column gets remaining space
        total_right = sum(right_widths)
        left_w = w - total_right

        # Render first column (left-aligned)
        self.draw_text_box(sanitize_text(str(columns[0])), x, y, left_w, h)

        # Render right columns
        col_x = x + left_w
        for i, col_text in enumerate(columns[1:]):
            col_w = right_widths[i]
            self.draw_text_box(sanitize_text(str(col_text)), col_x, y, col_w, h, center=True)
            col_x += col_w

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

        # Album art - show playing cover if track is loaded (playing or paused)
        art = state.playing_cover_s if state.playing_path else state.browsing_cover_s
        art_size = 84
        art_x, art_y = 8, 8
        self.draw_panel(art_x, art_y, art_size, art_size)
        if art:
            self.canvas.paste(art, (art_x + 1, art_y + 1))
        else:
            self.draw_text_box("NO IMAGE", art_x + 1, art_y + 35, 82, 12, invert=True, center=True)

        # Status bar - use state's status text method for temporary messages
        raw_status = state.get_status_text()
        icon = cfg.STATUS_ICONS.get(raw_status, 'Ⓘ')
        status_text = f"{icon} {raw_status}"
        self.draw_panel(8, 100, art_size, cfg.ROW_HEIGHT)
        self.draw_text_box(
            status_text, 8, 100, art_size, cfg.ROW_HEIGHT,
            invert=False, padding=(0, 0), center=True, font=cfg.FONT_HEADER
        )

        # Main panel
        header_text = "Scanning..." if state.is_scanning else state.album
        self.draw_panel(cfg.PANEL_X, cfg.PANEL_Y, cfg.PANEL_W, cfg.PANEL_H, header=header_text)

        list_start_y = cfg.PANEL_Y + cfg.ROW_HEIGHT

        # Separate pinned and scrollable items
        pinned_items = [item for item in view_items if item.get('pinned')]
        scrollable_items = [item for item in view_items if not item.get('pinned')]

        pinned_count = len(pinned_items)

        # Render pinned info items (always visible at top)
        for item in pinned_items:
            self._render_info_columns(item, cfg.PANEL_X, list_start_y, cfg.PANEL_W, cfg.ROW_HEIGHT)
            list_start_y += cfg.ROW_HEIGHT

        avail_h = (cfg.PANEL_Y + cfg.PANEL_H) - list_start_y
        # Scrollbar based on scrollable items only
        scrollable_total = state.total_items - pinned_count
        has_scrollbar = scrollable_total * cfg.ROW_HEIGHT > avail_h
        item_w = cfg.PANEL_W - 16 if has_scrollbar else cfg.PANEL_W - 8

        for i, item in enumerate(scrollable_items):
            y_pos = list_start_y + (i * cfg.ROW_HEIGHT)
            remaining_h = (cfg.PANEL_Y + cfg.PANEL_H) - y_pos
            if remaining_h <= 0:
                break
            draw_h = min(cfg.ROW_HEIGHT, remaining_h)

            # Index accounts for pinned + scroll position
            abs_idx = state.view_start_index + i + pinned_count
            is_selected = (abs_idx == state.selection_index)

            itype = item.get('type')

            # Controls bar - scrollable row with icons
            if itype == 'controls':
                self.render_controls(y_pos, item_w + 8, state, is_selected)
                continue

            # Info items - non-selectable, can have columns
            if itype == 'info':
                self._render_info_columns(item, cfg.PANEL_X, y_pos, item_w + 8, draw_h)
                continue

            # Heading items - uppercase, white on black, inner box when selected
            if itype == 'heading':
                name_str = sanitize_text(item.get('name', '')).upper()
                # Draw black background
                self.draw.rectangle(
                    (cfg.PANEL_X, y_pos, cfg.PANEL_X + item_w + 8, y_pos + draw_h - 1),
                    fill=cfg.BLACK
                )
                # Draw white text
                self.draw_text_box(name_str, cfg.PANEL_X, y_pos, item_w + 8, draw_h,
                                   invert=True, center=False, font=cfg.FONT_MAIN)
                # Draw inner box when selected
                if is_selected:
                    self.draw.rectangle(
                        (cfg.PANEL_X + 2, y_pos + 2, cfg.PANEL_X + item_w + 6, y_pos + draw_h - 2),
                        outline=cfg.WHITE
                    )
                continue

            # Determine icon for other item types
            icons = cfg.MENU_ICONS
            if 'icon' in item and itype != 'file':
                icon_str = item['icon']
            else:
                if itype == 'dir':
                    icon_str = icons.get('dir', 'Ⓕ')
                elif itype == 'artist':
                    icon_str = icons.get('artist', 'Ⓐ')
                elif itype == 'album':
                    icon_str = icons.get('album', 'Ⓑ')
                elif itype == 'recent':
                    icon_str = icons.get('recent', 'Ⓡ')
                elif itype == 'playlist':
                    icon_str = icons.get('playlist', 'Ⓛ')
                    if "Fav" in item.get('name', ""):
                        icon_str = icons.get('fav', 'Ⓗ')
                elif itype == 'file':
                    if 'icon' in item and item['icon'] == 'P':
                        icon_str = icons.get('playing', 'Ⓟ')
                    else:
                        # Use track number if available, otherwise use index
                        track_num = item.get('track', 0)
                        icon_str = f"{track_num}." if track_num else f"{abs_idx}."
                else:
                    icon_str = item.get('icon', '★')

            self.draw_text_box(icon_str, cfg.PANEL_X, y_pos, 12, draw_h, invert=is_selected, center=True)
            name_str = sanitize_text(item.get('title', item.get('name', '')))
            self.draw_text_box(name_str, cfg.PANEL_X + 12, y_pos, item_w - 4, draw_h, invert=is_selected)

        if has_scrollbar:
            # Adjust scrollbar for pinned items
            adjusted_selection = max(0, state.selection_index - pinned_count)
            self.render_scrollbar(
                scrollable_total, adjusted_selection, state.page_size,
                cfg.PANEL_X + cfg.PANEL_W - 8, list_start_y, avail_h + 1
            )

        # Loading overlay
        if state.loading_message:
            self.render_loading(state.loading_message)
        # Context menu overlay
        elif state.context_menu_active:
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

    def render_loading(self, message: str):
        """Render loading overlay."""
        w = 100
        h = cfg.ROW_HEIGHT + 8

        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        self.draw_panel(x, y, w, h)
        self.draw_text_box(message, x, y, w, h, center=True, font=cfg.FONT_HEADER)
