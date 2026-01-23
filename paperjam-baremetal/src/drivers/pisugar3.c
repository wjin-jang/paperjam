/*
 * PaperJam Bare-Metal OS - PiSugar 3 Battery Driver
 * I2C address: 0x57 (IP5312 chip)
 */

#include "hal/bcm2837.h"
#include "hal/i2c.h"
#include "hal/timer.h"
#include "pisugar3.h"

/* I2C address */
#define PISUGAR_ADDR        0x57

/* Registers (IP5312/PiSugar 3) */
#define REG_BATTERY_LEVEL   0x2A    /* Battery percentage */
#define REG_BATTERY_VOLTAGE 0xA2    /* Battery voltage (2 bytes) */
#define REG_CHARGING        0x02    /* Charging status */
#define REG_CTL1            0x01    /* Control register 1 */
#define REG_CTL2            0x03    /* Control register 2 */

/* Charging status bits */
#define CHARGING_BIT        (1 << 7)

/* Battery state */
static int battery_level = -1;
static int battery_voltage = -1;
static int battery_charging = 0;
static u64 last_update = 0;

/* Update interval in milliseconds */
#define UPDATE_INTERVAL_MS  5000

/*
 * Initialize PiSugar driver
 */
int pisugar_init(void) {
    /* I2C should already be initialized */
    /* Try to read battery level to verify communication */
    u8 level;
    if (i2c_read_reg(PISUGAR_ADDR, REG_BATTERY_LEVEL, &level) < 0) {
        return -1;
    }
    battery_level = level;
    last_update = timer_get_ms();
    return 0;
}

/*
 * Read battery percentage (0-100)
 */
int pisugar_get_battery_level(void) {
    u8 level;
    if (i2c_read_reg(PISUGAR_ADDR, REG_BATTERY_LEVEL, &level) < 0) {
        return battery_level;  /* Return cached value on error */
    }
    battery_level = level;
    if (battery_level > 100) battery_level = 100;
    return battery_level;
}

/*
 * Read battery voltage in millivolts
 */
int pisugar_get_battery_voltage(void) {
    u8 data[2];
    if (i2c_write_read(PISUGAR_ADDR, REG_BATTERY_VOLTAGE, data, 2) < 0) {
        return battery_voltage;
    }
    /* Voltage is in 1.26mV units */
    battery_voltage = ((data[0] << 8) | data[1]) * 126 / 100;
    return battery_voltage;
}

/*
 * Check if battery is charging
 */
int pisugar_is_charging(void) {
    u8 status;
    if (i2c_read_reg(PISUGAR_ADDR, REG_CHARGING, &status) < 0) {
        return battery_charging;
    }
    battery_charging = (status & CHARGING_BIT) ? 1 : 0;
    return battery_charging;
}

/*
 * Update battery status (call periodically)
 */
void pisugar_update(void) {
    u64 now = timer_get_ms();
    if (now - last_update < UPDATE_INTERVAL_MS) {
        return;
    }
    last_update = now;

    pisugar_get_battery_level();
    pisugar_is_charging();
}

/*
 * Get cached battery level
 */
int pisugar_get_cached_level(void) {
    return battery_level;
}

/*
 * Get cached charging status
 */
int pisugar_get_cached_charging(void) {
    return battery_charging;
}

/*
 * Check if battery is low (below threshold)
 */
int pisugar_is_low_battery(void) {
    return battery_level >= 0 && battery_level < PISUGAR_LOW_BATTERY_THRESHOLD;
}

/*
 * Check if battery is critical (below shutdown threshold)
 */
int pisugar_is_critical_battery(void) {
    return battery_level >= 0 && battery_level < PISUGAR_SHUTDOWN_THRESHOLD;
}

/*
 * Power off the device
 */
void pisugar_power_off(void) {
    /* Write to control register to trigger shutdown */
    /* This may vary by PiSugar model */
    i2c_write_reg(PISUGAR_ADDR, REG_CTL1, 0x00);
    timer_delay_ms(100);
}

/*
 * Get battery icon based on level
 * Returns a character representing battery state
 */
char pisugar_get_battery_icon(void) {
    if (battery_charging) {
        return '+';  /* Charging indicator */
    }
    if (battery_level < 0) {
        return '?';  /* Unknown */
    }
    if (battery_level < 20) {
        return '!';  /* Low */
    }
    if (battery_level < 40) {
        return '_';  /* Quarter */
    }
    if (battery_level < 60) {
        return '-';  /* Half */
    }
    if (battery_level < 80) {
        return '=';  /* Three quarters */
    }
    return '#';      /* Full */
}
