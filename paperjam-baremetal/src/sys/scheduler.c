/*
 * PaperJam Bare-Metal OS - Cooperative Scheduler
 *
 * Simple event-driven task scheduler with WFI for power efficiency
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "scheduler.h"
#include "sys/heap.h"

/* Task configuration */
#define MAX_TASKS       16
#define MAX_TIMERS      8

/* Task structure */
typedef struct {
    task_func_t func;
    void* data;
    u32 interval_ms;
    u64 next_run;
    int enabled;
    const char* name;
} task_t;

/* Timer structure */
typedef struct {
    timer_callback_t callback;
    void* data;
    u64 fire_time;
    int active;
} sched_timer_t;

/* Scheduler state */
static task_t tasks[MAX_TASKS];
static int task_count = 0;
static sched_timer_t timers[MAX_TIMERS];
static int scheduler_running = 0;
static int idle_count = 0;

/*
 * Initialize scheduler
 */
void scheduler_init(void) {
    memset(tasks, 0, sizeof(tasks));
    memset(timers, 0, sizeof(timers));
    task_count = 0;
    scheduler_running = 0;
    idle_count = 0;
}

/*
 * Register a periodic task
 */
int scheduler_add_task(const char* name, task_func_t func, void* data, u32 interval_ms) {
    if (task_count >= MAX_TASKS) return -1;

    task_t* task = &tasks[task_count];
    task->name = name;
    task->func = func;
    task->data = data;
    task->interval_ms = interval_ms;
    task->next_run = timer_get_ms() + interval_ms;
    task->enabled = 1;

    return task_count++;
}

/*
 * Remove a task
 */
void scheduler_remove_task(int task_id) {
    if (task_id < 0 || task_id >= task_count) return;
    tasks[task_id].enabled = 0;
}

/*
 * Enable/disable a task
 */
void scheduler_enable_task(int task_id, int enabled) {
    if (task_id < 0 || task_id >= task_count) return;
    tasks[task_id].enabled = enabled;
    if (enabled) {
        tasks[task_id].next_run = timer_get_ms() + tasks[task_id].interval_ms;
    }
}

/*
 * Schedule a one-shot timer
 */
int scheduler_set_timer(u32 delay_ms, timer_callback_t callback, void* data) {
    for (int i = 0; i < MAX_TIMERS; i++) {
        if (!timers[i].active) {
            timers[i].callback = callback;
            timers[i].data = data;
            timers[i].fire_time = timer_get_ms() + delay_ms;
            timers[i].active = 1;
            return i;
        }
    }
    return -1;
}

/*
 * Cancel a timer
 */
void scheduler_cancel_timer(int timer_id) {
    if (timer_id >= 0 && timer_id < MAX_TIMERS) {
        timers[timer_id].active = 0;
    }
}

/*
 * Run one iteration of the scheduler
 */
void scheduler_tick(void) {
    u64 now = timer_get_ms();
    int ran_something = 0;

    /* Check periodic tasks */
    for (int i = 0; i < task_count; i++) {
        task_t* task = &tasks[i];
        if (task->enabled && task->func && now >= task->next_run) {
            task->func(task->data);
            task->next_run = now + task->interval_ms;
            ran_something = 1;
        }
    }

    /* Check one-shot timers */
    for (int i = 0; i < MAX_TIMERS; i++) {
        sched_timer_t* timer = &timers[i];
        if (timer->active && now >= timer->fire_time) {
            timer->active = 0;
            if (timer->callback) {
                timer->callback(timer->data);
            }
            ran_something = 1;
        }
    }

    /* Track idle time */
    if (!ran_something) {
        idle_count++;
    }
}

/*
 * Calculate time until next task
 */
static u32 time_until_next(void) {
    u64 now = timer_get_ms();
    u32 min_delay = 1000;  /* Default 1 second */

    for (int i = 0; i < task_count; i++) {
        if (tasks[i].enabled) {
            if (now >= tasks[i].next_run) {
                return 0;
            }
            u32 delay = tasks[i].next_run - now;
            if (delay < min_delay) {
                min_delay = delay;
            }
        }
    }

    for (int i = 0; i < MAX_TIMERS; i++) {
        if (timers[i].active) {
            if (now >= timers[i].fire_time) {
                return 0;
            }
            u32 delay = timers[i].fire_time - now;
            if (delay < min_delay) {
                min_delay = delay;
            }
        }
    }

    return min_delay;
}

/*
 * Main scheduler loop
 */
void scheduler_run(void) {
    scheduler_running = 1;

    while (scheduler_running) {
        scheduler_tick();

        /* If nothing to do, use WFI for power efficiency */
        u32 delay = time_until_next();
        if (delay > 0) {
            /* Wait for interrupt or timeout */
            __asm__ volatile("wfi");
        }
    }
}

/*
 * Stop scheduler
 */
void scheduler_stop(void) {
    scheduler_running = 0;
}

/*
 * Check if scheduler is running
 */
int scheduler_is_running(void) {
    return scheduler_running;
}

/*
 * Get idle count (for power stats)
 */
u32 scheduler_get_idle_count(void) {
    return idle_count;
}

/*
 * Reset idle count
 */
void scheduler_reset_idle_count(void) {
    idle_count = 0;
}

/*
 * Yield to other tasks
 */
void scheduler_yield(void) {
    scheduler_tick();
}

/*
 * Delay without blocking other tasks
 */
void scheduler_delay(u32 ms) {
    u64 target = timer_get_ms() + ms;
    while (timer_get_ms() < target) {
        scheduler_tick();
    }
}
