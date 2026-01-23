/*
 * PaperJam Bare-Metal OS - Power Management
 */

#include "hal/bcm2837.h"
#include "hal/timer.h"
#include "power.h"
#include "drivers/pisugar3.h"
#include "drivers/epd_2in13_v4.h"
#include "app/favorites.h"
#include "sys/scheduler.h"

/* Power management state */
static u64 last_activity = 0;
static int low_battery_warned = 0;
static power_callback_t shutdown_callback = NULL;

/* Battery check interval (5 seconds) */
#define BATTERY_CHECK_INTERVAL  5000

/*
 * Initialize power management
 */
void power_init(void) {
    last_activity = timer_get_ms();
    low_battery_warned = 0;

    /* Register battery check task */
    scheduler_add_task("battery", power_check_battery, NULL, BATTERY_CHECK_INTERVAL);
}

/*
 * Record activity (resets idle timer)
 */
void power_activity(void) {
    last_activity = timer_get_ms();
}

/*
 * Get idle time in milliseconds
 */
u32 power_get_idle_time(void) {
    return timer_get_ms() - last_activity;
}

/*
 * Check battery and handle low battery
 */
void power_check_battery(void* data) {
    (void)data;

    pisugar_update();

    int level = pisugar_get_cached_level();

    /* Critical battery - shutdown */
    if (pisugar_is_critical_battery()) {
        power_shutdown();
        return;
    }

    /* Low battery warning */
    if (pisugar_is_low_battery() && !low_battery_warned) {
        low_battery_warned = 1;
        /* Could trigger a UI warning here */
    }

    /* Reset warning if battery recovered */
    if (level > PISUGAR_LOW_BATTERY_THRESHOLD + 5) {
        low_battery_warned = 0;
    }
}

/*
 * Prepare for shutdown
 */
void power_prepare_shutdown(void) {
    /* Save favorites */
    favorites_save();

    /* Put display to sleep */
    epd_sleep();

    /* Call shutdown callback if set */
    if (shutdown_callback) {
        shutdown_callback();
    }
}

/*
 * Shutdown the system
 */
void power_shutdown(void) {
    power_prepare_shutdown();

    /* Trigger power off via PiSugar */
    pisugar_power_off();

    /* If power off failed, halt CPU */
    while (1) {
        __asm__ volatile("wfi");
    }
}

/*
 * Reboot the system
 */
void power_reboot(void) {
    power_prepare_shutdown();

    /* Use watchdog to reboot */
    *PM_WDOG = PM_PASSWORD | 1;
    *PM_RSTC = PM_PASSWORD | 0x20;

    while (1) {
        __asm__ volatile("wfi");
    }
}

/*
 * Set shutdown callback
 */
void power_set_shutdown_callback(power_callback_t callback) {
    shutdown_callback = callback;
}

/*
 * Get battery level
 */
int power_get_battery_level(void) {
    return pisugar_get_cached_level();
}

/*
 * Check if charging
 */
int power_is_charging(void) {
    return pisugar_get_cached_charging();
}

/*
 * Check if battery is low
 */
int power_is_battery_low(void) {
    return pisugar_is_low_battery();
}

/*
 * Enter low power mode (for idle)
 */
void power_enter_idle(void) {
    /* WFI - CPU will wake on next interrupt */
    __asm__ volatile("wfi");
}

/*
 * Get power stats
 */
void power_get_stats(power_stats_t* stats) {
    stats->battery_level = pisugar_get_cached_level();
    stats->battery_voltage = pisugar_get_battery_voltage();
    stats->is_charging = pisugar_get_cached_charging();
    stats->idle_time_ms = power_get_idle_time();
    stats->scheduler_idle_count = scheduler_get_idle_count();
}
