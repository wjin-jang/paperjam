"""
Asset manager for loading and managing UI icons and images.
Provides error handling and fallback for missing assets.
"""
from pathlib import Path
from typing import Dict, Optional
from PIL import Image, ImageDraw


class AssetManager:
    """
    Manages UI assets (icons, images) with proper error handling.

    Provides fallback images when assets are missing to prevent crashes.
    """

    def __init__(self, asset_dir: Optional[Path] = None):
        """
        Initialize asset manager.

        Args:
            asset_dir: Path to assets directory. Defaults to ./assets
        """
        if asset_dir is None:
            asset_dir = Path(__file__).parent.parent / "assets"
        self.asset_dir = Path(asset_dir)
        self._icons: Dict[str, Image.Image] = {}
        self._load_icons()

    def _create_fallback_icon(self, width: int = 12, height: int = 12) -> Image.Image:
        """Create a simple fallback icon when asset is missing."""
        img = Image.new('1', (width, height), 1)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, width - 1, height - 1), outline=0)
        draw.line((0, 0, width - 1, height - 1), fill=0)
        draw.line((0, height - 1, width - 1, 0), fill=0)
        return img

    def _create_clear_icon(self, width: int = 12, height: int = 12) -> Image.Image:
        """Create a clear/trash icon."""
        img = Image.new('1', (width, height), 1) # White background
        draw = ImageDraw.Draw(img)
        # Draw X
        draw.line((2, 2, width - 3, height - 3), fill=0, width=2)
        draw.line((2, height - 3, width - 3, 2), fill=0, width=2)
        return img

    def _load_icon(self, name: str, filename: str) -> Image.Image:
        """
        Load a single icon with error handling.

        Args:
            name: Icon identifier
            filename: Filename in assets directory

        Returns:
            Loaded image or fallback
        """
        path = self.asset_dir / filename
        try:
            if path.exists():
                return Image.open(path)
            else:
                print(f"Warning: Asset not found: {path}")
                return self._create_fallback_icon()
        except Exception as e:
            print(f"Error loading asset {filename}: {e}")
            return self._create_fallback_icon()

    def _load_icons(self):
        """Load all UI icons."""
        icon_files = {
            'back': 'back.png',
            'shuffle': 'shuffle.png',
            'loop': 'loop.png',
            'fav': 'heart.png',
            'clear': 'trash.png'
        }

        for name, filename in icon_files.items():
            self._icons[name] = self._load_icon(name, filename)

    def get_icon(self, name: str) -> Image.Image:
        """
        Get an icon by name.

        Args:
            name: Icon identifier

        Returns:
            Icon image or fallback if not found
        """
        if name in self._icons:
            return self._icons[name]
        return self._create_fallback_icon()

    @property
    def icons(self) -> Dict[str, Image.Image]:
        """Get all loaded icons."""
        return self._icons

    def reload(self):
        """Reload all icons from disk."""
        self._icons.clear()
        self._load_icons()


# Global asset manager instance for backward compatibility
_asset_manager: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    """Get or create the global asset manager instance."""
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = AssetManager()
    return _asset_manager


def get_ui_icons() -> Dict[str, Image.Image]:
    """Get UI icons dict for backward compatibility with existing code."""
    return get_asset_manager().icons
