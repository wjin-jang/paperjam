/*
 * PaperJam Bare-Metal OS - PWM Audio Driver Header
 */

#ifndef PWM_H
#define PWM_H

#include "bcm2837.h"

/* Audio constants */
#define PWM_AUDIO_SAMPLE_RATE   44100
#define PWM_AUDIO_BUFFER_SIZE   4096

/* Function prototypes */
void pwm_init(void);
void pwm_set_duty(u32 duty);
u32  pwm_audio_buffer_available(void);
u32  pwm_audio_buffer_free(void);
u32  pwm_audio_write(const i16* samples, u32 count);
void pwm_audio_tick(void);
void pwm_audio_start(void);
void pwm_audio_stop(void);
void pwm_audio_clear(void);
bool pwm_audio_is_playing(void);
void pwm_set_volume(u32 volume);
u32  pwm_get_volume(void);
void pwm_play_tone(u32 freq, u32 duration_ms);

#endif /* PWM_H */
