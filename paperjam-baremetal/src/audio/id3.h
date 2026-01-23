/*
 * PaperJam Bare-Metal OS - ID3 Tag Parser Header
 */

#ifndef ID3_H
#define ID3_H

#include "hal/bcm2837.h"

/* ID3 version */
typedef enum {
    ID3_VERSION_NONE = 0,
    ID3_VERSION_1,
    ID3_VERSION_2_2,
    ID3_VERSION_2_3,
    ID3_VERSION_2_4
} id3_version_t;

/* ID3 tag structure */
typedef struct {
    char title[128];
    char artist[128];
    char album[128];
    char genre[32];
    u32 year;
    u32 track;
    id3_version_t version;
    int has_cover_art;
    u32 cover_art_offset;
    u32 cover_art_size;
} id3_tag_t;

/* Function prototypes */
int id3_parse(const char* path, id3_tag_t* tag);
const char* id3_get_genre_name(int index);
int id3_read_cover_art(const char* path, id3_tag_t* tag, u8* buffer, u32 max_size);

#endif /* ID3_H */
