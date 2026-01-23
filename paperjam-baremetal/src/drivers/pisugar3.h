/*
 * PaperJam Bare-Metal OS - PiSugar 3 Battery Driver Header
 */

#ifndef PISUGAR3_H
#define PISUGAR3_H

#include "hal/bcm2837.h"

/* Battery thresholds */
#define PISUGAR_LOW_BATTERY_THRESHOLD   20
#define PISUGAR_SHUTDOWN_THRESHOLD      12

/* Function prototypes */
int  pisugar_init(void);
int  pisugar_get_battery_level(void);
int  pisugar_get_battery_voltage(void);
int  pisugar_is_charging(void);
void pisugar_update(void);
int  pisugar_get_cached_level(void);
int  pisugar_get_cached_charging(void);
int  pisugar_is_low_battery(void);
int  pisugar_is_critical_battery(void);
void pisugar_power_off(void);
char pisugar_get_battery_icon(void);

#endif /* PISUGAR3_H */
