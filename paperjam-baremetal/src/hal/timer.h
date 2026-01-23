/*
 * PaperJam Bare-Metal OS - Timer Driver Header
 */

#ifndef TIMER_H
#define TIMER_H

#include "bcm2837.h"

/* Timer channels (1 and 3 available, 0 and 2 used by GPU) */
#define TIMER_CHANNEL_1     1
#define TIMER_CHANNEL_3     3

/* Function prototypes */
void timer_init(void);
u64  timer_get_ticks(void);
u64  timer_get_us(void);
u64  timer_get_ms(void);
void timer_delay_us(u32 us);
void timer_delay_ms(u32 ms);
void timer_set_compare(int channel, u32 value);
void timer_clear_match(int channel);
int  timer_match_pending(int channel);
void timer_setup_periodic(int channel, u32 interval_us);
void timer_advance_periodic(int channel, u32 interval_us);
u64  timer_get_tick_count(void);
u32  timer_elapsed_us(u64 start);
u32  timer_elapsed_ms(u64 start);

#endif /* TIMER_H */
