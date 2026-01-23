/*
 * PaperJam Bare-Metal OS - Audio Driver Header
 */

#ifndef AUDIO_H
#define AUDIO_H

#include "hal/bcm2837.h"

/* Default audio settings */
#define AUDIO_DEFAULT_SAMPLE_RATE   44100
#define AUDIO_DEFAULT_VOLUME        80

/* Function prototypes */
void audio_init(void);
void audio_set_sample_rate(u32 rate);
u32  audio_get_sample_rate(void);
u32  audio_buffer_free(void);
u32  audio_buffer_available(void);
u32  audio_write(const i16* samples, u32 count);
u32  audio_write_stereo(const i16* samples, u32 frames);
void audio_start(void);
void audio_stop(void);
void audio_pause(void);
void audio_resume(void);
void audio_clear(void);
int  audio_is_playing(void);
void audio_set_volume(int volume);
int  audio_get_volume(void);
void audio_adjust_volume(int delta);
void audio_set_mute(int mute);
int  audio_is_muted(void);
void audio_toggle_mute(void);
void audio_test_tone(u32 freq, u32 duration_ms);
void audio_wait_buffer(u32 threshold);
void audio_drain(void);

#endif /* AUDIO_H */
