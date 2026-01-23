/*
 * PaperJam Bare-Metal OS - Audio Output Driver
 *
 * High-level audio interface using PWM output
 */

#include "hal/bcm2837.h"
#include "hal/pwm.h"
#include "hal/timer.h"
#include "hal/irq.h"
#include "audio.h"
#include "sys/heap.h"

/* Audio state */
static int audio_initialized = 0;
static int audio_volume = 80;       /* 0-100 */
static int audio_muted = 0;

/* Ring buffer for audio data */
#define AUDIO_RING_BUFFER_SIZE  8192
static i16 audio_ring_buffer[AUDIO_RING_BUFFER_SIZE];
static volatile u32 ring_read_pos = 0;
static volatile u32 ring_write_pos = 0;

/* Sample rate and playback state */
static u32 audio_sample_rate = 44100;
static volatile int audio_playing = 0;

/* Timer tick counter for audio timing */
static u64 audio_tick_counter = 0;
static u64 audio_last_tick = 0;

/*
 * Apply volume to sample
 */
static i16 apply_volume(i16 sample) {
    if (audio_muted) return 0;
    return (i16)((i32)sample * audio_volume / 100);
}

/*
 * Timer interrupt handler for audio output
 */
static void audio_timer_handler(void) {
    if (!audio_playing) {
        timer_advance_periodic(TIMER_CHANNEL_1, 1000);
        return;
    }

    /* Calculate how many samples to output based on elapsed time */
    u64 now = timer_get_us();
    u64 elapsed = now - audio_last_tick;

    /* Output samples at correct rate */
    u32 samples_needed = (u32)(elapsed * audio_sample_rate / 1000000);
    audio_last_tick = now - (elapsed % (1000000 / audio_sample_rate));

    for (u32 i = 0; i < samples_needed && i < 10; i++) {
        if (ring_read_pos != ring_write_pos) {
            i16 sample = audio_ring_buffer[ring_read_pos];
            sample = apply_volume(sample);
            pwm_audio_write(&sample, 1);
            ring_read_pos = (ring_read_pos + 1) % AUDIO_RING_BUFFER_SIZE;
        }
    }

    pwm_audio_tick();
    timer_advance_periodic(TIMER_CHANNEL_1, 1000);  /* 1ms ticks */
}

/*
 * Initialize audio subsystem
 */
void audio_init(void) {
    pwm_init();

    ring_read_pos = 0;
    ring_write_pos = 0;
    audio_playing = 0;

    /* Set up timer interrupt for audio */
    irq_register_handler(IRQ_TIMER1, audio_timer_handler);
    irq_setup_timer();

    audio_initialized = 1;
}

/*
 * Set audio sample rate
 */
void audio_set_sample_rate(u32 rate) {
    audio_sample_rate = rate;
}

/*
 * Get audio sample rate
 */
u32 audio_get_sample_rate(void) {
    return audio_sample_rate;
}

/*
 * Get number of samples that can be written
 */
u32 audio_buffer_free(void) {
    u32 used = (ring_write_pos - ring_read_pos) % AUDIO_RING_BUFFER_SIZE;
    return AUDIO_RING_BUFFER_SIZE - used - 1;
}

/*
 * Get number of samples available to play
 */
u32 audio_buffer_available(void) {
    return (ring_write_pos - ring_read_pos) % AUDIO_RING_BUFFER_SIZE;
}

/*
 * Write samples to audio buffer
 * Returns number of samples written
 */
u32 audio_write(const i16* samples, u32 count) {
    u32 free = audio_buffer_free();
    if (count > free) count = free;

    for (u32 i = 0; i < count; i++) {
        audio_ring_buffer[ring_write_pos] = samples[i];
        ring_write_pos = (ring_write_pos + 1) % AUDIO_RING_BUFFER_SIZE;
    }

    return count;
}

/*
 * Write stereo samples (converts to mono by averaging)
 */
u32 audio_write_stereo(const i16* samples, u32 frames) {
    u32 free = audio_buffer_free();
    if (frames > free) frames = free;

    for (u32 i = 0; i < frames; i++) {
        i32 left = samples[i * 2];
        i32 right = samples[i * 2 + 1];
        audio_ring_buffer[ring_write_pos] = (i16)((left + right) / 2);
        ring_write_pos = (ring_write_pos + 1) % AUDIO_RING_BUFFER_SIZE;
    }

    return frames;
}

/*
 * Start audio playback
 */
void audio_start(void) {
    if (!audio_initialized) return;
    audio_last_tick = timer_get_us();
    pwm_audio_start();
    audio_playing = 1;
}

/*
 * Stop audio playback
 */
void audio_stop(void) {
    audio_playing = 0;
    pwm_audio_stop();
}

/*
 * Pause audio playback
 */
void audio_pause(void) {
    audio_playing = 0;
}

/*
 * Resume audio playback
 */
void audio_resume(void) {
    audio_last_tick = timer_get_us();
    audio_playing = 1;
}

/*
 * Clear audio buffer
 */
void audio_clear(void) {
    irq_global_disable();
    ring_read_pos = 0;
    ring_write_pos = 0;
    pwm_audio_clear();
    irq_global_enable();
}

/*
 * Check if audio is playing
 */
int audio_is_playing(void) {
    return audio_playing;
}

/*
 * Set volume (0-100)
 */
void audio_set_volume(int volume) {
    if (volume < 0) volume = 0;
    if (volume > 100) volume = 100;
    audio_volume = volume;
    pwm_set_volume(volume);
}

/*
 * Get volume
 */
int audio_get_volume(void) {
    return audio_volume;
}

/*
 * Adjust volume
 */
void audio_adjust_volume(int delta) {
    audio_set_volume(audio_volume + delta);
}

/*
 * Mute/unmute
 */
void audio_set_mute(int mute) {
    audio_muted = mute;
}

int audio_is_muted(void) {
    return audio_muted;
}

void audio_toggle_mute(void) {
    audio_muted = !audio_muted;
}

/*
 * Play a test tone
 */
void audio_test_tone(u32 freq, u32 duration_ms) {
    pwm_play_tone(freq, duration_ms);
}

/*
 * Wait until buffer is below threshold
 */
void audio_wait_buffer(u32 threshold) {
    while (audio_buffer_available() > threshold) {
        timer_delay_ms(1);
    }
}

/*
 * Drain audio buffer (wait for playback to complete)
 */
void audio_drain(void) {
    while (audio_buffer_available() > 0 && audio_playing) {
        timer_delay_ms(10);
    }
    timer_delay_ms(100);  /* Extra delay for PWM buffer */
}
