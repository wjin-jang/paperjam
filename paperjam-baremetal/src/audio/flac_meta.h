/*
 * PaperJam Bare-Metal OS - FLAC Metadata Parser Header
 *
 * Parses Vorbis comments and picture blocks from FLAC files
 */

#ifndef FLAC_META_H
#define FLAC_META_H

#include "hal/bcm2837.h"

/* Maximum field lengths */
#define FLAC_META_MAX_STRING  128
#define FLAC_META_MAX_PICTURE (64 * 1024)

/* Picture types (FLAC standard) */
#define FLAC_PICTURE_OTHER          0
#define FLAC_PICTURE_FILE_ICON      1
#define FLAC_PICTURE_OTHER_ICON     2
#define FLAC_PICTURE_FRONT_COVER    3
#define FLAC_PICTURE_BACK_COVER     4
#define FLAC_PICTURE_LEAFLET        5
#define FLAC_PICTURE_MEDIA          6
#define FLAC_PICTURE_LEAD_ARTIST    7
#define FLAC_PICTURE_ARTIST         8
#define FLAC_PICTURE_CONDUCTOR      9
#define FLAC_PICTURE_BAND           10
#define FLAC_PICTURE_COMPOSER       11
#define FLAC_PICTURE_LYRICIST       12
#define FLAC_PICTURE_LOCATION       13
#define FLAC_PICTURE_DURING_REC     14
#define FLAC_PICTURE_DURING_PERF    15
#define FLAC_PICTURE_SCREEN_CAP     16
#define FLAC_PICTURE_FISH           17
#define FLAC_PICTURE_ILLUSTRATION   18
#define FLAC_PICTURE_BAND_LOGO      19
#define FLAC_PICTURE_PUB_LOGO       20

/* FLAC metadata structure */
typedef struct {
    char title[FLAC_META_MAX_STRING];
    char artist[FLAC_META_MAX_STRING];
    char album[FLAC_META_MAX_STRING];
    char album_artist[FLAC_META_MAX_STRING];
    char genre[FLAC_META_MAX_STRING];
    char date[32];
    int track_number;
    int track_total;
    int disc_number;
    int disc_total;
    u32 duration_ms;
    u32 sample_rate;
    u32 total_samples;
    int bits_per_sample;
    int channels;
} flac_metadata_t;

/* FLAC picture structure */
typedef struct {
    int type;
    char mime_type[64];
    char description[128];
    int width;
    int height;
    int depth;
    int colors;
    u8* data;
    u32 data_size;
} flac_picture_t;

/*
 * Parse FLAC metadata from file
 *
 * path: Path to FLAC file
 * meta: Output metadata structure
 *
 * Returns: 0 on success, -1 on error
 */
int flac_meta_parse(const char* path, flac_metadata_t* meta);

/*
 * Extract picture from FLAC file
 *
 * path: Path to FLAC file
 * picture_type: Desired picture type (FLAC_PICTURE_FRONT_COVER recommended)
 * picture: Output picture structure (caller allocates, data allocated internally)
 *
 * Returns: 0 on success, -1 if no picture found
 */
int flac_meta_get_picture(const char* path, int picture_type, flac_picture_t* picture);

/*
 * Free picture data
 */
void flac_meta_free_picture(flac_picture_t* picture);

/*
 * Check if file is a FLAC file
 */
int flac_meta_is_flac(const char* path);

#endif /* FLAC_META_H */
