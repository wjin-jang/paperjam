/*
 * PaperJam Bare-Metal OS - Settings System
 *
 * Persists user preferences to /data/settings.dat
 */

#include "hal/bcm2837.h"
#include "settings.h"
#include "lib/fatfs/ff.h"
#include "sys/heap.h"

/* Settings file path */
#define SETTINGS_FILE   "/data/settings.dat"

/* Settings magic number for validation */
#define SETTINGS_MAGIC  0x504A5354  /* "PJST" */
#define SETTINGS_VERSION 1

/* Current settings */
static settings_t current_settings;
static int settings_loaded = 0;

/* Default settings */
static const settings_t default_settings = {
    .magic = SETTINGS_MAGIC,
    .version = SETTINGS_VERSION,
    .volume = 80,
    .repeat_mode = 0,      /* REPEAT_NONE */
    .shuffle = 0,
    .screensaver_timeout = 60,  /* 60 seconds */
    .display_brightness = 100,
    .show_remaining_time = 0,
    .auto_play = 1,
    .resume_playback = 1,
    .last_track_index = 0,
    .last_position = 0,
    .eq_bass = 0,
    .eq_treble = 0,
    .reserved = {0}
};

/*
 * Initialize settings system
 */
void settings_init(void) {
    memcpy(&current_settings, &default_settings, sizeof(settings_t));
    settings_loaded = 0;
}

/*
 * Load settings from file
 */
int settings_load(void) {
    FIL file;

    if (f_open(&file, SETTINGS_FILE, FA_READ) != FR_OK) {
        /* File doesn't exist, use defaults */
        settings_init();
        return -1;
    }

    UINT br;
    settings_t loaded;

    if (f_read(&file, &loaded, sizeof(settings_t), &br) != FR_OK ||
        br != sizeof(settings_t)) {
        f_close(&file);
        settings_init();
        return -2;
    }

    f_close(&file);

    /* Validate magic and version */
    if (loaded.magic != SETTINGS_MAGIC) {
        settings_init();
        return -3;
    }

    /* Handle version migration if needed */
    if (loaded.version != SETTINGS_VERSION) {
        /* For now, just use what we can */
    }

    /* Validate ranges */
    if (loaded.volume > 100) loaded.volume = 100;
    if (loaded.repeat_mode > 2) loaded.repeat_mode = 0;
    if (loaded.screensaver_timeout > 600) loaded.screensaver_timeout = 60;

    memcpy(&current_settings, &loaded, sizeof(settings_t));
    current_settings.magic = SETTINGS_MAGIC;
    current_settings.version = SETTINGS_VERSION;

    settings_loaded = 1;
    return 0;
}

/*
 * Save settings to file
 */
int settings_save(void) {
    /* Ensure data directory exists */
    f_mkdir("/data");

    FIL file;
    if (f_open(&file, SETTINGS_FILE, FA_WRITE | FA_CREATE_ALWAYS) != FR_OK) {
        return -1;
    }

    UINT bw;
    if (f_write(&file, &current_settings, sizeof(settings_t), &bw) != FR_OK ||
        bw != sizeof(settings_t)) {
        f_close(&file);
        return -2;
    }

    f_close(&file);
    return 0;
}

/*
 * Reset to defaults
 */
void settings_reset(void) {
    memcpy(&current_settings, &default_settings, sizeof(settings_t));
    settings_save();
}

/*
 * Get settings pointer
 */
settings_t* settings_get(void) {
    return &current_settings;
}

/*
 * Volume settings
 */
int settings_get_volume(void) {
    return current_settings.volume;
}

void settings_set_volume(int volume) {
    if (volume < 0) volume = 0;
    if (volume > 100) volume = 100;
    current_settings.volume = volume;
}

/*
 * Repeat mode
 */
int settings_get_repeat_mode(void) {
    return current_settings.repeat_mode;
}

void settings_set_repeat_mode(int mode) {
    if (mode < 0) mode = 0;
    if (mode > 2) mode = 2;
    current_settings.repeat_mode = mode;
}

/*
 * Shuffle
 */
int settings_get_shuffle(void) {
    return current_settings.shuffle;
}

void settings_set_shuffle(int enabled) {
    current_settings.shuffle = enabled ? 1 : 0;
}

/*
 * Screensaver timeout
 */
int settings_get_screensaver_timeout(void) {
    return current_settings.screensaver_timeout;
}

void settings_set_screensaver_timeout(int seconds) {
    if (seconds < 10) seconds = 10;
    if (seconds > 600) seconds = 600;
    current_settings.screensaver_timeout = seconds;
}

/*
 * Auto-play on boot
 */
int settings_get_auto_play(void) {
    return current_settings.auto_play;
}

void settings_set_auto_play(int enabled) {
    current_settings.auto_play = enabled ? 1 : 0;
}

/*
 * Resume playback position
 */
int settings_get_resume_playback(void) {
    return current_settings.resume_playback;
}

void settings_set_resume_playback(int enabled) {
    current_settings.resume_playback = enabled ? 1 : 0;
}

/*
 * Last playback position (for resume)
 */
void settings_set_last_position(int track_index, u32 position_ms) {
    current_settings.last_track_index = track_index;
    current_settings.last_position = position_ms;
}

void settings_get_last_position(int* track_index, u32* position_ms) {
    if (track_index) *track_index = current_settings.last_track_index;
    if (position_ms) *position_ms = current_settings.last_position;
}

/*
 * Check if settings have been loaded
 */
int settings_is_loaded(void) {
    return settings_loaded;
}
