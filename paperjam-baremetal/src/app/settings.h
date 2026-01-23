/*
 * PaperJam Bare-Metal OS - Settings Header
 */

#ifndef SETTINGS_H
#define SETTINGS_H

#include "hal/bcm2837.h"

/* Settings structure - stored on disk */
typedef struct __attribute__((packed)) {
    u32 magic;
    u32 version;

    /* Audio settings */
    u8 volume;              /* 0-100 */
    u8 repeat_mode;         /* 0=none, 1=all, 2=one */
    u8 shuffle;             /* 0 or 1 */

    /* Display settings */
    u8 screensaver_timeout; /* seconds */
    u8 display_brightness;  /* 0-100 (not used for e-paper) */
    u8 show_remaining_time; /* 0=elapsed, 1=remaining */

    /* Playback settings */
    u8 auto_play;           /* Start playing on boot */
    u8 resume_playback;     /* Resume from last position */

    /* Resume state */
    i32 last_track_index;
    u32 last_position;      /* Position in ms */

    /* EQ settings (future) */
    i8 eq_bass;             /* -10 to +10 */
    i8 eq_treble;           /* -10 to +10 */

    /* Reserved for future use */
    u8 reserved[32];
} settings_t;

/* Function prototypes */
void settings_init(void);
int  settings_load(void);
int  settings_save(void);
void settings_reset(void);
settings_t* settings_get(void);

/* Convenience accessors */
int  settings_get_volume(void);
void settings_set_volume(int volume);
int  settings_get_repeat_mode(void);
void settings_set_repeat_mode(int mode);
int  settings_get_shuffle(void);
void settings_set_shuffle(int enabled);
int  settings_get_screensaver_timeout(void);
void settings_set_screensaver_timeout(int seconds);
int  settings_get_auto_play(void);
void settings_set_auto_play(int enabled);
int  settings_get_resume_playback(void);
void settings_set_resume_playback(int enabled);
void settings_set_last_position(int track_index, u32 position_ms);
void settings_get_last_position(int* track_index, u32* position_ms);
int  settings_is_loaded(void);

#endif /* SETTINGS_H */
