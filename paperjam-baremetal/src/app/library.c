/*
 * PaperJam Bare-Metal OS - Music Library Management
 */

#include "hal/bcm2837.h"
#include "library.h"
#include "lib/fatfs/ff.h"
#include "sys/heap.h"

/* Library configuration */
#define MUSIC_PATH          "/music"
#define MAX_LIBRARY_SIZE    1000
#define MAX_PATH_LENGTH     256

/* Track entry */
typedef struct {
    char path[MAX_PATH_LENGTH];
    char title[64];
    char artist[64];
    char album[64];
} library_entry_t;

/* Library state */
static library_entry_t* library = NULL;
static int library_count = 0;
static int library_capacity = 0;
static int library_loaded = 0;

/* Supported extensions */
static const char* supported_extensions[] = {
    ".mp3", ".MP3",
    ".flac", ".FLAC",
    ".wav", ".WAV",
    NULL
};

/*
 * Check if file has supported extension
 */
static int is_supported_file(const char* filename) {
    int len = strlen(filename);
    if (len < 4) return 0;

    for (int i = 0; supported_extensions[i]; i++) {
        int ext_len = strlen(supported_extensions[i]);
        if (len >= ext_len &&
            strcmp(filename + len - ext_len, supported_extensions[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

/*
 * Add entry to library
 */
static int library_add_entry(const char* path) {
    if (library_count >= library_capacity) {
        /* Expand library */
        int new_capacity = library_capacity ? library_capacity * 2 : 100;
        if (new_capacity > MAX_LIBRARY_SIZE) {
            new_capacity = MAX_LIBRARY_SIZE;
        }
        if (new_capacity <= library_capacity) {
            return -1;  /* At capacity */
        }

        library_entry_t* new_lib = (library_entry_t*)heap_realloc(
            library, new_capacity * sizeof(library_entry_t));
        if (!new_lib) return -1;

        library = new_lib;
        library_capacity = new_capacity;
    }

    library_entry_t* entry = &library[library_count];
    memset(entry, 0, sizeof(library_entry_t));

    /* Copy path */
    int len = strlen(path);
    if (len >= MAX_PATH_LENGTH) len = MAX_PATH_LENGTH - 1;
    memcpy(entry->path, path, len);
    entry->path[len] = '\0';

    /* Extract filename as title (without extension) */
    const char* filename = path;
    for (const char* p = path; *p; p++) {
        if (*p == '/') filename = p + 1;
    }

    len = strlen(filename);
    /* Remove extension */
    for (int i = len - 1; i > 0; i--) {
        if (filename[i] == '.') {
            len = i;
            break;
        }
    }
    if (len >= 64) len = 63;
    memcpy(entry->title, filename, len);
    entry->title[len] = '\0';

    /* Default artist/album */
    strcpy(entry->artist, "Unknown");
    strcpy(entry->album, "Unknown");

    library_count++;
    return 0;
}

/*
 * Scan directory recursively
 */
static int library_scan_dir(const char* path, int depth) {
    if (depth > 5) return 0;  /* Max recursion depth */

    DIR dir;
    FILINFO fno;

    if (f_opendir(&dir, path) != FR_OK) {
        return -1;
    }

    char full_path[MAX_PATH_LENGTH];

    while (f_readdir(&dir, &fno) == FR_OK && fno.fname[0]) {
        if (fno.fname[0] == '.') continue;  /* Skip hidden */

        /* Build full path */
        int path_len = strlen(path);
        int name_len = strlen(fno.fname);
        if (path_len + name_len + 2 > MAX_PATH_LENGTH) continue;

        strcpy(full_path, path);
        full_path[path_len] = '/';
        strcpy(full_path + path_len + 1, fno.fname);

        if (fno.fattrib & AM_DIR) {
            /* Recurse into directory */
            library_scan_dir(full_path, depth + 1);
        } else {
            /* Check if supported file */
            if (is_supported_file(fno.fname)) {
                library_add_entry(full_path);
            }
        }
    }

    f_closedir(&dir);
    return 0;
}

/*
 * Initialize library
 */
void library_init(void) {
    library = NULL;
    library_count = 0;
    library_capacity = 0;
    library_loaded = 0;
}

/*
 * Scan for music files
 */
int library_scan(void) {
    /* Clear existing */
    if (library) {
        heap_free(library);
        library = NULL;
    }
    library_count = 0;
    library_capacity = 0;

    /* Scan music directory */
    int result = library_scan_dir(MUSIC_PATH, 0);
    library_loaded = 1;

    return result;
}

/*
 * Get library count
 */
int library_count_entries(void) {
    return library_count;
}

/*
 * Get entry path
 */
const char* library_get_path(int index) {
    if (index < 0 || index >= library_count) return NULL;
    return library[index].path;
}

/*
 * Get entry title
 */
const char* library_get_title(int index) {
    if (index < 0 || index >= library_count) return NULL;
    return library[index].title;
}

/*
 * Get entry artist
 */
const char* library_get_artist(int index) {
    if (index < 0 || index >= library_count) return NULL;
    return library[index].artist;
}

/*
 * Get entry album
 */
const char* library_get_album(int index) {
    if (index < 0 || index >= library_count) return NULL;
    return library[index].album;
}

/*
 * Find entry by path
 */
int library_find_path(const char* path) {
    for (int i = 0; i < library_count; i++) {
        if (strcmp(library[i].path, path) == 0) {
            return i;
        }
    }
    return -1;
}

/*
 * Check if library is loaded
 */
int library_is_loaded(void) {
    return library_loaded;
}

/*
 * Free library
 */
void library_free(void) {
    if (library) {
        heap_free(library);
        library = NULL;
    }
    library_count = 0;
    library_capacity = 0;
    library_loaded = 0;
}
