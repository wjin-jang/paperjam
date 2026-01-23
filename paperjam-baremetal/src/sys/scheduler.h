/*
 * PaperJam Bare-Metal OS - Scheduler Header
 */

#ifndef SCHEDULER_H
#define SCHEDULER_H

#include "hal/bcm2837.h"

/* Task function type */
typedef void (*task_func_t)(void* data);

/* Timer callback type */
typedef void (*timer_callback_t)(void* data);

/* Function prototypes */
void scheduler_init(void);
int  scheduler_add_task(const char* name, task_func_t func, void* data, u32 interval_ms);
void scheduler_remove_task(int task_id);
void scheduler_enable_task(int task_id, int enabled);
int  scheduler_set_timer(u32 delay_ms, timer_callback_t callback, void* data);
void scheduler_cancel_timer(int timer_id);
void scheduler_tick(void);
void scheduler_run(void);
void scheduler_stop(void);
int  scheduler_is_running(void);
u32  scheduler_get_idle_count(void);
void scheduler_reset_idle_count(void);
void scheduler_yield(void);
void scheduler_delay(u32 ms);

#endif /* SCHEDULER_H */
