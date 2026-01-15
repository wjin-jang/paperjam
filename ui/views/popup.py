"""
Popup panel system for overlays and dialogs.

Provides a unified system for:
- Loading screens (programmatic dismissal)
- Volume control (timer-based dismissal)
- Confirmation dialogs (input-based dismissal)
- Context menus (input-based dismissal)
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
import time
from PIL import Image, ImageDraw
import config as cfg
from ui.views.common import Panel


class PopupTermination(Enum):
    """How a popup should terminate."""
    INPUT = auto()       # Wait for user input (confirm/cancel)
    PROGRAMMATIC = auto()  # Killed programmatically (loading screens)
    TIMER = auto()       # Auto-dismiss after timeout


@dataclass
class PopupConfig:
    """Configuration for a popup panel."""
    header: Optional[str] = None
    termination: PopupTermination = PopupTermination.INPUT
    timeout: float = 1.5
    width: int = 140
    min_height: int = 24
    max_height: int = 96
    centered: bool = True
    shadow: bool = True
    # For volume-style popups with custom rendering
    custom_render: Optional[Callable] = None


@dataclass
class PopupState:
    """Runtime state for an active popup."""
    config: PopupConfig
    content: List[Any]
    selection_index: int = 0
    created_at: float = field(default_factory=time.time)
    dismissed: bool = False
    result: Any = None
    # Extra data for custom rendering (e.g., volume level)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if timer-based popup has expired."""
        if self.config.termination != PopupTermination.TIMER:
            return False
        return (time.time() - self.created_at) >= self.config.timeout

    def reset_timer(self):
        """Reset the timer (for updating content while keeping popup alive)."""
        self.created_at = time.time()


class PopupPanel:
    """A popup overlay panel.

    Supports three termination modes:
    - INPUT: Waits for user to confirm or cancel
    - PROGRAMMATIC: Stays until explicitly dismissed
    - TIMER: Auto-dismisses after timeout
    """

    def __init__(self, config: PopupConfig):
        """Create a popup panel.

        Args:
            config: Popup configuration
        """
        self.config = config
        self.state: Optional[PopupState] = None
        self._callbacks: Dict[str, Callable] = {}

    def show(self, content: List[Any], initial_selection: int = 0,
             extra: Dict[str, Any] = None) -> 'PopupPanel':
        """Show the popup with given content.

        Args:
            content: List of items to display
            initial_selection: Initially selected index
            extra: Extra data for custom rendering

        Returns:
            Self for chaining
        """
        self.state = PopupState(
            config=self.config,
            content=content,
            selection_index=initial_selection,
            extra=extra or {}
        )
        return self

    def update(self, content: List[Any] = None, extra: Dict[str, Any] = None):
        """Update popup content and reset timer.

        Args:
            content: New content list (optional)
            extra: New extra data (optional)
        """
        if self.state:
            if content is not None:
                self.state.content = content
            if extra is not None:
                self.state.extra.update(extra)
            self.state.reset_timer()

    def dismiss(self, result: Any = None):
        """Dismiss the popup.

        Args:
            result: Result value to store
        """
        if self.state:
            self.state.dismissed = True
            self.state.result = result

    def is_active(self) -> bool:
        """Check if popup is still active."""
        if not self.state:
            return False
        if self.state.dismissed:
            return False
        if self.state.is_expired:
            return False
        return True

    def get_result(self) -> Any:
        """Get the result after popup is dismissed."""
        return self.state.result if self.state else None

    def get_callbacks(self) -> Dict[str, Callable]:
        """Get input callbacks for this popup.

        Returns:
            Dict of callback name -> function
        """
        if self.config.termination == PopupTermination.TIMER:
            return {}

        if self.config.termination == PopupTermination.PROGRAMMATIC:
            return {}

        return {
            'up': self._on_up,
            'down': self._on_down,
            'enter': self._on_enter,
            'back': self._on_back
        }

    def on_select(self, callback: Callable[[int, Any], None]) -> 'PopupPanel':
        """Set callback for selection confirmation.

        Args:
            callback: Function taking (index, item)

        Returns:
            Self for chaining
        """
        self._callbacks['on_select'] = callback
        return self

    def on_cancel(self, callback: Callable[[], None]) -> 'PopupPanel':
        """Set callback for cancellation.

        Args:
            callback: Function with no arguments

        Returns:
            Self for chaining
        """
        self._callbacks['on_cancel'] = callback
        return self

    def _on_up(self):
        """Handle up navigation."""
        if self.state and self.state.content:
            n = len(self.state.content)
            self.state.selection_index = (self.state.selection_index - 1) % n

    def _on_down(self):
        """Handle down navigation."""
        if self.state and self.state.content:
            n = len(self.state.content)
            self.state.selection_index = (self.state.selection_index + 1) % n

    def _on_enter(self):
        """Handle enter/confirm."""
        if self.state:
            cb = self._callbacks.get('on_select')
            if cb and self.state.content:
                item = self.state.content[self.state.selection_index]
                cb(self.state.selection_index, item)
            self.dismiss(self.state.selection_index)

    def _on_back(self):
        """Handle back/cancel."""
        cb = self._callbacks.get('on_cancel')
        if cb:
            cb()
        self.dismiss(None)

    def render(self, base_canvas: Image.Image) -> Image.Image:
        """Render popup onto base canvas.

        Args:
            base_canvas: Canvas to render onto

        Returns:
            Canvas with popup rendered
        """
        if not self.state:
            return base_canvas

        # Use custom renderer if provided
        if self.config.custom_render:
            return self.config.custom_render(base_canvas, self.state)

        # Calculate dimensions
        header_h = cfg.ROW_HEIGHT if self.config.header else 0
        content_h = len(self.state.content) * cfg.ROW_HEIGHT if self.state.content else cfg.ROW_HEIGHT
        total_h = header_h + content_h

        h = min(self.config.max_height, max(self.config.min_height, total_h))
        w = self.config.width

        if self.config.centered:
            x = (cfg.SCREEN_WIDTH - w) // 2
            y = (cfg.SCREEN_HEIGHT - h) // 2
        else:
            x = (cfg.SCREEN_WIDTH - w) // 2
            y = cfg.SCREEN_HEIGHT - h - 8

        # Create panel
        panel = Panel(x, y, w, h, header=self.config.header)

        # Render content items
        current_y = 0
        visible_h = h - header_h
        visible_count = visible_h // cfg.ROW_HEIGHT

        # Calculate scroll offset for long lists
        start_idx = 0
        if self.state.selection_index >= visible_count:
            start_idx = self.state.selection_index - visible_count + 1

        for i in range(visible_count):
            idx = start_idx + i
            if idx >= len(self.state.content or []):
                break

            item = self.state.content[idx]
            is_selected = (idx == self.state.selection_index)

            # Get text from item
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = item.get('name', str(item))
            else:
                text = str(item)

            panel.draw_text_box(text, 0, current_y, w, cfg.ROW_HEIGHT, invert=is_selected)
            current_y += cfg.ROW_HEIGHT

        # Composite onto base
        panel.composite(base_canvas, shadow=self.config.shadow)

        return base_canvas


class PopupManager:
    """Manages popup stack and input routing.

    Provides a central point for managing all popups in the application.
    Popups are stacked, with the topmost popup receiving input.
    """

    def __init__(self):
        """Create a popup manager."""
        self._stack: List[PopupPanel] = []

    def push(self, popup: PopupPanel) -> PopupPanel:
        """Push a popup onto the stack.

        Args:
            popup: Popup to add

        Returns:
            The popup for chaining
        """
        self._stack.append(popup)
        return popup

    def pop(self) -> Optional[PopupPanel]:
        """Pop the top popup.

        Returns:
            The removed popup, or None if stack was empty
        """
        if self._stack:
            return self._stack.pop()
        return None

    def peek(self) -> Optional[PopupPanel]:
        """Get the top popup without removing it.

        Returns:
            The top popup, or None if stack is empty
        """
        return self._stack[-1] if self._stack else None

    def clear(self):
        """Clear all popups."""
        self._stack.clear()

    def has_active_popup(self) -> bool:
        """Check if there's an active popup.

        Returns:
            True if at least one active popup exists
        """
        self._cleanup_expired()
        return bool(self._stack)

    def get_callbacks(self) -> Optional[Dict[str, Callable]]:
        """Get callbacks for active popup.

        Returns:
            Callback dict, or None if no popup or popup doesn't accept input
        """
        self._cleanup_expired()
        top = self.peek()
        if top and top.is_active():
            callbacks = top.get_callbacks()
            return callbacks if callbacks else None
        return None

    def render(self, base_canvas: Image.Image) -> Image.Image:
        """Render all active popups onto canvas.

        Args:
            base_canvas: Canvas to render onto

        Returns:
            Canvas with all popups rendered
        """
        self._cleanup_expired()
        for popup in self._stack:
            if popup.is_active():
                base_canvas = popup.render(base_canvas)
        return base_canvas

    def _cleanup_expired(self):
        """Remove expired popups from stack."""
        self._stack = [p for p in self._stack if p.is_active()]

    # Factory methods for common popup types

    def show_loading(self, message: str) -> PopupPanel:
        """Show a loading popup (programmatic dismissal).

        Args:
            message: Loading message to display

        Returns:
            The popup for later dismissal
        """
        config = PopupConfig(
            header=None,
            termination=PopupTermination.PROGRAMMATIC,
            width=120,
            min_height=cfg.ROW_HEIGHT + 8,
            shadow=True
        )
        popup = PopupPanel(config)
        popup.show([{'name': message}])
        return self.push(popup)

    def show_volume(self, title: str, level: int) -> PopupPanel:
        """Show volume popup (timer dismissal).

        Args:
            title: Title text (e.g., "VOLUME")
            level: Volume level (0-100)

        Returns:
            The popup for updating level
        """
        def render_volume(canvas: Image.Image, state: PopupState) -> Image.Image:
            vol = state.extra.get('level', 0)
            title_text = state.extra.get('title', 'VOLUME')

            panel_w = 160
            panel_h = cfg.ROW_HEIGHT * 2
            x = (cfg.SCREEN_WIDTH - panel_w) // 2
            y = (cfg.SCREEN_HEIGHT - panel_h) // 2

            draw = ImageDraw.Draw(canvas)

            # Draw shadow
            draw.rectangle(
                (x + 1, y + 1, x + panel_w + 1, y + panel_h + 1),
                outline=cfg.BLACK
            )
            # Draw panel border
            draw.rectangle(
                (x, y, x + panel_w, y + panel_h),
                fill=cfg.WHITE, outline=cfg.BLACK
            )
            # Draw header
            draw.rectangle(
                (x, y, x + panel_w, y + cfg.ROW_HEIGHT),
                fill=cfg.BLACK
            )
            draw.text(
                (x + 5, y),
                f"{title_text} {int(vol)}%",
                font=cfg.FONT_HEADER, fill=cfg.WHITE
            )

            # Draw +/- buttons
            btn_y = y + cfg.ROW_HEIGHT
            # Minus button
            draw.rectangle((x, btn_y, x + cfg.ROW_HEIGHT, btn_y + cfg.ROW_HEIGHT), outline=cfg.BLACK)
            draw.text((x + 4, btn_y), '-', font=cfg.FONT_HEADER, fill=cfg.BLACK)
            # Plus button
            plus_x = x + panel_w - cfg.ROW_HEIGHT
            draw.rectangle((plus_x, btn_y, plus_x + cfg.ROW_HEIGHT, btn_y + cfg.ROW_HEIGHT), outline=cfg.BLACK)
            draw.text((plus_x + 4, btn_y), '+', font=cfg.FONT_HEADER, fill=cfg.BLACK)

            # Draw volume bar
            bar_x = x + cfg.ROW_HEIGHT
            bar_w = panel_w - (cfg.ROW_HEIGHT * 2)
            fill_w = int(bar_w * (vol / 100.0))

            if fill_w > 0:
                draw.rectangle(
                    (bar_x, btn_y, bar_x + fill_w, btn_y + cfg.ROW_HEIGHT),
                    fill=cfg.BLACK
                )

            return canvas

        config = PopupConfig(
            header=None,
            termination=PopupTermination.TIMER,
            timeout=1.5,
            width=160,
            custom_render=render_volume
        )
        popup = PopupPanel(config)
        popup.show([], extra={'title': title, 'level': level})
        return self.push(popup)

    def show_confirm(self, title: str, options: List[str] = None,
                     default: int = 0) -> PopupPanel:
        """Show confirmation dialog (input dismissal).

        Args:
            title: Dialog title
            options: List of option strings (default: ["No", "Yes"])
            default: Default selected index

        Returns:
            The popup for setting callbacks
        """
        if options is None:
            options = ["No", "Yes"]

        config = PopupConfig(
            header=title,
            termination=PopupTermination.INPUT,
            width=140
        )
        popup = PopupPanel(config)
        popup.show(options, initial_selection=default)
        return self.push(popup)

    def show_context_menu(self, title: str, options: List[str]) -> PopupPanel:
        """Show context menu popup.

        Args:
            title: Menu title
            options: List of menu options

        Returns:
            The popup for setting callbacks
        """
        config = PopupConfig(
            header=title,
            termination=PopupTermination.INPUT,
            width=120,
            max_height=96
        )
        popup = PopupPanel(config)
        popup.show(options)
        return self.push(popup)

    def show_message(self, message: str, timeout: float = 1.5) -> PopupPanel:
        """Show a temporary message popup.

        Args:
            message: Message to display
            timeout: Auto-dismiss timeout

        Returns:
            The popup
        """
        config = PopupConfig(
            header=None,
            termination=PopupTermination.TIMER,
            timeout=timeout,
            width=140,
            min_height=cfg.ROW_HEIGHT + 8
        )
        popup = PopupPanel(config)
        popup.show([message])
        return self.push(popup)
