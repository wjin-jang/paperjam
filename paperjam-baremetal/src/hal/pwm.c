/*
 * PaperJam Bare-Metal OS - PWM Audio Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 *
 * GPIO 18: PWM0 output (ALT5)
 * Used for audio output at 44100Hz
 */

#include "bcm2837.h"
#include "gpio.h"
#include "pwm.h"
#include "timer.h"

/* Audio configuration */
#define AUDIO_SAMPLE_RATE   44100
#define PWM_RANGE           1024    /* 10-bit PWM resolution */
#define PWM_CLOCK_FREQ      (AUDIO_SAMPLE_RATE * PWM_RANGE)

/* Ring buffer for audio samples */
#define AUDIO_BUFFER_SIZE   4096
static u16 audio_buffer[AUDIO_BUFFER_SIZE];
static volatile u32 buffer_read_pos = 0;
static volatile u32 buffer_write_pos = 0;
static volatile bool audio_playing = false;

/*
 * Configure PWM clock
 */
static void pwm_set_clock(u32 freq) {
    /* Stop clock */
    *CM_PWMCTL = CM_PASSWORD | 0x01;
    timer_delay_us(100);

    /* Wait for clock to stop */
    while (*CM_PWMCTL & 0x80) {
        timer_delay_us(10);
    }

    /* Calculate divider: 500MHz / freq */
    /* Using PLLD (500MHz) as source */
    u32 divi = 500000000 / freq;
    u32 divf = ((500000000 % freq) * 4096) / freq;

    *CM_PWMDIV = CM_PASSWORD | (divi << 12) | divf;
    timer_delay_us(100);

    /* Start clock with PLLD source (6) */
    *CM_PWMCTL = CM_PASSWORD | 0x16;  /* Enable, PLLD */
    timer_delay_us(100);

    /* Wait for clock to stabilize */
    while (!(*CM_PWMCTL & 0x80)) {
        timer_delay_us(10);
    }
}

/*
 * Initialize PWM for audio output
 */
void pwm_init(void) {
    /* Configure GPIO 18 for PWM (ALT5) */
    gpio_set_function(18, GPIO_FUNC_ALT5);
    gpio_set_pull(18, GPIO_PULL_NONE);

    /* Disable PWM */
    *PWM_CTL = 0;
    timer_delay_us(100);

    /* Set up PWM clock for audio sample rate */
    pwm_set_clock(PWM_CLOCK_FREQ);

    /* Set PWM range (resolution) */
    *PWM_RNG1 = PWM_RANGE;
    timer_delay_us(100);

    /* Initialize data to midpoint (silence) */
    *PWM_DAT1 = PWM_RANGE / 2;

    /* Enable PWM in mark-space mode */
    *PWM_CTL = PWM_CTL_PWEN1 | PWM_CTL_MSEN1;
    timer_delay_us(100);

    /* Clear buffer */
    buffer_read_pos = 0;
    buffer_write_pos = 0;
    audio_playing = false;
}

/*
 * Set PWM duty cycle (0 to PWM_RANGE)
 */
void pwm_set_duty(u32 duty) {
    if (duty > PWM_RANGE) duty = PWM_RANGE;
    *PWM_DAT1 = duty;
}

/*
 * Convert signed 16-bit sample to PWM value
 */
static u32 sample_to_pwm(i16 sample) {
    /* Convert from -32768..32767 to 0..1023 */
    i32 val = ((i32)sample + 32768) * PWM_RANGE / 65536;
    if (val < 0) val = 0;
    if (val > (i32)PWM_RANGE - 1) val = PWM_RANGE - 1;
    return (u32)val;
}

/*
 * Get number of samples available in buffer
 */
u32 pwm_audio_buffer_available(void) {
    u32 write = buffer_write_pos;
    u32 read = buffer_read_pos;
    return (write - read) % AUDIO_BUFFER_SIZE;
}

/*
 * Get number of free samples in buffer
 */
u32 pwm_audio_buffer_free(void) {
    return AUDIO_BUFFER_SIZE - pwm_audio_buffer_available() - 1;
}

/*
 * Add samples to audio buffer
 * samples: array of signed 16-bit samples
 * count: number of samples
 * Returns: number of samples actually added
 */
u32 pwm_audio_write(const i16* samples, u32 count) {
    u32 free = pwm_audio_buffer_free();
    if (count > free) count = free;

    for (u32 i = 0; i < count; i++) {
        audio_buffer[buffer_write_pos] = sample_to_pwm(samples[i]);
        buffer_write_pos = (buffer_write_pos + 1) % AUDIO_BUFFER_SIZE;
    }

    return count;
}

/*
 * Audio tick - call this at AUDIO_SAMPLE_RATE (from timer interrupt)
 */
void pwm_audio_tick(void) {
    if (!audio_playing) return;

    if (buffer_read_pos != buffer_write_pos) {
        *PWM_DAT1 = audio_buffer[buffer_read_pos];
        buffer_read_pos = (buffer_read_pos + 1) % AUDIO_BUFFER_SIZE;
    } else {
        /* Buffer underrun - output silence */
        *PWM_DAT1 = PWM_RANGE / 2;
    }
}

/*
 * Start audio playback
 */
void pwm_audio_start(void) {
    audio_playing = true;
}

/*
 * Stop audio playback
 */
void pwm_audio_stop(void) {
    audio_playing = false;
    *PWM_DAT1 = PWM_RANGE / 2;  /* Silence */
}

/*
 * Clear audio buffer
 */
void pwm_audio_clear(void) {
    buffer_read_pos = 0;
    buffer_write_pos = 0;
}

/*
 * Check if audio is playing
 */
bool pwm_audio_is_playing(void) {
    return audio_playing;
}

/*
 * Set volume (0-100)
 */
static u32 current_volume = 100;

void pwm_set_volume(u32 volume) {
    if (volume > 100) volume = 100;
    current_volume = volume;
}

u32 pwm_get_volume(void) {
    return current_volume;
}

/*
 * Play a simple tone (for testing)
 * freq: frequency in Hz
 * duration_ms: duration in milliseconds
 */
void pwm_play_tone(u32 freq, u32 duration_ms) {
    pwm_audio_clear();
    audio_playing = true;

    u32 samples_per_cycle = AUDIO_SAMPLE_RATE / freq;
    u32 total_samples = (AUDIO_SAMPLE_RATE * duration_ms) / 1000;

    for (u32 i = 0; i < total_samples; i++) {
        /* Simple square wave */
        i16 sample = (i % samples_per_cycle < samples_per_cycle / 2) ? 16000 : -16000;
        pwm_audio_write(&sample, 1);

        /* Feed PWM at sample rate */
        if (pwm_audio_buffer_available() > 100) {
            pwm_audio_tick();
            timer_delay_us(1000000 / AUDIO_SAMPLE_RATE);
        }
    }

    /* Drain buffer */
    while (pwm_audio_buffer_available() > 0) {
        pwm_audio_tick();
        timer_delay_us(1000000 / AUDIO_SAMPLE_RATE);
    }

    audio_playing = false;
    *PWM_DAT1 = PWM_RANGE / 2;
}
