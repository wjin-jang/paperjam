/*
 * PaperJam Bare-Metal OS - Playback Engine Header
 */

#ifndef PLAYBACK_H
#define PLAYBACK_H

#include "hal/bcm2837.h"
#include "decoder.h"

/* Playback state */
typedef enum {
    PLAYBACK_STOPPED = 0,
    PLAYBACK_LOADED,
    PLAYBACK_PLAYING,
    PLAYBACK_PAUSED,
    PLAYBACK_FINISHED,
    PLAYBACK_ERROR
} playback_state_t;

/* Callback type */
typedef void (*playback_callback_t)(void);

/* Function prototypes */
void playback_init(void);
int  playback_load(const char* path);
void playback_play(void);
void playback_pause(void);
void playback_toggle(void);
void playback_stop(void);
void playback_seek_ms(u32 position_ms);
void playback_seek(u32 position_sec);
void playback_seek_relative(int delta_sec);
u32  playback_get_position_ms(void);
u32  playback_get_position(void);
u32  playback_get_duration_ms(void);
u32  playback_get_duration(void);
playback_state_t playback_get_state(void);
int  playback_is_playing(void);
int  playback_get_metadata(audio_metadata_t* meta);
void playback_set_track_end_callback(playback_callback_t callback);
void playback_set_error_callback(playback_callback_t callback);
void playback_update(void);
int  playback_get_progress(void);
void playback_format_time(u32 seconds, char* buf, int buflen);

#endif /* PLAYBACK_H */
