/*
 * PaperJam Bare-Metal OS - Player Header
 */

#ifndef PLAYER_H
#define PLAYER_H

#include "hal/bcm2837.h"

/* Player states */
typedef enum {
    PLAYER_STOPPED,
    PLAYER_PLAYING,
    PLAYER_PAUSED,
    PLAYER_ERROR
} player_state_t;

/* Repeat modes */
typedef enum {
    REPEAT_NONE,
    REPEAT_ALL,
    REPEAT_ONE
} repeat_mode_t;

/* Function prototypes */
void player_init(void);
int  player_play_file(const char* path);
int  player_play_track(int index);
void player_toggle(void);
void player_stop(void);
void player_next(void);
void player_prev(void);
void player_seek_forward(int seconds);
void player_seek_backward(int seconds);
player_state_t player_get_state(void);
int  player_get_current_track(void);
void player_set_repeat(repeat_mode_t mode);
repeat_mode_t player_get_repeat(void);
void player_cycle_repeat(void);
void player_set_shuffle(int enabled);
int  player_get_shuffle(void);
void player_toggle_shuffle(void);
void player_set_volume(int volume);
int  player_get_volume(void);
void player_adjust_volume(int delta);
void player_on_track_end(void);
void player_update(void);

#endif /* PLAYER_H */
