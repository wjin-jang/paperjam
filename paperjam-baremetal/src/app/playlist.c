/*
 * PaperJam Bare-Metal OS - Queue and Playlist Management
 */

#include "hal/bcm2837.h"
#include "playlist.h"
#include "library.h"
#include "fatfs/ff.h"
#include "sys/heap.h"

/* Queue configuration */
#define MAX_QUEUE_SIZE      500
#define MAX_PATH_LENGTH     256

/* Queue entry */
typedef struct {
    char path[MAX_PATH_LENGTH];
} queue_entry_t;

/* Queue state */
static queue_entry_t* queue = NULL;
static int queue_count_val = 0;
static int queue_capacity = 0;
static int current_index = 0;

/*
 * Initialize queue
 */
void queue_init(void) {
    queue = NULL;
    queue_count_val = 0;
    queue_capacity = 0;
}

/*
 * Clear queue
 */
void queue_clear(void) {
    queue_count_val = 0;
    current_index = 0;
}

/*
 * Add to queue
 */
int queue_add(const char* path) {
    if (queue_count_val >= queue_capacity) {
        int new_capacity = queue_capacity ? queue_capacity * 2 : 50;
        if (new_capacity > MAX_QUEUE_SIZE) {
            new_capacity = MAX_QUEUE_SIZE;
        }
        if (new_capacity <= queue_capacity) {
            return -1;
        }

        queue_entry_t* new_queue = (queue_entry_t*)heap_realloc(
            queue, new_capacity * sizeof(queue_entry_t));
        if (!new_queue) return -1;

        queue = new_queue;
        queue_capacity = new_capacity;
    }

    int len = strlen(path);
    if (len >= MAX_PATH_LENGTH) len = MAX_PATH_LENGTH - 1;
    memcpy(queue[queue_count_val].path, path, len);
    queue[queue_count_val].path[len] = '\0';

    queue_count_val++;
    return queue_count_val - 1;
}

/*
 * Insert into queue at specific position
 */
int queue_insert(int index, const char* path) {
    if (index < 0) index = 0;
    if (index > queue_count_val) index = queue_count_val;

    /* Ensure capacity */
    if (queue_count_val >= queue_capacity) {
        int new_capacity = queue_capacity ? queue_capacity * 2 : 50;
        if (new_capacity > MAX_QUEUE_SIZE) {
            new_capacity = MAX_QUEUE_SIZE;
        }
        if (new_capacity <= queue_capacity) {
            return -1;
        }

        queue_entry_t* new_queue = (queue_entry_t*)heap_realloc(
            queue, new_capacity * sizeof(queue_entry_t));
        if (!new_queue) return -1;

        queue = new_queue;
        queue_capacity = new_capacity;
    }

    /* Shift entries to make room */
    for (int i = queue_count_val; i > index; i--) {
        memcpy(&queue[i], &queue[i - 1], sizeof(queue_entry_t));
    }

    /* Insert new entry */
    int len = strlen(path);
    if (len >= MAX_PATH_LENGTH) len = MAX_PATH_LENGTH - 1;
    memcpy(queue[index].path, path, len);
    queue[index].path[len] = '\0';

    queue_count_val++;

    /* Adjust current index if needed */
    if (index <= current_index && current_index < queue_count_val - 1) {
        current_index++;
    }

    return index;
}

/*
 * Add to queue after current track
 */
int queue_add_next(const char* path) {
    return queue_insert(current_index + 1, path);
}

/*
 * Remove from queue
 */
int queue_remove(int index) {
    if (index < 0 || index >= queue_count_val) return -1;

    /* Shift entries */
    for (int i = index; i < queue_count_val - 1; i++) {
        memcpy(&queue[i], &queue[i + 1], sizeof(queue_entry_t));
    }

    queue_count_val--;

    /* Adjust current index */
    if (index < current_index) {
        current_index--;
    } else if (index == current_index && current_index >= queue_count_val) {
        current_index = queue_count_val > 0 ? queue_count_val - 1 : 0;
    }

    return 0;
}

/*
 * Move queue item
 */
int queue_move(int from, int to) {
    if (from < 0 || from >= queue_count_val) return -1;
    if (to < 0 || to >= queue_count_val) return -1;
    if (from == to) return 0;

    queue_entry_t temp;
    memcpy(&temp, &queue[from], sizeof(queue_entry_t));

    if (from < to) {
        for (int i = from; i < to; i++) {
            memcpy(&queue[i], &queue[i + 1], sizeof(queue_entry_t));
        }
    } else {
        for (int i = from; i > to; i--) {
            memcpy(&queue[i], &queue[i - 1], sizeof(queue_entry_t));
        }
    }

    memcpy(&queue[to], &temp, sizeof(queue_entry_t));
    return 0;
}

/*
 * Get queue count
 */
int queue_count(void) {
    return queue_count_val;
}

/*
 * Get queue path
 */
const char* queue_get_path(int index) {
    if (index < 0 || index >= queue_count_val) return NULL;
    return queue[index].path;
}

/*
 * Alias for queue_get_path
 */
const char* queue_get(int index) {
    return queue_get_path(index);
}

/*
 * Get current track index
 */
int queue_get_current(void) {
    return current_index;
}

/*
 * Set current track index
 */
void queue_set_current(int index) {
    if (index >= 0 && index < queue_count_val) {
        current_index = index;
    }
}

/*
 * Add all from library
 */
void queue_add_all(void) {
    queue_clear();
    int count = library_count_entries();
    for (int i = 0; i < count && queue_count_val < MAX_QUEUE_SIZE; i++) {
        queue_add(library_get_path(i));
    }
}

/*
 * Shuffle queue
 */
void queue_shuffle(void) {
    if (queue_count_val < 2) return;

    /* Fisher-Yates shuffle */
    for (int i = queue_count_val - 1; i > 0; i--) {
        /* Simple pseudo-random using timer */
        int j = timer_get_ticks() % (i + 1);
        if (i != j) {
            queue_entry_t temp;
            memcpy(&temp, &queue[i], sizeof(queue_entry_t));
            memcpy(&queue[i], &queue[j], sizeof(queue_entry_t));
            memcpy(&queue[j], &temp, sizeof(queue_entry_t));
        }
    }
}

/*
 * Save queue to file
 */
int queue_save(const char* filename) {
    FIL file;
    if (f_open(&file, filename, FA_WRITE | FA_CREATE_ALWAYS) != FR_OK) {
        return -1;
    }

    UINT bw;
    for (int i = 0; i < queue_count_val; i++) {
        f_write(&file, queue[i].path, strlen(queue[i].path), &bw);
        f_write(&file, "\n", 1, &bw);
    }

    f_close(&file);
    return 0;
}

/*
 * Load queue from file
 */
int queue_load(const char* filename) {
    FIL file;
    if (f_open(&file, filename, FA_READ) != FR_OK) {
        return -1;
    }

    queue_clear();

    char line[MAX_PATH_LENGTH];
    while (f_gets(line, sizeof(line), &file)) {
        /* Remove newline */
        int len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) {
            line[--len] = '\0';
        }
        if (len > 0) {
            queue_add(line);
        }
    }

    f_close(&file);
    return 0;
}

/*
 * Free queue
 */
void queue_free(void) {
    if (queue) {
        heap_free(queue);
        queue = NULL;
    }
    queue_count_val = 0;
    queue_capacity = 0;
}
