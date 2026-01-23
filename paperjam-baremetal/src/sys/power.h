/*
 * PaperJam Bare-Metal OS - Power Management Header
 */

#ifndef POWER_H
#define POWER_H

#include "hal/bcm2837.h"

/* Power callback type */
typedef void (*power_callback_t)(void);

/* Power statistics */
typedef struct {
    int battery_level;
    int battery_voltage;
    int is_charging;
    u32 idle_time_ms;
    u32 scheduler_idle_count;
} power_stats_t;

/* Function prototypes */
void power_init(void);
void power_activity(void);
u32  power_get_idle_time(void);
void power_check_battery(void* data);
void power_prepare_shutdown(void);
void power_shutdown(void);
void power_reboot(void);
void power_set_shutdown_callback(power_callback_t callback);
int  power_get_battery_level(void);
int  power_is_charging(void);
int  power_is_battery_low(void);
void power_enter_idle(void);
void power_get_stats(power_stats_t* stats);

#endif /* POWER_H */
