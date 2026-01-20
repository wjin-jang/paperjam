from ui.views.core import Panel, Menu
from ui.views.items import Item
import config as cfg
import time
from dataclasses import dataclass, field
from typing import Dict, Callable, Optional, List, Any
from PIL import Image
from core.i18n import t


class PopupPanel(Panel):
    """
    Specialized panel for popups.
    """
    def __init__(self, x, y, w, h, title=None, dismiss_mode='INPUT', timeout=cfg.POPUP_DEFAULT_TIMEOUT):
        super().__init__(x, y, w, h, header=title)
        self.dismiss_mode = dismiss_mode
        self.timeout = timeout
        self.start_time = 0
        self.created_time = 0
        self.menu = None
        self.state = None # Optional state object

    def create_menu(self):
        return super().create_menu()

    def update(self, items=None, extra=None):
        """Update popup content."""
        if items:
            self.menu.items = items
        if extra:
            # Update state if exists
            if self.state:
                self.state.extra.update(extra)
                # Rebuild items if needed (e.g. volume)
                if self.state.extra.get('is_volume'):
                    level = self.state.extra.get('level', 0)
                    title = self.state.extra.get('title', "VOLUME")
                    self.header = f"{title} {level}%"
                    self.menu.items = [Item(show_volume=True, value=level)]


@dataclass
class PopupState:
    """State for an active popup."""
    panel: PopupPanel
    callbacks: Dict[str, Callable]
    on_close: Optional[Callable]
    extra: Dict[str, Any] = field(default_factory=dict)


class PopupManager:
    """Manages the stack of active popups."""

    def __init__(self):
        """Create a popup manager."""
        self._stack: List[PopupState] = []
        self._refresh_needed = False

    def push(self, panel: PopupPanel, callbacks: Dict[str, Callable] = None, on_close: Callable = None):
        """Push a new popup onto the stack."""
        state = PopupState(panel, callbacks or {}, on_close)
        panel.state = state
        panel.created_time = time.time()
        
        # If TIMER mode, start the timer
        if panel.dismiss_mode == 'TIMER':
            panel.start_time = time.time()
            
        self._stack.append(state)

    def pop(self):
        """Remove the top popup."""
        if self._stack:
            state = self._stack.pop()
            if state.on_close:
                state.on_close()
            self._refresh_needed = True

    def peek(self) -> Optional[PopupPanel]:
        """Get the active popup panel."""
        if self._stack:
            return self._stack[-1].panel
        return None

    def render(self, frame: Image.Image) -> Image.Image:
        """Render active popups onto the frame."""
        if not self._stack:
            return frame

        # Check timeouts
        now = time.time()
        active = self._stack[-1]
        panel = active.panel
        
        if panel.dismiss_mode == 'TIMER' and (now - panel.start_time > panel.timeout):
            self.pop()
            # If stack empty, return frame (cleared), else recurse/loop?
            # For simplicity, just return frame, next loop will render next popup or base
            return frame

        # Render top popup
        # Create a temp canvas or draw directly?
        # Drawing directly onto the frame is fine
        # We need to use the panel's render method but redirect it to our frame
        # Panel.render takes a canvas and pastes onto it.
        panel.render(frame)
        
        return frame

    def get_callbacks(self) -> Optional[Dict[str, Callable]]:
        """Get callbacks for the active popup."""
        if self._stack:
            # If INPUT mode, return callbacks (which might be empty -> blocks input)
            # If TIMER or PROGRAMMATIC, usually we might want to block input or allow pass-through?
            # Existing logic implies popups capture input.
            
            # Default close on 'back' or 'enter' if not specified for INPUT mode?
            callbacks = self._stack[-1].callbacks.copy()
            
            # Auto-dismiss handlers
            if self._stack[-1].panel.dismiss_mode == 'INPUT':
                if 'back' not in callbacks:
                    callbacks['back'] = self.pop
                if 'enter' not in callbacks:
                    callbacks['enter'] = self.pop
            
            return callbacks
        return None

    def has_active_popup(self) -> bool:
        return len(self._stack) > 0

    def consume_refresh_flag(self) -> bool:
        if self._refresh_needed:
            self._refresh_needed = False
            return True
        return False

    # --- Factory Methods ---

    def show_message(self, title, text, timeout=cfg.POPUP_DEFAULT_TIMEOUT):
        """Show a temporary message popup."""
        w = cfg.MESSAGE_POPUP_WIDTH
        # Estimate height based on line count
        lines = len(text.split('\n'))
        h = (lines * cfg.ROW_HEIGHT) + cfg.ROW_HEIGHT
        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        panel = PopupPanel(x, y, w, h, title=title, dismiss_mode='TIMER', timeout=timeout)
        menu = panel.create_menu()
        
        # Convert content to Items
        # Handle multi-line
        if '\n' in text:
            menu.items = [Item(text=line, selectable=False) for line in text.split('\n')]
        else:
            menu.items = [Item(text=text, selectable=False)]
            
        self.push(panel)

    def show_confirm(self, title, on_yes, on_no=None):
        """Show a confirmation dialog."""
        w = cfg.CONFIRM_POPUP_WIDTH
        h = cfg.CONFIRM_POPUP_HEIGHT
        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        panel = PopupPanel(x, y, w, h, title=title, dismiss_mode='INPUT')
        menu = panel.create_menu()
        
        menu.items = [
            Item(text=t('general.no'), selectable=True),
            Item(text=t('general.yes'), selectable=True)
        ]
        menu.cursor.row = 0
        
        def handle_enter():
            idx = menu.cursor.row
            self.pop()
            if idx == 1:
                on_yes()
            elif on_no:
                on_no()
                
        def handle_up():
            menu.cursor.row = (menu.cursor.row - 1) % 2
            
        def handle_down():
            menu.cursor.row = (menu.cursor.row + 1) % 2

        callbacks = {
            'enter': handle_enter,
            'up': handle_up,
            'down': handle_down,
            'back': lambda: (self.pop(), on_no() if on_no else None)
        }
        
        self.push(panel, callbacks)

    def show_loading(self, title=None):
        """Show a loading spinner/text (programmatic dismiss)."""
        w = cfg.LOADING_POPUP_WIDTH
        h = cfg.LOADING_POPUP_HEIGHT
        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        panel = PopupPanel(x, y, w, h, title=title or t('general.loading'), dismiss_mode='PROGRAMMATIC')
        # No menu items needed really, or just static text
        self.push(panel)
        return panel # Return handle to close

    def show_volume(self, title, level):
        """Show volume overlay."""
        w = cfg.MENU_PANEL_WIDTH
        h = cfg.ROW_HEIGHT * 2
        x = (cfg.SCREEN_WIDTH - w) // 2
        y = (cfg.SCREEN_HEIGHT - h) // 2

        header = f"{title} {int(level)}%"
        panel = PopupPanel(x, y, w, h, title=header, dismiss_mode='TIMER', timeout=cfg.VOLUME_POPUP_TIMEOUT)
        menu = panel.create_menu()
        menu.items = [Item(show_volume=True, value=level)]
        
        # Override standard volume rendering update logic
        panel.state = None # Will be set in push
        
        self.push(panel)
        return panel