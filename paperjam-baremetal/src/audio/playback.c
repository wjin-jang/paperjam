/*
 * PaperJam Bare-Metal OS - Audio Playback Engine
 *
 * Manages decoding and playback with ring buffer
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "drivers/audio.h"
#include "decoder.h"
#include "playback.h"
#include "sys/heap.h"
#include "lib/fatfs/ff.h"

/* Playback state */
static decoder_context_t decoder;
static FIL current_file;
static playback_state_t playback_state = PLAYBACK_STOPPED;
static int file_open = 0;

/* Decode buffer */
#define DECODE_BUFFER_SIZE  4096
static i16 decode_buffer[DECODE_BUFFER_SIZE];

/* Callbacks */
static playback_callback_t on_track_end = NULL;
static playback_callback_t on_error = NULL;

/*
 * Initialize playback engine
 */
void playback_init(void) {
    memset(&decoder, 0, sizeof(decoder));
    memset(&current_file, 0, sizeof(current_file));
    playback_state = PLAYBACK_STOPPED;
    file_open = 0;
}

/*
 * Load a file for playback
 */
int playback_load(const char* path) {
    /* Stop current playback */
    playback_stop();

    /* Detect format */
    audio_format_t format = decoder_detect_format(path);
    if (format == AUDIO_FORMAT_UNKNOWN) {
        return -1;
    }

    /* Open file */
    FRESULT res = f_open(&current_file, path, FA_READ);
    if (res != FR_OK) {
        return -2;
    }
    file_open = 1;

    /* Initialize decoder */
    if (decoder_init(&decoder, path) < 0) {
        f_close(&current_file);
        file_open = 0;
        return -3;
    }

    /* Open decoder on file */
    if (decoder.ops && decoder.ops->open(&decoder, &current_file) < 0) {
        f_close(&current_file);
        file_open = 0;
        return -4;
    }

    /* Configure audio output */
    audio_set_sample_rate(decoder.sample_rate);
    audio_clear();

    playback_state = PLAYBACK_LOADED;
    return 0;
}

/*
 * Start or resume playback
 */
void playback_play(void) {
    if (playback_state == PLAYBACK_LOADED ||
        playback_state == PLAYBACK_PAUSED) {
        audio_start();
        playback_state = PLAYBACK_PLAYING;
    }
}

/*
 * Pause playback
 */
void playback_pause(void) {
    if (playback_state == PLAYBACK_PLAYING) {
        audio_pause();
        playback_state = PLAYBACK_PAUSED;
    }
}

/*
 * Toggle play/pause
 */
void playback_toggle(void) {
    if (playback_state == PLAYBACK_PLAYING) {
        playback_pause();
    } else {
        playback_play();
    }
}

/*
 * Stop playback
 */
void playback_stop(void) {
    audio_stop();
    audio_clear();

    if (decoder.ops && decoder.ops->close) {
        decoder.ops->close(&decoder);
    }

    if (file_open) {
        f_close(&current_file);
        file_open = 0;
    }

    decoder_cleanup(&decoder);
    playback_state = PLAYBACK_STOPPED;
}

/*
 * Seek to position (in milliseconds)
 */
void playback_seek_ms(u32 position_ms) {
    if (!decoder.ops || !decoder.ops->seek) return;

    u32 sample_pos = (u64)position_ms * decoder.sample_rate / 1000;
    decoder.ops->seek(&decoder, sample_pos);
    audio_clear();
}

/*
 * Seek to position (in seconds)
 */
void playback_seek(u32 position_sec) {
    playback_seek_ms(position_sec * 1000);
}

/*
 * Seek relative (delta in seconds)
 */
void playback_seek_relative(int delta_sec) {
    u32 current_ms = playback_get_position_ms();
    i32 new_ms = (i32)current_ms + delta_sec * 1000;
    if (new_ms < 0) new_ms = 0;
    playback_seek_ms((u32)new_ms);
}

/*
 * Get current position in milliseconds
 */
u32 playback_get_position_ms(void) {
    if (!decoder.ops || !decoder.ops->get_position) return 0;
    u32 samples = decoder.ops->get_position(&decoder);
    return (u64)samples * 1000 / decoder.sample_rate;
}

/*
 * Get current position in seconds
 */
u32 playback_get_position(void) {
    return playback_get_position_ms() / 1000;
}

/*
 * Get total duration in milliseconds
 */
u32 playback_get_duration_ms(void) {
    if (!decoder.ops || !decoder.ops->get_total_samples) return 0;
    u32 samples = decoder.ops->get_total_samples(&decoder);
    return (u64)samples * 1000 / decoder.sample_rate;
}

/*
 * Get total duration in seconds
 */
u32 playback_get_duration(void) {
    return playback_get_duration_ms() / 1000;
}

/*
 * Get playback state
 */
playback_state_t playback_get_state(void) {
    return playback_state;
}

/*
 * Check if playing
 */
int playback_is_playing(void) {
    return playback_state == PLAYBACK_PLAYING;
}

/*
 * Get metadata
 */
int playback_get_metadata(audio_metadata_t* meta) {
    if (!decoder.ops || !decoder.ops->get_metadata) return -1;
    return decoder.ops->get_metadata(&decoder, meta);
}

/*
 * Set callbacks
 */
void playback_set_track_end_callback(playback_callback_t callback) {
    on_track_end = callback;
}

void playback_set_error_callback(playback_callback_t callback) {
    on_error = callback;
}

/*
 * Update playback (call from main loop)
 * Decodes audio and feeds the audio buffer
 */
void playback_update(void) {
    if (playback_state != PLAYBACK_PLAYING) return;

    /* Fill audio buffer if there's room */
    while (audio_buffer_free() > DECODE_BUFFER_SIZE / 2) {
        int samples = 0;

        if (decoder.ops && decoder.ops->decode) {
            samples = decoder.ops->decode(&decoder, decode_buffer, DECODE_BUFFER_SIZE);
        }

        if (samples > 0) {
            /* Write to audio buffer */
            if (decoder.channels == 2) {
                audio_write_stereo(decode_buffer, samples / 2);
            } else {
                audio_write(decode_buffer, samples);
            }
        } else if (samples == 0) {
            /* End of file */
            playback_state = PLAYBACK_FINISHED;
            if (on_track_end) {
                on_track_end();
            }
            break;
        } else {
            /* Error */
            playback_state = PLAYBACK_ERROR;
            if (on_error) {
                on_error();
            }
            break;
        }
    }
}

/*
 * Get progress (0-100)
 */
int playback_get_progress(void) {
    u32 duration = playback_get_duration_ms();
    if (duration == 0) return 0;
    u32 position = playback_get_position_ms();
    return (int)((u64)position * 100 / duration);
}

/*
 * Format time as MM:SS string
 */
void playback_format_time(u32 seconds, char* buf, int buflen) {
    u32 mins = seconds / 60;
    u32 secs = seconds % 60;
    int i = 0;

    if (mins >= 10) buf[i++] = '0' + (mins / 10);
    buf[i++] = '0' + (mins % 10);
    buf[i++] = ':';
    buf[i++] = '0' + (secs / 10);
    buf[i++] = '0' + (secs % 10);
    buf[i] = '\0';
    (void)buflen;
}
