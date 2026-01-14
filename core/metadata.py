import os, io
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from PIL import Image
from ui.graphics import dither_image

try:
    from korean_romanizer.romanizer import Romanizer
    import pykakasi
    HAS_ROMANIZER = True
    kks = pykakasi.kakasi()
except ImportError:
    HAS_ROMANIZER = False

def sanitize_text(text):
    if not text: return ""
    if HAS_ROMANIZER:
        try:
            text = Romanizer(text).romanize()
            text = ''.join([item['hepburn'] for item in kks.convert(text)])
        except: pass 
    return text.encode('ascii', 'ignore').decode().strip()

def format_track_name(file_path):
    name = file_path.stem
    parts = name.split(' ', 1)
    if len(parts) > 1 and parts[0].replace('.', '').isdigit():
        return parts[1]
    return name

def clean_tag(text):
    if text and isinstance(text, str):
        return text.split(';')[0].strip()
    return text

def parse_num(val):
    if not val: return 0
    try:
        if isinstance(val, str): return int(val.split('/')[0])
        return int(val)
    except: return 0

def get_metadata(file_path):
    """
    Fast extraction of text-only metadata.
    Returns: (album, artist, title, track_number, disc_number, year)
    """
    if not os.path.exists(file_path): 
        return ("Unknown Album", "Unknown Artist", format_track_name(file_path), 0, 0, "")
    
    album, album_artist, title, year = None, None, None, None
    track_num, disc_num = 0, 0

    try:
        audio = File(file_path)
        if isinstance(audio, FLAC):
            album = audio.get("album", [None])[0]
            album_artist = audio.get("albumartist", [None])[0]
            if not album_artist: album_artist = audio.get("artist", [None])[0]
            title = audio.get("title", [None])[0]
            
            track_num = parse_num(audio.get("tracknumber", [0])[0])
            disc_num = parse_num(audio.get("discnumber", [1])[0])
            
            date_str = audio.get("date", [None])[0]
            if date_str: year = date_str.split('-')[0]

        elif isinstance(audio, MP3):
            tags = audio.tags
            if tags:
                if 'TALB' in tags: album = tags['TALB'].text[0]
                if 'TPE2' in tags: album_artist = tags['TPE2'].text[0]
                if not album_artist and 'TPE1' in tags: album_artist = tags['TPE1'].text[0]
                if 'TIT2' in tags: title = tags['TIT2'].text[0]
                if 'TRCK' in tags: track_num = parse_num(tags['TRCK'].text[0])
                if 'TPOS' in tags: disc_num = parse_num(tags['TPOS'].text[0])
                
                if 'TDRC' in tags: year = str(tags['TDRC'].text[0]).split('-')[0]
                elif 'TYER' in tags: year = str(tags['TYER'].text[0])

    except: pass

    album = clean_tag(album)
    album_artist = clean_tag(album_artist)
    if not title: title = format_track_name(file_path)

    return (
        sanitize_text(album or "Unknown Album"), 
        sanitize_text(album_artist or "Unknown Artist"),
        sanitize_text(title),
        track_num,
        disc_num,
        str(year) if year else ""
    )

def get_cover(file_path):
    """
    Image-only extraction. Heavy operation.
    Returns: (small_dithered_image, large_dithered_image) or (None, None)
    """
    if not os.path.exists(file_path): return (None, None)
    
    cover_bytes = None
    
    try:
        audio = File(file_path)
        if isinstance(audio, FLAC):
            if audio.pictures: 
                cover_bytes = audio.pictures[0].data
        elif isinstance(audio, MP3):
            if audio.tags:
                for key in audio.tags.keys():
                    if key.startswith('APIC'):
                        cover_bytes = audio.tags[key].data
                        break
    except: pass

    final_small = None
    final_large = None
    
    if cover_bytes:
        try:
            img_obj = Image.open(io.BytesIO(cover_bytes))
            final_small = dither_image(img_obj.copy(), target_size=(83, 83))
            final_large = dither_image(img_obj.copy(), target_size=(111, 111))
        except: pass

    return (final_small, final_large)
