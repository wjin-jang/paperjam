/*
 * PaperJam Bare-Metal OS - System Timer Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 *
 * Uses the BCM2837 System Timer (1MHz free-running counter)
 */

#include "bcm2837.h"
#include "timer.h"

/* System timer runs at 1MHz */
#define TIMER_FREQ_HZ   1000000

/* Global tick counter for scheduler */
static volatile u64 tick_count = 0;

/*
 * Get current timer value (64-bit, microseconds)
 */
u64 timer_get_ticks(void) {
    u32 hi, lo, hi_check;

    /* Read high/low atomically */
    do {
        hi = *SYSTIMER_CHI;
        lo = *SYSTIMER_CLO;
        hi_check = *SYSTIMER_CHI;
    } while (hi != hi_check);

    return ((u64)hi << 32) | lo;
}

/*
 * Get current time in microseconds
 */
u64 timer_get_us(void) {
    return timer_get_ticks();
}

/*
 * Get current time in milliseconds
 */
u64 timer_get_ms(void) {
    return timer_get_ticks() / 1000;
}

/*
 * Delay for specified microseconds (busy wait)
 */
void timer_delay_us(u32 us) {
    u64 target = timer_get_ticks() + us;
    while (timer_get_ticks() < target) {
        /* Busy wait */
    }
}

/*
 * Delay for specified milliseconds (busy wait)
 */
void timer_delay_ms(u32 ms) {
    timer_delay_us(ms * 1000);
}

/*
 * Set timer compare value (for interrupts)
 * channel: 0-3 (0 and 2 used by GPU, use 1 or 3)
 * value: absolute timer value to trigger at
 */
void timer_set_compare(int channel, u32 value) {
    switch (channel) {
        case 0: *SYSTIMER_C0 = value; break;
        case 1: *SYSTIMER_C1 = value; break;
        case 2: *SYSTIMER_C2 = value; break;
        case 3: *SYSTIMER_C3 = value; break;
    }
}

/*
 * Clear timer match flag
 */
void timer_clear_match(int channel) {
    *SYSTIMER_CS = (1 << channel);
}

/*
 * Check if timer match occurred
 */
int timer_match_pending(int channel) {
    return (*SYSTIMER_CS >> channel) & 1;
}

/*
 * Set up periodic timer interrupt
 * interval_us: interval in microseconds
 */
void timer_setup_periodic(int channel, u32 interval_us) {
    u32 current = *SYSTIMER_CLO;
    timer_set_compare(channel, current + interval_us);
}

/*
 * Advance periodic timer (call from ISR)
 */
void timer_advance_periodic(int channel, u32 interval_us) {
    u32 compare;
    switch (channel) {
        case 0: compare = *SYSTIMER_C0; break;
        case 1: compare = *SYSTIMER_C1; break;
        case 2: compare = *SYSTIMER_C2; break;
        case 3: compare = *SYSTIMER_C3; break;
        default: return;
    }
    timer_set_compare(channel, compare + interval_us);
    timer_clear_match(channel);
    tick_count++;
}

/*
 * Get tick count (incremented by periodic timer)
 */
u64 timer_get_tick_count(void) {
    return tick_count;
}

/*
 * Initialize system timer
 */
void timer_init(void) {
    /* Clear any pending matches */
    *SYSTIMER_CS = 0x0F;
    tick_count = 0;
}

/*
 * Elapsed time helper
 */
u32 timer_elapsed_us(u64 start) {
    return (u32)(timer_get_us() - start);
}

u32 timer_elapsed_ms(u64 start) {
    return (u32)(timer_get_ms() - start);
}
