import math
from PIL import Image, ImageDraw, ImageOps
import config as cfg
from ui.graphics import create_dithered_strip, UI_ICONS
from core.metadata import sanitize_text

class UIRenderer:
    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)
        
    def _draw_panel(self, x, y, w, h, header=None):
        self.draw.rectangle((x+1, y+1, x+w+1, y+h+1), outline=cfg.BLACK)
        self.draw.rectangle((x, y, x+w, y+h), fill=cfg.WHITE, outline=cfg.BLACK)
        if header:
            self.draw.rectangle((x, y, x+w, y+cfg.ROW_HEIGHT), fill=cfg.BLACK)
            self.draw.text((x+5, y), header, font=cfg.FONT_HEADER, fill=cfg.WHITE)

    def _draw_text_box(self, text, x, y, w, h, invert=False, padding=(5,3), center=False, font=cfg.FONT_MAIN):
        if h < 1: return
        bg = cfg.BLACK if invert else cfg.WHITE
        fg = cfg.WHITE if invert else cfg.BLACK
        text_layer = Image.new('1', (w+1, h+1), bg)
        text_draw = ImageDraw.Draw(text_layer)
        text_draw.rectangle((0, 0, w, h), outline=cfg.BLACK)
        if center:
            bbox = text_draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            draw_x = (w - text_w) // 2 + 1; draw_y = padding[1]
        else:
            draw_x = padding[0]; draw_y = padding[1]
        text_draw.text((draw_x, draw_y), text, font=font, fill=fg)
        self.canvas.paste(text_layer, (x, y))

    def render_volume(self, title, volume_level):
        self.clear()
        
        # Draw Main Panel
        panel_w = 160
        panel_h = cfg.ROW_HEIGHT * 2
        x = (cfg.SCREEN_WIDTH - panel_w) // 2
        y = (cfg.SCREEN_HEIGHT - panel_h) // 2
        
        self._draw_panel(x, y, panel_w, panel_h, header=f"{title} {int(volume_level)}%" )
        self._draw_text_box('-',x,y+cfg.ROW_HEIGHT,cfg.ROW_HEIGHT,cfg.ROW_HEIGHT,padding=(4,0),font=cfg.FONT_HEADER)
        self._draw_text_box('+',x+panel_w-cfg.ROW_HEIGHT,y+cfg.ROW_HEIGHT,cfg.ROW_HEIGHT,cfg.ROW_HEIGHT,padding=(4,0),font=cfg.FONT_HEADER)
        
        # Draw Fill
        bar_w = panel_w - (cfg.ROW_HEIGHT * 2)
        fill_w = int(bar_w * (volume_level / 100.0))
        bar_x = x + cfg.ROW_HEIGHT
        bar_y= y + cfg.ROW_HEIGHT
        bar_h = cfg.ROW_HEIGHT
        if fill_w > 0:
            self.draw.rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=cfg.BLACK)
        
        return self.canvas

    def _render_header_icons(self, y_pos, state):
        self.draw.rectangle((cfg.PANEL_X, y_pos, cfg.PANEL_X + cfg.PANEL_W, y_pos + cfg.ROW_HEIGHT), fill=cfg.WHITE)
        btn_w = 33 
        icon_keys = ['back', 'shuffle', 'loop', 'fav']
        for b_i, key in enumerate(icon_keys):
            bx = cfg.PANEL_X + (b_i * btn_w)
            is_active = False
            if key == 'shuffle' and state.shuffle_active: is_active = True
            if key == 'loop' and state.loop_mode > 0: is_active = True
            if key == 'fav' and state.album in state.fav_albums: is_active = True
            is_focused = (state.selection_index == state.view_start_index) and (state.top_bar_index == b_i)
            
            draw_inner_box = False;
            icon_inverted = False;
            
            if is_active:
                icon_inverted = True
                if is_focused: draw_inner_box = True
            else:
                if is_focused: icon_inverted = True
                else: icon_inverted = False
            icon = UI_ICONS[key]
            if icon_inverted: icon = ImageOps.invert(icon.convert('L')).convert('1')
            ix = bx + (btn_w - icon.width)//2; iy = y_pos + (12 - icon.height)//2
            self.canvas.paste(icon, (ix, iy), mask=icon if not icon_inverted else None)
            if key == 'loop' and state.loop_mode == 2:
                txt_col = cfg.BLACK if fill_c == cfg.WHITE else cfg.WHITE
                self.draw.text((bx+2, y_pos+1), "1", font=cfg.FONT_MAIN, fill=txt_col)
            if draw_inner_box: self.draw.rectangle((bx+2, y_pos+2, bx+btn_w-1, y_pos+cfg.ROW_HEIGHT-1), outline=cfg.WHITE)
            self.draw.rectangle((bx+btn_w, y_pos, bx+btn_w+8, y_pos+cfg.ROW_HEIGHT), outline=cfg.BLACK)
            
    def _render_scrollbar(self, total, current, page_size, x, y, h):
        if total <= page_size: return
        self.canvas.paste(create_dithered_strip(9, h), (x, y))
        
        total_pages = math.ceil(total / page_size)
        current_page = current // page_size
        
        handle_h = max(6, int(h / total_pages))
        
        if total_pages > 1:
            pct = current_page / (total_pages - 1)
        else:
            pct = 0
            
        handle_y = y + int((h - handle_h) * pct)
        
        self.draw.rectangle((x, handle_y, x+8, handle_y+handle_h-1), fill=cfg.WHITE, outline=cfg.BLACK)

    def render_context_menu(self, state):
        """Draws the popup menu over the current state."""
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
        
        # Draw Menu Panel
        self._draw_panel(x, y, w, menu_h, header="OPTIONS")
        
        list_y = y + header_h
        visible_count = (menu_h - header_h) // item_h
        
        # Scrolling logic for context menu
        start_idx = 0
        if state.context_index >= visible_count:
            start_idx = state.context_index - visible_count + 1
            
        for i in range(visible_count):
            idx = start_idx + i
            if idx >= num_opts: break
            
            opt = state.context_options[idx]
            opt_y = list_y + (i * item_h)
            is_sel = (idx == state.context_index)
            
            self._draw_text_box(opt, x, opt_y, w, item_h, invert=is_sel)
            
        return self.canvas

    def render_screensaver(self, state):
        self.clear()
        img = state.screensaver_image
        if not img:
            self._draw_text_box("IDLE", 0, 73, 104, 20, center=True, font=cfg.FONT_HEADER)
        else:
            x = (cfg.SCREEN_WIDTH - img.width + 1) // 2
            y = (cfg.SCREEN_HEIGHT - img.height + 1) // 2
            self._draw_panel(x-1, y-1, img.width + 1, img.height + 1)
            self.canvas.paste(img, (x, y))
            
            if not state.is_playing:
                # Draw square panel
                pw, ph = cfg.ROW_HEIGHT, cfg.ROW_HEIGHT
                px = x + img.width + 8
                py = y + img.height - ph
                
                self._draw_panel(px,py,pw,ph)
                
                self._draw_text_box("¥", px, py, pw, ph, invert=False, padding=(2,0), font=cfg.FONT_HEADER)

        return self.canvas

    def render_music_view(self, state, view_items):
        self.clear()
        
        art = state.playing_cover_s if (state.playing_path and state.is_playing) else state.browsing_cover_s
        art_size = 84; art_x, art_y = 8, 8
        self._draw_panel(art_x, art_y, art_size, art_size)
        if art: self.canvas.paste(art, (art_x+1, art_y+1))
        else: self._draw_text_box("NO IMAGE", art_x+1, art_y+35, 82, 12, invert=True, center=True)

        status_text = "¦ PLAYING" if state.is_playing else ("¥ PAUSED" if state.playing_path else "¤ IDLE")
        self._draw_panel(8, 100, art_size, cfg.ROW_HEIGHT)
        self._draw_text_box(status_text, 8, 100, art_size, cfg.ROW_HEIGHT, invert=False, padding=(0,0), center=True, font=cfg.FONT_HEADER)

        header_text = "Scanning..." if state.is_scanning else state.album
        self._draw_panel(cfg.PANEL_X, cfg.PANEL_Y, cfg.PANEL_W, cfg.PANEL_H, header=header_text)

        info_y = cfg.PANEL_Y + cfg.ROW_HEIGHT
        if state.artist:
            self._draw_text_box(state.artist, cfg.PANEL_X, info_y, 112, 12)
            self._draw_text_box(state.year, cfg.PANEL_X + 112, info_y, 28, 12, center=True)
            list_start_y = info_y + cfg.ROW_HEIGHT
        else:
            list_start_y = info_y

        avail_h = (cfg.PANEL_Y + cfg.PANEL_H) - list_start_y
        has_scrollbar = state.total_items * cfg.ROW_HEIGHT > avail_h
        item_w = 120 if has_scrollbar else 128

        for i, item in enumerate(view_items):
            y_pos = list_start_y + (i * cfg.ROW_HEIGHT)
            remaining_h = (cfg.PANEL_Y + cfg.PANEL_H) - y_pos
            if remaining_h <= 0: break
            draw_h = min(cfg.ROW_HEIGHT, remaining_h)

            abs_idx = state.view_start_index + i
            is_selected = (abs_idx == state.selection_index)

            if item.get('type') == 'header':
                self._render_header_icons(y_pos, state)
                continue
            
            # Default
            if 'icon' in item and item.get('type') != 'file':
                icon_str = item['icon']
            else:
                # 2. Fallback to Type logic
                itype = item.get('type')
                
                if itype == 'dir': icon_str = "Ⓕ"
                elif itype == 'artist': icon_str = "Ⓐ"
                elif itype == 'album': icon_str = "Ⓑ"
                elif itype == 'recent': icon_str = "Ⓡ"
                elif itype == 'playlist': 
                    icon_str = "Ⓛ" 
                    if "Fav" in item.get('name', ""): icon_str = "Ⓗ"
                elif itype == 'file':
                     # Numbered Logic
                     if 'icon' in item and item['icon'] == 'P': icon_str = "Ⓟ"
                     else: icon_str = f"{abs_idx}."
                else:
                    icon_str = item.get('icon', '★')

            self._draw_text_box(icon_str, cfg.PANEL_X, y_pos, 12, draw_h, invert=is_selected, center=True)
            name_str = sanitize_text(item.get('title', item.get('name', '')))
            self._draw_text_box(name_str, cfg.PANEL_X+12, y_pos, item_w, draw_h, invert=is_selected)

        if has_scrollbar:
            self._render_scrollbar(state.total_items, state.selection_index, state.page_size, 
                                  cfg.PANEL_X + cfg.PANEL_W - 8, list_start_y, avail_h + 1)
        
        # --- Context Menu Overlay ---
        if state.context_menu_active:
            self.render_context_menu(state)
            
        return self.canvas
    
    def render_menu(self, title, items, sel_idx, scroll_idx):
        self.clear()
        box_w = 160
        full_content_h = (len(items) * cfg.ROW_HEIGHT) + cfg.ROW_HEIGHT
        box_h = min(cfg.PANEL_H, full_content_h)
        box_x = (cfg.SCREEN_WIDTH - box_w) // 2
        box_y = (cfg.SCREEN_HEIGHT - box_h) // 2
        
        self._draw_panel(box_x, box_y, box_w, box_h, header=title)
        
        list_y = box_y + cfg.ROW_HEIGHT
        avail_list_h = box_h - cfg.ROW_HEIGHT
        needs_scrollbar = len(items) * cfg.ROW_HEIGHT > avail_list_h
        item_draw_w = box_w if not needs_scrollbar else box_w
        
        limit = math.ceil(avail_list_h / cfg.ROW_HEIGHT)
        visible_items = items[scroll_idx : scroll_idx + limit]
        
        for i, item_obj in enumerate(visible_items):
            y_pos = list_y + (i * cfg.ROW_HEIGHT)
            remaining_h = (box_y + box_h) - y_pos
            if remaining_h <= 0: break
            draw_h = min(cfg.ROW_HEIGHT, remaining_h)
            
            is_selected = (sel_idx == scroll_idx + i)
            text = item_obj if isinstance(item_obj, str) else item_obj.get('name', str(item_obj))
            
            self._draw_text_box(text, box_x, y_pos, item_draw_w, draw_h, invert=is_selected, center=False)
            
        if needs_scrollbar:
            from ui.graphics import create_dithered_strip
            sb_h = avail_list_h
            self.canvas.paste(create_dithered_strip(8, sb_h), (box_x + box_w - 8, list_y))
            if len(items) > 0:
                handle_h = max(4, int(sb_h * (limit / len(items))))
                handle_y = list_y + int((sb_h - handle_h) * (scroll_idx / len(items)))
                self.draw.rectangle((box_x + box_w - 8, handle_y, box_x + box_w, handle_y + handle_h), fill=cfg.WHITE, outline=cfg.BLACK)

        return self.canvas

    def render_shutdown(self, image=None):
        self.clear()
        
        # 1. Draw Background Image (Random Cover)
        if image:
            # Center the image
            x = (cfg.SCREEN_WIDTH - image.width) // 2
            y = (cfg.SCREEN_HEIGHT - image.height) // 2
            
            # Draw a border panel for the image
            self._draw_panel(x-1, y-1, image.width + 1, image.height + 1)
            self.canvas.paste(image, (x, y))
        
        # 2. Draw "power off" text
        text = "power off"
        font = cfg.FONT_MAIN
        
        # Calculate text size
        bbox = self.draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        x = cfg.SCREEN_WIDTH - w - 8
        y = cfg.SCREEN_HEIGHT - h - 8
        
        # Draw a small white backing box (with outline) so text is always readable
        # extending slightly beyond text bounds
        self.draw.rectangle((x-3, y-1, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)
        self.draw.text((x, y), text, font=font, fill=cfg.BLACK)
        
        return self.canvas
