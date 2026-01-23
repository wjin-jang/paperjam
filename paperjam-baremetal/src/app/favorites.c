/*
 * PaperJam Bare-Metal OS - Favorites System
 */

#include "hal/bcm2837.h"
#include "favorites.h"
#include "lib/fatfs/ff.h"
#include "sys/heap.h"

/* Favorites configuration */
#define FAVORITES_FILE      "/data/favorites.txt"
#define MAX_FAVORITES       200
#define MAX_PATH_LENGTH     256

/* Favorites storage */
static char** favorites = NULL;
static int favorites_count = 0;
static int favorites_capacity = 0;

/*
 * Initialize favorites
 */
void favorites_init(void) {
    favorites = NULL;
    favorites_count = 0;
    favorites_capacity = 0;
}

/*
 * Load favorites from file
 */
int favorites_load(void) {
    FIL file;
    if (f_open(&file, FAVORITES_FILE, FA_READ) != FR_OK) {
        return -1;  /* File doesn't exist yet */
    }

    char line[MAX_PATH_LENGTH];
    while (f_gets(line, sizeof(line), &file)) {
        /* Remove newline */
        int len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) {
            line[--len] = '\0';
        }
        if (len > 0) {
            favorites_add(line);
        }
    }

    f_close(&file);
    return 0;
}

/*
 * Save favorites to file
 */
int favorites_save(void) {
    /* Ensure /data directory exists */
    f_mkdir("/data");

    FIL file;
    if (f_open(&file, FAVORITES_FILE, FA_WRITE | FA_CREATE_ALWAYS) != FR_OK) {
        return -1;
    }

    UINT bw;
    for (int i = 0; i < favorites_count; i++) {
        f_write(&file, favorites[i], strlen(favorites[i]), &bw);
        f_write(&file, "\n", 1, &bw);
    }

    f_close(&file);
    return 0;
}

/*
 * Add to favorites
 */
int favorites_add(const char* path) {
    /* Check if already in favorites */
    if (favorites_is_favorite(path)) {
        return 0;
    }

    /* Expand if needed */
    if (favorites_count >= favorites_capacity) {
        int new_capacity = favorites_capacity ? favorites_capacity * 2 : 20;
        if (new_capacity > MAX_FAVORITES) {
            new_capacity = MAX_FAVORITES;
        }
        if (new_capacity <= favorites_capacity) {
            return -1;
        }

        char** new_fav = (char**)heap_realloc(favorites, new_capacity * sizeof(char*));
        if (!new_fav) return -1;

        favorites = new_fav;
        favorites_capacity = new_capacity;
    }

    /* Allocate and copy path */
    int len = strlen(path);
    char* entry = (char*)heap_alloc(len + 1);
    if (!entry) return -1;

    strcpy(entry, path);
    favorites[favorites_count++] = entry;

    return 0;
}

/*
 * Remove from favorites
 */
int favorites_remove(const char* path) {
    for (int i = 0; i < favorites_count; i++) {
        if (strcmp(favorites[i], path) == 0) {
            heap_free(favorites[i]);

            /* Shift entries */
            for (int j = i; j < favorites_count - 1; j++) {
                favorites[j] = favorites[j + 1];
            }

            favorites_count--;
            return 0;
        }
    }
    return -1;
}

/*
 * Toggle favorite status
 */
int favorites_toggle(const char* path) {
    if (favorites_is_favorite(path)) {
        favorites_remove(path);
        return 0;
    } else {
        favorites_add(path);
        return 1;
    }
}

/*
 * Check if path is favorite
 */
int favorites_is_favorite(const char* path) {
    for (int i = 0; i < favorites_count; i++) {
        if (strcmp(favorites[i], path) == 0) {
            return 1;
        }
    }
    return 0;
}

/*
 * Get favorites count
 */
int favorites_count_entries(void) {
    return favorites_count;
}

/*
 * Get favorite path
 */
const char* favorites_get_path(int index) {
    if (index < 0 || index >= favorites_count) return NULL;
    return favorites[index];
}

/*
 * Clear all favorites
 */
void favorites_clear(void) {
    for (int i = 0; i < favorites_count; i++) {
        heap_free(favorites[i]);
    }
    favorites_count = 0;
}

/*
 * Free favorites
 */
void favorites_free(void) {
    favorites_clear();
    if (favorites) {
        heap_free(favorites);
        favorites = NULL;
    }
    favorites_capacity = 0;
}
