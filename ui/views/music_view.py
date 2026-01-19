"""
Music player view rendering using Panel → Menu → Item hierarchy.
"""
from PIL import Image, ImageDraw
import config as cfg
from core.i18n import t
from ui.views.core import Panel, Menu
from ui.views.items import Item, Column
from ui.graphics import UI_ICONS
from core.metadata import sanitize_text


class MusicViewRenderer:
    """Renderer for music player view using the new Panel/Menu system."""

    def __init__(self):
        self.canvas = Image.new('1', (cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), cfg.WHITE)
        self.draw = ImageDraw.Draw(self.canvas)

    def clear(self):
        """Clear the canvas."""
        self.draw.rectangle((0, 0, cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), fill=cfg.WHITE)

    def _create_controls_item(self, state) -> Item:
        """Create controls bar as a ColumnItem.

        Args:
            state: Player state with shuffle_active, loop_mode, etc.

        Returns:
            Item with columns and column_nav=True
        """
        # Determine which icons to use
        icon_keys = ['back', 'shuffle', 'loop', 'fav']
        if state.browse_mode == 'QUEUE_VIEW':
            icon_keys = ['back', 'shuffle', 'loop', 'clear']

        columns = []
        for i, key in enumerate(icon_keys):
            icon = UI_ICONS.get(key, UI_ICONS.get('back'))
            active = False

            if key == 'shuffle' and state.shuffle_active:
                active = True
            elif key == 'loop' and state.loop_mode > 0:
                active = True
                if state.loop_mode == 2:
                    icon = UI_ICONS.get('loop_one', icon)
            elif key == 'fav':
                if state.browse_mode == 'ARTIST_VIEW':
                    if state.fav_artists and state.album in state.fav_artists:
                        active = True
                elif state.fav_albums and state.album in state.fav_albums:
                    active = True

            columns.append(Column(
                content=icon,
                width=None,  # Auto-calculate to fit available width
                align='center',
                active=active
            ))

        return Item(column_nav=True, columns=columns, selectable=True, pinned=True)

    def _convert_legacy_item(self, item: dict, state, display_idx: int = None):
        """Convert legacy item format to new Item classes.

        Args:
            item: Dict with flags like 'heading', 'column_nav', 'selectable'
            state: Player state for determining active items
            display_idx: Display index for track numbering

        Returns:
            Item instance
        """
        # Check for column_nav (controls bar)
        if item.get('column_nav'):
            return self._create_controls_item(state)

        # Check for heading
        if item.get('heading'):
            return Item(text=item.get('name', ''), heading=True, selectable=True, id=item.get('id'))

        # Check for non-selectable (info-style items)
        if not item.get('selectable', True):
            lines = item.get('lines')
            columns = item.get('columns')
            if lines:
                return Item(lines=lines, selectable=False)
            if columns:
                return Item(columns=columns, selectable=False)
            return Item(text=item.get('name', ''), selectable=False)

        # Icon+text items (file, album, artist, dir, playlist, recent)
        icon_str = self._get_item_icon(item, state, display_idx)
        name = sanitize_text(item.get('title', item.get('name', '')))

        pinned = item.get('pinned', False)
        return Item(text=name, icon=icon_str, selectable=True, pinned=pinned, id=item.get('id'))

    def _get_item_icon(self, item: dict, state, display_idx: int = None) -> str:
        """Get icon string for an item.

        Args:
            item: Item dict
            state: Player state
            display_idx: Display index for track numbering

        Returns:
            Icon string
        """
        # Get kind from id dict
        item_id = item.get('id', {})
        ikind = item_id.get('kind') if isinstance(item_id, dict) else None
        item_path = item_id.get('path') if isinstance(item_id, dict) else None
        icons = cfg.MENU_ICONS

        # Check if this is the currently playing item
        is_playing = state.is_playing
        current_icon = icons.get('playing', 'Ⓟ') if is_playing else icons.get('paused', 'Ⓢ')

        is_active = False
        if ikind == 'file' and state.playing_path:
            if str(item_path) == str(state.playing_path):
                is_active = True
        elif ikind == 'album' and state.playing_album:
            if item.get('name') == state.playing_album:
                is_active = True
        elif ikind == 'artist' and state.playing_artist:
            if item.get('name') == state.playing_artist:
                is_active = True

        if is_active:
            return current_icon

        # Use explicit icon if provided
        if 'icon' in item:
            icon = item['icon']
            if ikind == 'file' and icon == 'Ⓟ':
                # Stale playing icon
                track_num = item.get('track', 0)
                val = track_num if track_num else display_idx
                return f"{val}." if val else ""
            if ikind == 'file' and icon not in ('Ⓢ', ''):
                return icon if icon.endswith('.') else f"{icon}."
            return icon

        # Default icons by kind
        if ikind == 'file':
            track_num = item.get('track', 0)
            val = track_num if track_num else display_idx
            return f"{val}." if val else ""
        if ikind == 'dir':
            return icons.get('dir', 'Ⓕ')
        if ikind == 'artist':
            return icons.get('artist', 'Ⓐ')
        if ikind == 'album':
            return icons.get('album', 'Ⓑ')
        if ikind == 'recent':
            return icons.get('recent', 'Ⓡ')
        if ikind == 'playlist':
            if "Fav" in item.get('name', ''):
                return icons.get('fav', 'Ⓗ')
            return icons.get('playlist', 'Ⓛ')

        return item.get('icon', '')

    def render(self, state, view_items) -> tuple[Image.Image, int]:
        """Render the full music view.

        Args:
            state: PlayerState with all current state
            view_items: List of items to display (legacy format)

        Returns:
            Tuple of (Rendered canvas image, updated scroll offset)
        """
        self.clear()

        # === Album Art Panel ===
        art_size = 84
        art_x, art_y = 8, 8
        art_panel = Panel(art_x, art_y, art_size, art_size)
        art_menu = art_panel.create_menu()

        # Get appropriate cover art
        art = state.playing_cover_s if state.playing_path else state.browsing_cover_s
        # Create image item
        art_item = Item(show_image=True, image=art, placeholder=t('player.browse.no_image'))
        art_item.set_height(art_size)  # Account for border
        art_menu.items = [art_item]

        art_panel.render(self.canvas)

        # === Status Bar Panel ===
        status_x, status_y = 8, 100
        status_w, status_h = art_size, cfg.ROW_HEIGHT

        status_panel = Panel(status_x, status_y, status_w, status_h)
        status_menu = status_panel.create_menu()

        # Get status key and look up icon from STATUS_ICONS
        status_key = state.get_status_text()
        status_icon = cfg.STATUS_ICONS.get(status_key, '')
        status_text = f"{status_icon} {t(status_key)}" if status_icon else t(status_key)
        status_item = Item(text=status_text, font=cfg.FONT_HEADER, padding=(2, 0), selectable=False, sanitize=False)
        status_menu.items = [status_item]

        status_panel.render(self.canvas)

        # === Main Panel ===
        header_text = t('settings.library.scanning') if state.is_scanning else state.album
        main_panel = Panel(cfg.PANEL_X, cfg.PANEL_Y, cfg.PANEL_W, cfg.PANEL_H,
                          header=header_text)
        main_menu = main_panel.create_menu()
        main_menu.scroll_offset = state.scroll_offset

        # Separate pinned and scrollable items
        pinned_legacy = [item for item in view_items if item.get('pinned')]
        scrollable_legacy = [item for item in view_items if not item.get('pinned')]

        # Convert items
        menu_items = []
        track_offset = 0

        # Convert pinned items
        for item in pinned_legacy:
            menu_items.append(self._convert_legacy_item(item, state))

        # Convert scrollable items
        for i, item in enumerate(scrollable_legacy):
            is_heading = item.get('heading', False)
            is_controls = item.get('column_nav', False)
            is_info = not item.get('selectable', True)
            display_idx = None
            if not is_heading and not is_controls and not is_info:
                track_offset += 1
                display_idx = track_offset

            menu_items.append(self._convert_legacy_item(item, state, display_idx))

        main_menu.items = menu_items

        # Set cursor from state and auto-scroll to make it visible
        main_menu.cursor.row = state.cursor.row
        main_menu.cursor.col = state.cursor.col
        main_menu._ensure_visible()

        main_panel.render(self.canvas)

        # === Overlays ===
        if state.loading_message:
            self.render_loading(state.loading_message)
        elif state.context_menu_active:
            self.render_context_menu(state)

        return self.canvas, main_menu.scroll_offset

    def render_context_menu(self, state):
        """Render context menu overlay.

        Args:
            state: Player state with context_options and context_index
        """
        w = 120
        max_h = 96
        header_h = cfg.ROW_HEIGHT

        num_opts = len(state.context_options)
        needed_h = header_h + (num_opts * cfg.ROW_HEIGHT) + 4
        menu_h = min(needed_h, max_h)

        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - menu_h) // 2

        panel = Panel(x, y, w, menu_h, header=t('player.context.options'))
        menu = panel.create_menu()

        # Use context_options directly (already Item objects from context_menu.menu.items)
        menu.items = list(state.context_options)
        menu.cursor.row = state.context_index
        menu.cursor.col = 0

        panel.render(self.canvas)

    def render_loading(self, message: str):
        """Render loading overlay.

        Args:
            message: Loading message to display
        """
        w = 100
        h = cfg.ROW_HEIGHT

        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        panel = Panel(x, y, w, h)
        menu = panel.create_menu()
        menu.items = [Item(text=message, selectable=False)]

        panel.render(self.canvas)
