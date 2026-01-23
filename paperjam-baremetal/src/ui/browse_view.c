/*
 * PaperJam Bare-Metal OS - Browse View
 *
 * Browse music by folders, artists, albums
 */

#include "hal/bcm2837.h"
#include "browse_view.h"
#include "menu.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "app/library.h"
#include "app/playlist.h"
#include "app/player.h"
#include "lib/fatfs/ff.h"
#include "sys/heap.h"

/* Browse modes */
typedef enum {
    BROWSE_MODE_FOLDERS,
    BROWSE_MODE_ARTISTS,
    BROWSE_MODE_ALBUMS,
    BROWSE_MODE_ALL_TRACKS
} browse_mode_t;

/* Browse state */
static browse_mode_t current_mode = BROWSE_MODE_FOLDERS;
static char current_path[256] = "/music";
static menu_t* browse_menu = NULL;
static char** item_labels = NULL;
static char** item_paths = NULL;
static int item_count = 0;

/*
 * Free current items
 */
static void free_items(void) {
    if (item_labels) {
        for (int i = 0; i < item_count; i++) {
            if (item_labels[i]) heap_free(item_labels[i]);
        }
        heap_free(item_labels);
        item_labels = NULL;
    }
    if (item_paths) {
        for (int i = 0; i < item_count; i++) {
            if (item_paths[i]) heap_free(item_paths[i]);
        }
        heap_free(item_paths);
        item_paths = NULL;
    }
    item_count = 0;
}

/*
 * Item selection callback
 */
static void on_item_selected(menu_item_t* item) {
    int index = (int)(intptr_t)item->data;

    if (index < 0 || index >= item_count) return;

    const char* path = item_paths[index];
    if (!path) return;

    /* Check if it's a directory */
    FILINFO fno;
    if (f_stat(path, &fno) == FR_OK) {
        if (fno.fattrib & AM_DIR) {
            /* Navigate into directory */
            strcpy(current_path, path);
            browse_view_refresh();
        } else {
            /* Play file */
            queue_clear();

            /* Add all files in current directory to queue */
            DIR dir;
            if (f_opendir(&dir, current_path) == FR_OK) {
                FILINFO finfo;
                int track_index = 0;
                int selected_track = -1;

                while (f_readdir(&dir, &finfo) == FR_OK && finfo.fname[0]) {
                    if (finfo.fattrib & AM_DIR) continue;

                    /* Check if audio file */
                    int len = strlen(finfo.fname);
                    if (len < 4) continue;

                    const char* ext = &finfo.fname[len - 4];
                    if (strcmp(ext, ".mp3") == 0 || strcmp(ext, ".MP3") == 0 ||
                        strcmp(ext, "flac") == 0 || strcmp(ext, "FLAC") == 0 ||
                        strcmp(ext, ".wav") == 0 || strcmp(ext, ".WAV") == 0) {

                        char full_path[256];
                        strcpy(full_path, current_path);
                        strcat(full_path, "/");
                        strcat(full_path, finfo.fname);

                        queue_add(full_path);

                        if (strcmp(full_path, path) == 0) {
                            selected_track = track_index;
                        }
                        track_index++;
                    }
                }
                f_closedir(&dir);

                /* Play selected track */
                if (selected_track >= 0) {
                    player_play_track(selected_track);
                }
            }
        }
    }
}

/*
 * Initialize browse view
 */
void browse_view_init(void) {
    current_mode = BROWSE_MODE_FOLDERS;
    strcpy(current_path, "/music");
    browse_menu = NULL;
    item_labels = NULL;
    item_paths = NULL;
    item_count = 0;
}

/*
 * Set browse mode
 */
void browse_view_set_mode(int mode) {
    current_mode = (browse_mode_t)mode;
    strcpy(current_path, "/music");
    browse_view_refresh();
}

/*
 * Refresh browse view
 */
void browse_view_refresh(void) {
    /* Free previous items */
    free_items();

    /* Destroy previous menu */
    if (browse_menu) {
        menu_destroy(browse_menu);
        browse_menu = NULL;
    }

    /* Read directory */
    DIR dir;
    FILINFO fno;
    int capacity = 50;

    item_labels = (char**)heap_alloc(capacity * sizeof(char*));
    item_paths = (char**)heap_alloc(capacity * sizeof(char*));
    if (!item_labels || !item_paths) return;

    memset(item_labels, 0, capacity * sizeof(char*));
    memset(item_paths, 0, capacity * sizeof(char*));

    if (f_opendir(&dir, current_path) == FR_OK) {
        while (f_readdir(&dir, &fno) == FR_OK && fno.fname[0]) {
            if (fno.fname[0] == '.') continue;  /* Skip hidden */

            /* Filter by mode */
            int is_dir = (fno.fattrib & AM_DIR) != 0;
            int is_audio = 0;

            if (!is_dir) {
                int len = strlen(fno.fname);
                if (len >= 4) {
                    const char* ext = &fno.fname[len - 4];
                    is_audio = (strcmp(ext, ".mp3") == 0 || strcmp(ext, ".MP3") == 0 ||
                               strcmp(ext, "flac") == 0 || strcmp(ext, "FLAC") == 0 ||
                               strcmp(ext, ".wav") == 0 || strcmp(ext, ".WAV") == 0);
                }
            }

            if (!is_dir && !is_audio) continue;

            /* Expand arrays if needed */
            if (item_count >= capacity) {
                capacity *= 2;
                char** new_labels = (char**)heap_realloc(item_labels, capacity * sizeof(char*));
                char** new_paths = (char**)heap_realloc(item_paths, capacity * sizeof(char*));
                if (!new_labels || !new_paths) break;
                item_labels = new_labels;
                item_paths = new_paths;
            }

            /* Create label */
            int label_len = strlen(fno.fname) + 3;
            item_labels[item_count] = (char*)heap_alloc(label_len);
            if (item_labels[item_count]) {
                if (is_dir) {
                    item_labels[item_count][0] = '[';
                    strcpy(&item_labels[item_count][1], fno.fname);
                    strcat(item_labels[item_count], "]");
                } else {
                    strcpy(item_labels[item_count], fno.fname);
                    /* Remove extension */
                    int len = strlen(item_labels[item_count]);
                    for (int i = len - 1; i > 0; i--) {
                        if (item_labels[item_count][i] == '.') {
                            item_labels[item_count][i] = '\0';
                            break;
                        }
                    }
                }
            }

            /* Create full path */
            int path_len = strlen(current_path) + strlen(fno.fname) + 2;
            item_paths[item_count] = (char*)heap_alloc(path_len);
            if (item_paths[item_count]) {
                strcpy(item_paths[item_count], current_path);
                strcat(item_paths[item_count], "/");
                strcat(item_paths[item_count], fno.fname);
            }

            item_count++;
        }
        f_closedir(&dir);
    }

    /* Create menu */
    if (item_count > 0) {
        browse_menu = menu_create(current_path, (const char**)item_labels, item_count, on_item_selected);
        if (browse_menu) {
            /* Set data pointers */
            for (int i = 0; i < item_count; i++) {
                browse_menu->items[i].data = (void*)(intptr_t)i;
            }
            menu_set(browse_menu);
        }
    }
}

/*
 * Go up one directory
 */
void browse_view_go_up(void) {
    /* Find last slash */
    int len = strlen(current_path);
    for (int i = len - 1; i > 0; i--) {
        if (current_path[i] == '/') {
            current_path[i] = '\0';
            browse_view_refresh();
            return;
        }
    }
}

/*
 * Handle button press
 */
void browse_view_handle_button(int button) {
    switch (button) {
        case BUTTON_BACK:
            if (strcmp(current_path, "/music") != 0) {
                browse_view_go_up();
            }
            break;

        default:
            menu_handle_button(button);
            break;
    }
}

/*
 * Draw browse view
 */
void browse_view_draw(void) {
    menu_draw();
}

/*
 * Get current path
 */
const char* browse_view_get_path(void) {
    return current_path;
}

/*
 * Cleanup
 */
void browse_view_cleanup(void) {
    free_items();
    if (browse_menu) {
        menu_destroy(browse_menu);
        browse_menu = NULL;
    }
}
