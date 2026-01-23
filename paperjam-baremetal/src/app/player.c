/*
 * PaperJam Bare-Metal OS - Music Player Logic
 */

#include "hal/bcm2837.h"
#include "player.h"
#include "library.h"
#include "playlist.h"
#include "audio/playback.h"
#include "drivers/audio.h"
#include "ui/renderer.h"
#include "sys/heap.h"

/* Player state */
static player_state_t player_state = PLAYER_STOPPED;
static repeat_mode_t repeat_mode = REPEAT_NONE;
static int shuffle_enabled = 0;
static int current_track = -1;

/*
 * Initialize player
 */
void player_init(void) {
    playback_init();
    player_state = PLAYER_STOPPED;
    current_track = -1;
    repeat_mode = REPEAT_NONE;
    shuffle_enabled = 0;

    /* Set callbacks */
    playback_set_track_end_callback(player_on_track_end);
}

/*
 * Play a specific track by path
 */
int player_play_file(const char* path) {
    if (playback_load(path) < 0) {
        player_state = PLAYER_ERROR;
        return -1;
    }

    playback_play();
    player_state = PLAYER_PLAYING;
    return 0;
}

/*
 * Play track from queue
 */
int player_play_track(int index) {
    const char* path = queue_get_path(index);
    if (!path) return -1;

    if (player_play_file(path) < 0) {
        return -1;
    }

    current_track = index;
    return 0;
}

/*
 * Play/pause toggle
 */
void player_toggle(void) {
    switch (player_state) {
        case PLAYER_PLAYING:
            playback_pause();
            player_state = PLAYER_PAUSED;
            break;

        case PLAYER_PAUSED:
            playback_resume();
            player_state = PLAYER_PLAYING;
            break;

        case PLAYER_STOPPED:
            if (current_track >= 0) {
                player_play_track(current_track);
            } else if (queue_count() > 0) {
                player_play_track(0);
            }
            break;

        default:
            break;
    }
}

/*
 * Stop playback
 */
void player_stop(void) {
    playback_stop();
    player_state = PLAYER_STOPPED;
}

/*
 * Next track
 */
void player_next(void) {
    int count = queue_count();
    if (count == 0) return;

    int next = current_track + 1;

    if (shuffle_enabled) {
        /* Simple random - could be improved */
        next = (current_track + 7) % count;
    }

    if (next >= count) {
        if (repeat_mode == REPEAT_ALL) {
            next = 0;
        } else {
            player_stop();
            return;
        }
    }

    player_play_track(next);
}

/*
 * Previous track
 */
void player_prev(void) {
    int count = queue_count();
    if (count == 0) return;

    /* If more than 3 seconds in, restart current track */
    if (playback_get_position() > 3) {
        playback_seek(0);
        return;
    }

    int prev = current_track - 1;

    if (prev < 0) {
        if (repeat_mode == REPEAT_ALL) {
            prev = count - 1;
        } else {
            prev = 0;
        }
    }

    player_play_track(prev);
}

/*
 * Seek forward
 */
void player_seek_forward(int seconds) {
    playback_seek_relative(seconds);
}

/*
 * Seek backward
 */
void player_seek_backward(int seconds) {
    playback_seek_relative(-seconds);
}

/*
 * Get player state
 */
player_state_t player_get_state(void) {
    return player_state;
}

/*
 * Get current track index
 */
int player_get_current_track(void) {
    return current_track;
}

/*
 * Set repeat mode
 */
void player_set_repeat(repeat_mode_t mode) {
    repeat_mode = mode;
}

/*
 * Get repeat mode
 */
repeat_mode_t player_get_repeat(void) {
    return repeat_mode;
}

/*
 * Cycle repeat mode
 */
void player_cycle_repeat(void) {
    repeat_mode = (repeat_mode + 1) % 3;
}

/*
 * Set shuffle
 */
void player_set_shuffle(int enabled) {
    shuffle_enabled = enabled;
}

/*
 * Get shuffle
 */
int player_get_shuffle(void) {
    return shuffle_enabled;
}

/*
 * Toggle shuffle
 */
void player_toggle_shuffle(void) {
    shuffle_enabled = !shuffle_enabled;
}

/*
 * Volume control
 */
void player_set_volume(int volume) {
    audio_set_volume(volume);
}

int player_get_volume(void) {
    return audio_get_volume();
}

void player_adjust_volume(int delta) {
    audio_adjust_volume(delta);
}

/*
 * Callback when track ends
 */
void player_on_track_end(void) {
    if (repeat_mode == REPEAT_ONE) {
        playback_seek(0);
        playback_play();
    } else {
        player_next();
    }
}

/*
 * Update (call from main loop)
 */
void player_update(void) {
    playback_update();

    /* Update state based on playback */
    playback_state_t pb_state = playback_get_state();
    switch (pb_state) {
        case PLAYBACK_PLAYING:
            player_state = PLAYER_PLAYING;
            break;
        case PLAYBACK_PAUSED:
            player_state = PLAYER_PAUSED;
            break;
        case PLAYBACK_STOPPED:
        case PLAYBACK_FINISHED:
            if (player_state == PLAYER_PLAYING) {
                player_on_track_end();
            }
            break;
        case PLAYBACK_ERROR:
            player_state = PLAYER_ERROR;
            break;
        default:
            break;
    }
}
