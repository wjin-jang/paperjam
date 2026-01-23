/*
 * PaperJam Bare-Metal OS - FLAC Metadata Parser
 *
 * Parses Vorbis comments and picture blocks from FLAC files
 */

#include "hal/bcm2837.h"
#include "flac_meta.h"
#include "fatfs/ff.h"
#include "sys/heap.h"

/* FLAC magic number */
#define FLAC_MAGIC 0x664C6143  /* "fLaC" */

/* Metadata block types */
#define BLOCK_STREAMINFO     0
#define BLOCK_PADDING        1
#define BLOCK_APPLICATION    2
#define BLOCK_SEEKTABLE      3
#define BLOCK_VORBIS_COMMENT 4
#define BLOCK_CUESHEET       5
#define BLOCK_PICTURE        6

/*
 * Read big-endian 24-bit value
 */
static u32 read_be24(const u8* data) {
    return ((u32)data[0] << 16) | ((u32)data[1] << 8) | data[2];
}

/*
 * Read big-endian 32-bit value
 */
static u32 read_be32(const u8* data) {
    return ((u32)data[0] << 24) | ((u32)data[1] << 16) |
           ((u32)data[2] << 8) | data[3];
}

/*
 * Read little-endian 32-bit value (Vorbis comments use LE)
 */
static u32 read_le32(const u8* data) {
    return data[0] | ((u32)data[1] << 8) |
           ((u32)data[2] << 16) | ((u32)data[3] << 24);
}

/*
 * Case-insensitive string compare for n characters
 */
static int strncasecmp_local(const char* s1, const char* s2, int n) {
    for (int i = 0; i < n; i++) {
        char c1 = s1[i];
        char c2 = s2[i];

        /* Convert to lowercase */
        if (c1 >= 'A' && c1 <= 'Z') c1 += 32;
        if (c2 >= 'A' && c2 <= 'Z') c2 += 32;

        if (c1 != c2) return c1 - c2;
        if (c1 == '\0') return 0;
    }
    return 0;
}

/*
 * Parse a single Vorbis comment field
 */
static void parse_vorbis_field(const char* field, int field_len, flac_metadata_t* meta) {
    /* Find '=' separator */
    int eq_pos = -1;
    for (int i = 0; i < field_len; i++) {
        if (field[i] == '=') {
            eq_pos = i;
            break;
        }
    }

    if (eq_pos <= 0) return;

    const char* value = field + eq_pos + 1;
    int value_len = field_len - eq_pos - 1;

    /* Limit value length */
    if (value_len >= FLAC_META_MAX_STRING) {
        value_len = FLAC_META_MAX_STRING - 1;
    }

    /* Match field name */
    if (strncasecmp_local(field, "TITLE", 5) == 0 && eq_pos == 5) {
        memcpy(meta->title, value, value_len);
        meta->title[value_len] = '\0';
    }
    else if (strncasecmp_local(field, "ARTIST", 6) == 0 && eq_pos == 6) {
        memcpy(meta->artist, value, value_len);
        meta->artist[value_len] = '\0';
    }
    else if (strncasecmp_local(field, "ALBUM", 5) == 0 && eq_pos == 5) {
        memcpy(meta->album, value, value_len);
        meta->album[value_len] = '\0';
    }
    else if (strncasecmp_local(field, "ALBUMARTIST", 11) == 0 && eq_pos == 11) {
        memcpy(meta->album_artist, value, value_len);
        meta->album_artist[value_len] = '\0';
    }
    else if (strncasecmp_local(field, "GENRE", 5) == 0 && eq_pos == 5) {
        memcpy(meta->genre, value, value_len);
        meta->genre[value_len] = '\0';
    }
    else if (strncasecmp_local(field, "DATE", 4) == 0 && eq_pos == 4) {
        int len = value_len < 31 ? value_len : 31;
        memcpy(meta->date, value, len);
        meta->date[len] = '\0';
    }
    else if (strncasecmp_local(field, "TRACKNUMBER", 11) == 0 && eq_pos == 11) {
        meta->track_number = 0;
        for (int i = 0; i < value_len && value[i] >= '0' && value[i] <= '9'; i++) {
            meta->track_number = meta->track_number * 10 + (value[i] - '0');
        }
    }
    else if (strncasecmp_local(field, "TRACKTOTAL", 10) == 0 && eq_pos == 10) {
        meta->track_total = 0;
        for (int i = 0; i < value_len && value[i] >= '0' && value[i] <= '9'; i++) {
            meta->track_total = meta->track_total * 10 + (value[i] - '0');
        }
    }
    else if (strncasecmp_local(field, "DISCNUMBER", 10) == 0 && eq_pos == 10) {
        meta->disc_number = 0;
        for (int i = 0; i < value_len && value[i] >= '0' && value[i] <= '9'; i++) {
            meta->disc_number = meta->disc_number * 10 + (value[i] - '0');
        }
    }
    else if (strncasecmp_local(field, "DISCTOTAL", 9) == 0 && eq_pos == 9) {
        meta->disc_total = 0;
        for (int i = 0; i < value_len && value[i] >= '0' && value[i] <= '9'; i++) {
            meta->disc_total = meta->disc_total * 10 + (value[i] - '0');
        }
    }
}

/*
 * Parse STREAMINFO block
 */
static void parse_streaminfo(const u8* data, flac_metadata_t* meta) {
    /* Skip min/max block size (4 bytes) and min/max frame size (6 bytes) */
    const u8* p = data + 10;

    /* Sample rate (20 bits), channels-1 (3 bits), bits-1 (5 bits), total samples (36 bits) */
    u32 word1 = read_be32(p);
    u32 word2 = read_be32(p + 4);

    meta->sample_rate = word1 >> 12;
    meta->channels = ((word1 >> 9) & 0x7) + 1;
    meta->bits_per_sample = ((word1 >> 4) & 0x1F) + 1;

    /* Total samples is 36 bits: 4 bits from word1, 32 bits from word2 */
    u64 total_samples = ((u64)(word1 & 0xF) << 32) | word2;
    meta->total_samples = (u32)total_samples;

    /* Calculate duration */
    if (meta->sample_rate > 0) {
        meta->duration_ms = (u32)((total_samples * 1000) / meta->sample_rate);
    }
}

/*
 * Parse Vorbis comment block
 */
static void parse_vorbis_comment(const u8* data, u32 block_size, flac_metadata_t* meta) {
    if (block_size < 8) return;

    u32 pos = 0;

    /* Vendor string length (LE) */
    u32 vendor_len = read_le32(data + pos);
    pos += 4;

    /* Skip vendor string */
    if (pos + vendor_len > block_size) return;
    pos += vendor_len;

    /* Number of comments */
    if (pos + 4 > block_size) return;
    u32 comment_count = read_le32(data + pos);
    pos += 4;

    /* Parse each comment */
    for (u32 i = 0; i < comment_count && pos + 4 <= block_size; i++) {
        u32 field_len = read_le32(data + pos);
        pos += 4;

        if (pos + field_len > block_size) break;

        parse_vorbis_field((const char*)(data + pos), field_len, meta);
        pos += field_len;
    }
}

/*
 * Parse FLAC metadata from file
 */
int flac_meta_parse(const char* path, flac_metadata_t* meta) {
    FIL file;
    UINT br;
    u8 header[4];
    u8* block_data = NULL;
    int result = -1;

    memset(meta, 0, sizeof(flac_metadata_t));

    if (f_open(&file, path, FA_READ) != FR_OK) {
        return -1;
    }

    /* Read FLAC magic */
    if (f_read(&file, header, 4, &br) != FR_OK || br != 4) {
        goto cleanup;
    }

    if (read_be32(header) != FLAC_MAGIC) {
        goto cleanup;
    }

    /* Parse metadata blocks */
    int is_last = 0;
    while (!is_last) {
        /* Read block header */
        if (f_read(&file, header, 4, &br) != FR_OK || br != 4) {
            break;
        }

        is_last = (header[0] & 0x80) != 0;
        int block_type = header[0] & 0x7F;
        u32 block_size = read_be24(header + 1);

        /* Allocate block data */
        if (block_data) {
            heap_free(block_data);
            block_data = NULL;
        }

        if (block_size > 0 && block_size < (1024 * 1024)) {
            block_data = (u8*)heap_alloc(block_size);
            if (!block_data) break;

            if (f_read(&file, block_data, block_size, &br) != FR_OK || br != block_size) {
                break;
            }

            /* Parse based on block type */
            switch (block_type) {
                case BLOCK_STREAMINFO:
                    parse_streaminfo(block_data, meta);
                    break;

                case BLOCK_VORBIS_COMMENT:
                    parse_vorbis_comment(block_data, block_size, meta);
                    break;
            }
        } else {
            /* Skip block */
            f_lseek(&file, f_tell(&file) + block_size);
        }
    }

    result = 0;

cleanup:
    if (block_data) heap_free(block_data);
    f_close(&file);
    return result;
}

/*
 * Extract picture from FLAC file
 */
int flac_meta_get_picture(const char* path, int picture_type, flac_picture_t* picture) {
    FIL file;
    UINT br;
    u8 header[4];
    u8* block_data = NULL;
    int result = -1;
    int found_any = 0;

    memset(picture, 0, sizeof(flac_picture_t));

    if (f_open(&file, path, FA_READ) != FR_OK) {
        return -1;
    }

    /* Read FLAC magic */
    if (f_read(&file, header, 4, &br) != FR_OK || br != 4) {
        goto cleanup;
    }

    if (read_be32(header) != FLAC_MAGIC) {
        goto cleanup;
    }

    /* Search for picture block */
    int is_last = 0;
    while (!is_last) {
        /* Read block header */
        if (f_read(&file, header, 4, &br) != FR_OK || br != 4) {
            break;
        }

        is_last = (header[0] & 0x80) != 0;
        int block_type = header[0] & 0x7F;
        u32 block_size = read_be24(header + 1);

        if (block_type == BLOCK_PICTURE && block_size >= 32) {
            /* Read picture block */
            if (block_data) heap_free(block_data);
            block_data = (u8*)heap_alloc(block_size);
            if (!block_data) break;

            if (f_read(&file, block_data, block_size, &br) != FR_OK || br != block_size) {
                break;
            }

            u32 pos = 0;

            /* Picture type */
            int pic_type = read_be32(block_data + pos);
            pos += 4;

            /* MIME type */
            u32 mime_len = read_be32(block_data + pos);
            pos += 4;
            if (pos + mime_len > block_size) continue;

            int copy_len = mime_len < 63 ? mime_len : 63;
            memcpy(picture->mime_type, block_data + pos, copy_len);
            picture->mime_type[copy_len] = '\0';
            pos += mime_len;

            /* Description */
            if (pos + 4 > block_size) continue;
            u32 desc_len = read_be32(block_data + pos);
            pos += 4;
            if (pos + desc_len > block_size) continue;

            copy_len = desc_len < 127 ? desc_len : 127;
            memcpy(picture->description, block_data + pos, copy_len);
            picture->description[copy_len] = '\0';
            pos += desc_len;

            /* Dimensions */
            if (pos + 20 > block_size) continue;
            picture->width = read_be32(block_data + pos);
            picture->height = read_be32(block_data + pos + 4);
            picture->depth = read_be32(block_data + pos + 8);
            picture->colors = read_be32(block_data + pos + 12);
            pos += 16;

            /* Picture data */
            u32 data_len = read_be32(block_data + pos);
            pos += 4;
            if (pos + data_len > block_size) continue;

            picture->type = pic_type;
            picture->data_size = data_len;

            /* Check if this is the type we want, or accept any if not found yet */
            if (pic_type == picture_type || (!found_any && data_len > 0)) {
                /* Copy picture data */
                if (picture->data) heap_free(picture->data);
                picture->data = (u8*)heap_alloc(data_len);
                if (picture->data) {
                    memcpy(picture->data, block_data + pos, data_len);
                    found_any = 1;

                    /* If exact match, we're done */
                    if (pic_type == picture_type) {
                        result = 0;
                        goto cleanup;
                    }
                }
            }
        } else {
            /* Skip block */
            f_lseek(&file, f_tell(&file) + block_size);
        }
    }

    /* Return success if we found any picture */
    if (found_any) {
        result = 0;
    }

cleanup:
    if (block_data) heap_free(block_data);
    f_close(&file);
    return result;
}

/*
 * Free picture data
 */
void flac_meta_free_picture(flac_picture_t* picture) {
    if (picture->data) {
        heap_free(picture->data);
        picture->data = NULL;
    }
    picture->data_size = 0;
}

/*
 * Check if file is a FLAC file
 */
int flac_meta_is_flac(const char* path) {
    FIL file;
    UINT br;
    u8 header[4];

    if (f_open(&file, path, FA_READ) != FR_OK) {
        return 0;
    }

    int is_flac = 0;
    if (f_read(&file, header, 4, &br) == FR_OK && br == 4) {
        is_flac = (read_be32(header) == FLAC_MAGIC);
    }

    f_close(&file);
    return is_flac;
}
