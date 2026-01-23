/*
 * PaperJam Bare-Metal OS - ID3 Tag Parser
 *
 * Parses ID3v1, ID3v2.3, and ID3v2.4 tags from MP3 files
 * Extracts: title, artist, album, year, track, genre, cover art
 */

#include "hal/bcm2837.h"
#include "id3.h"
#include "lib/fatfs/ff.h"
#include "sys/heap.h"

/* ID3v2 frame IDs */
#define ID3_FRAME_TITLE     0x54495432  /* "TIT2" */
#define ID3_FRAME_ARTIST    0x54504531  /* "TPE1" */
#define ID3_FRAME_ALBUM     0x54414C42  /* "TALB" */
#define ID3_FRAME_YEAR      0x54594552  /* "TYER" (v2.3) */
#define ID3_FRAME_DATE      0x54445243  /* "TDRC" (v2.4) */
#define ID3_FRAME_TRACK     0x5452434B  /* "TRCK" */
#define ID3_FRAME_GENRE     0x54434F4E  /* "TCON" */
#define ID3_FRAME_PICTURE   0x41504943  /* "APIC" */

/* ID3v1 genres */
static const char* id3v1_genres[] = {
    "Blues", "Classic Rock", "Country", "Dance", "Disco", "Funk", "Grunge",
    "Hip-Hop", "Jazz", "Metal", "New Age", "Oldies", "Other", "Pop", "R&B",
    "Rap", "Reggae", "Rock", "Techno", "Industrial", "Alternative", "Ska",
    "Death Metal", "Pranks", "Soundtrack", "Euro-Techno", "Ambient",
    "Trip-Hop", "Vocal", "Jazz+Funk", "Fusion", "Trance", "Classical",
    "Instrumental", "Acid", "House", "Game", "Sound Clip", "Gospel", "Noise",
    "AlternRock", "Bass", "Soul", "Punk", "Space", "Meditative",
    "Instrumental Pop", "Instrumental Rock", "Ethnic", "Gothic", "Darkwave",
    "Techno-Industrial", "Electronic", "Pop-Folk", "Eurodance", "Dream",
    "Southern Rock", "Comedy", "Cult", "Gangsta", "Top 40", "Christian Rap",
    "Pop/Funk", "Jungle", "Native American", "Cabaret", "New Wave",
    "Psychedelic", "Rave", "Showtunes", "Trailer", "Lo-Fi", "Tribal",
    "Acid Punk", "Acid Jazz", "Polka", "Retro", "Musical", "Rock & Roll",
    "Hard Rock"
};
#define NUM_ID3V1_GENRES (sizeof(id3v1_genres) / sizeof(id3v1_genres[0]))

/*
 * Read syncsafe integer (ID3v2)
 */
static u32 read_syncsafe_int(const u8* data) {
    return ((data[0] & 0x7F) << 21) |
           ((data[1] & 0x7F) << 14) |
           ((data[2] & 0x7F) << 7) |
           (data[3] & 0x7F);
}

/*
 * Read big-endian 32-bit integer
 */
static u32 read_u32_be(const u8* data) {
    return (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3];
}

/*
 * Copy string, handling encoding
 */
static void copy_string(char* dst, const u8* src, int src_len, int encoding, int max_len) {
    int i = 0;
    int di = 0;

    switch (encoding) {
        case 0:  /* ISO-8859-1 */
        case 3:  /* UTF-8 */
            while (i < src_len && di < max_len - 1) {
                if (src[i] == 0) break;
                dst[di++] = src[i++];
            }
            break;

        case 1:  /* UTF-16 with BOM */
        case 2:  /* UTF-16 BE */
            /* Skip BOM if present */
            if (encoding == 1 && src_len >= 2) {
                if (src[0] == 0xFF && src[1] == 0xFE) {
                    src += 2;
                    src_len -= 2;
                } else if (src[0] == 0xFE && src[1] == 0xFF) {
                    src += 2;
                    src_len -= 2;
                    encoding = 2;  /* Big endian */
                }
            }

            /* Convert UTF-16 to ASCII (lossy) */
            while (i + 1 < src_len && di < max_len - 1) {
                u16 c;
                if (encoding == 2) {
                    c = (src[i] << 8) | src[i + 1];
                } else {
                    c = src[i] | (src[i + 1] << 8);
                }
                if (c == 0) break;
                if (c < 128) {
                    dst[di++] = (char)c;
                } else {
                    dst[di++] = '?';
                }
                i += 2;
            }
            break;
    }

    dst[di] = '\0';
}

/*
 * Parse ID3v2 tag
 */
static int parse_id3v2(FIL* file, id3_tag_t* tag, u32 tag_size) {
    u8 frame_header[10];
    u32 pos = 10;  /* After ID3 header */

    while (pos + 10 < tag_size) {
        /* Read frame header */
        UINT br;
        if (f_read(file, frame_header, 10, &br) != FR_OK || br < 10) {
            break;
        }

        /* Check for padding */
        if (frame_header[0] == 0) break;

        u32 frame_id = read_u32_be(&frame_header[0]);
        u32 frame_size = read_u32_be(&frame_header[4]);

        /* Skip flags */
        pos += 10;

        /* Limit frame size */
        if (frame_size > 1024 * 1024 || frame_size > tag_size - pos) {
            break;
        }

        /* Read frame data */
        u8* frame_data = (u8*)heap_alloc(frame_size + 1);
        if (!frame_data) break;

        if (f_read(file, frame_data, frame_size, &br) != FR_OK || br < frame_size) {
            heap_free(frame_data);
            break;
        }

        /* Parse frame based on ID */
        u8 encoding = frame_data[0];

        switch (frame_id) {
            case ID3_FRAME_TITLE:
                copy_string(tag->title, &frame_data[1], frame_size - 1, encoding, sizeof(tag->title));
                break;

            case ID3_FRAME_ARTIST:
                copy_string(tag->artist, &frame_data[1], frame_size - 1, encoding, sizeof(tag->artist));
                break;

            case ID3_FRAME_ALBUM:
                copy_string(tag->album, &frame_data[1], frame_size - 1, encoding, sizeof(tag->album));
                break;

            case ID3_FRAME_YEAR:
            case ID3_FRAME_DATE:
                {
                    char year_str[8];
                    copy_string(year_str, &frame_data[1], frame_size - 1, encoding, sizeof(year_str));
                    tag->year = 0;
                    for (int i = 0; year_str[i] >= '0' && year_str[i] <= '9' && i < 4; i++) {
                        tag->year = tag->year * 10 + (year_str[i] - '0');
                    }
                }
                break;

            case ID3_FRAME_TRACK:
                {
                    char track_str[8];
                    copy_string(track_str, &frame_data[1], frame_size - 1, encoding, sizeof(track_str));
                    tag->track = 0;
                    for (int i = 0; track_str[i] >= '0' && track_str[i] <= '9'; i++) {
                        tag->track = tag->track * 10 + (track_str[i] - '0');
                    }
                }
                break;

            case ID3_FRAME_GENRE:
                copy_string(tag->genre, &frame_data[1], frame_size - 1, encoding, sizeof(tag->genre));
                /* Handle numeric genre reference: (123) */
                if (tag->genre[0] == '(') {
                    int genre_num = 0;
                    for (int i = 1; tag->genre[i] >= '0' && tag->genre[i] <= '9'; i++) {
                        genre_num = genre_num * 10 + (tag->genre[i] - '0');
                    }
                    if (genre_num < (int)NUM_ID3V1_GENRES) {
                        strcpy(tag->genre, id3v1_genres[genre_num]);
                    }
                }
                break;

            case ID3_FRAME_PICTURE:
                /* APIC frame structure:
                 * encoding (1 byte)
                 * MIME type (null-terminated)
                 * picture type (1 byte)
                 * description (null-terminated)
                 * picture data
                 */
                {
                    int offset = 1;  /* Skip encoding */

                    /* Skip MIME type */
                    while (offset < (int)frame_size && frame_data[offset] != 0) offset++;
                    offset++;

                    /* Check picture type (3 = front cover) */
                    if (offset < (int)frame_size) {
                        u8 pic_type = frame_data[offset++];
                        (void)pic_type;

                        /* Skip description */
                        if (encoding == 1 || encoding == 2) {
                            while (offset + 1 < (int)frame_size) {
                                if (frame_data[offset] == 0 && frame_data[offset + 1] == 0) {
                                    offset += 2;
                                    break;
                                }
                                offset += 2;
                            }
                        } else {
                            while (offset < (int)frame_size && frame_data[offset] != 0) offset++;
                            offset++;
                        }

                        /* Remaining is picture data */
                        if (offset < (int)frame_size) {
                            tag->has_cover_art = 1;
                            tag->cover_art_offset = f_tell(file) - frame_size + offset;
                            tag->cover_art_size = frame_size - offset;
                        }
                    }
                }
                break;
        }

        heap_free(frame_data);
        pos += frame_size;
    }

    return 0;
}

/*
 * Parse ID3v1 tag
 */
static int parse_id3v1(FIL* file, id3_tag_t* tag) {
    u8 data[128];
    UINT br;

    /* Seek to last 128 bytes */
    if (f_lseek(file, f_size(file) - 128) != FR_OK) {
        return -1;
    }

    if (f_read(file, data, 128, &br) != FR_OK || br < 128) {
        return -1;
    }

    /* Check TAG marker */
    if (data[0] != 'T' || data[1] != 'A' || data[2] != 'G') {
        return -1;
    }

    /* Extract fields (30, 30, 30, 4, 30, 1 bytes) */
    memcpy(tag->title, &data[3], 30);
    tag->title[30] = '\0';

    memcpy(tag->artist, &data[33], 30);
    tag->artist[30] = '\0';

    memcpy(tag->album, &data[63], 30);
    tag->album[30] = '\0';

    char year_str[5];
    memcpy(year_str, &data[93], 4);
    year_str[4] = '\0';
    tag->year = 0;
    for (int i = 0; year_str[i] >= '0' && year_str[i] <= '9'; i++) {
        tag->year = tag->year * 10 + (year_str[i] - '0');
    }

    /* ID3v1.1: track number in comment[28] if comment[29] != 0 */
    if (data[125] == 0 && data[126] != 0) {
        tag->track = data[126];
    }

    /* Genre */
    u8 genre_idx = data[127];
    if (genre_idx < NUM_ID3V1_GENRES) {
        strcpy(tag->genre, id3v1_genres[genre_idx]);
    }

    /* Trim trailing spaces */
    for (int i = strlen(tag->title) - 1; i >= 0 && tag->title[i] == ' '; i--) {
        tag->title[i] = '\0';
    }
    for (int i = strlen(tag->artist) - 1; i >= 0 && tag->artist[i] == ' '; i--) {
        tag->artist[i] = '\0';
    }
    for (int i = strlen(tag->album) - 1; i >= 0 && tag->album[i] == ' '; i--) {
        tag->album[i] = '\0';
    }

    return 0;
}

/*
 * Parse ID3 tags from MP3 file
 */
int id3_parse(const char* path, id3_tag_t* tag) {
    if (!path || !tag) return -1;

    memset(tag, 0, sizeof(id3_tag_t));

    FIL file;
    if (f_open(&file, path, FA_READ) != FR_OK) {
        return -1;
    }

    /* Check for ID3v2 tag */
    u8 header[10];
    UINT br;

    if (f_read(&file, header, 10, &br) == FR_OK && br == 10) {
        if (header[0] == 'I' && header[1] == 'D' && header[2] == '3') {
            /* ID3v2 found */
            tag->version = (header[3] == 4) ? ID3_VERSION_2_4 :
                          (header[3] == 3) ? ID3_VERSION_2_3 :
                          (header[3] == 2) ? ID3_VERSION_2_2 : ID3_VERSION_2_3;

            u32 tag_size = read_syncsafe_int(&header[6]);
            parse_id3v2(&file, tag, tag_size + 10);
        }
    }

    /* Try ID3v1 if ID3v2 didn't have all info */
    if (tag->title[0] == '\0' || tag->artist[0] == '\0') {
        parse_id3v1(&file, tag);
        if (tag->version == ID3_VERSION_NONE) {
            tag->version = ID3_VERSION_1;
        }
    }

    f_close(&file);

    /* Set default title from filename if not found */
    if (tag->title[0] == '\0') {
        const char* filename = path;
        for (const char* p = path; *p; p++) {
            if (*p == '/') filename = p + 1;
        }
        int len = strlen(filename);
        /* Remove extension */
        for (int i = len - 1; i > 0; i--) {
            if (filename[i] == '.') {
                len = i;
                break;
            }
        }
        if (len > (int)sizeof(tag->title) - 1) {
            len = sizeof(tag->title) - 1;
        }
        memcpy(tag->title, filename, len);
        tag->title[len] = '\0';
    }

    return 0;
}

/*
 * Get ID3v1 genre name by index
 */
const char* id3_get_genre_name(int index) {
    if (index < 0 || index >= (int)NUM_ID3V1_GENRES) {
        return "Unknown";
    }
    return id3v1_genres[index];
}

/*
 * Read cover art data
 */
int id3_read_cover_art(const char* path, id3_tag_t* tag, u8* buffer, u32 max_size) {
    if (!path || !tag || !buffer || !tag->has_cover_art) {
        return -1;
    }

    FIL file;
    if (f_open(&file, path, FA_READ) != FR_OK) {
        return -1;
    }

    if (f_lseek(&file, tag->cover_art_offset) != FR_OK) {
        f_close(&file);
        return -1;
    }

    u32 size = tag->cover_art_size;
    if (size > max_size) size = max_size;

    UINT br;
    if (f_read(&file, buffer, size, &br) != FR_OK) {
        f_close(&file);
        return -1;
    }

    f_close(&file);
    return (int)br;
}
