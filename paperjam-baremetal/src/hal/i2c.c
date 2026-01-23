/*
 * PaperJam Bare-Metal OS - I2C Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 *
 * BSC1 (I2C1): GPIO 2 = SDA, GPIO 3 = SCL
 * Used for PiSugar 3 battery module (address 0x57)
 */

#include "bcm2837.h"
#include "gpio.h"
#include "i2c.h"
#include "timer.h"

/* I2C clock: core_clock / divider = 250MHz / 2500 = 100kHz */
#define I2C_CLOCK_DIVIDER   2500
#define I2C_TIMEOUT_US      100000  /* 100ms timeout */

/*
 * Initialize I2C (BSC1)
 */
void i2c_init(void) {
    /* Configure GPIO 2 and 3 for I2C (ALT0) */
    gpio_set_function(2, GPIO_FUNC_ALT0);  /* SDA */
    gpio_set_function(3, GPIO_FUNC_ALT0);  /* SCL */

    /* Enable pull-ups on I2C pins */
    gpio_set_pull(2, GPIO_PULL_UP);
    gpio_set_pull(3, GPIO_PULL_UP);

    /* Set clock divider for 100kHz */
    *BSC1_DIV = I2C_CLOCK_DIVIDER;

    /* Clear status flags and disable */
    *BSC1_S = BSC_S_CLKT | BSC_S_ERR | BSC_S_DONE;

    /* Enable I2C */
    *BSC1_C = BSC_C_I2CEN;
}

/*
 * Set I2C clock speed
 * freq_hz: desired frequency in Hz
 */
void i2c_set_clock(u32 freq_hz) {
    u32 divider = 250000000 / freq_hz;
    if (divider < 2) divider = 2;
    *BSC1_DIV = divider;
}

/*
 * Wait for I2C transfer to complete
 * Returns: 0 on success, -1 on timeout, -2 on error
 */
static int i2c_wait_done(void) {
    u64 start = timer_get_us();

    while (1) {
        u32 status = *BSC1_S;

        if (status & BSC_S_DONE) {
            /* Check for errors */
            if (status & BSC_S_ERR) {
                *BSC1_S = BSC_S_ERR;
                return -2;
            }
            if (status & BSC_S_CLKT) {
                *BSC1_S = BSC_S_CLKT;
                return -1;
            }
            return 0;
        }

        if (timer_elapsed_us(start) > I2C_TIMEOUT_US) {
            return -1;
        }
    }
}

/*
 * Write bytes to I2C device
 * addr: 7-bit I2C address
 * data: data buffer
 * len: number of bytes to write
 * Returns: 0 on success, negative on error
 */
int i2c_write(u8 addr, const u8* data, u32 len) {
    /* Clear status flags */
    *BSC1_S = BSC_S_CLKT | BSC_S_ERR | BSC_S_DONE;

    /* Set slave address */
    *BSC1_A = addr;

    /* Set data length */
    *BSC1_DLEN = len;

    /* Start write transfer */
    *BSC1_C = BSC_C_I2CEN | BSC_C_ST | BSC_C_CLEAR;

    /* Write data to FIFO */
    for (u32 i = 0; i < len; i++) {
        /* Wait for FIFO space */
        while (!(*BSC1_S & BSC_S_TXD)) {
            if (*BSC1_S & (BSC_S_ERR | BSC_S_CLKT)) {
                return -2;
            }
        }
        *BSC1_FIFO = data[i];
    }

    /* Wait for completion */
    return i2c_wait_done();
}

/*
 * Read bytes from I2C device
 * addr: 7-bit I2C address
 * data: data buffer
 * len: number of bytes to read
 * Returns: 0 on success, negative on error
 */
int i2c_read(u8 addr, u8* data, u32 len) {
    /* Clear status flags */
    *BSC1_S = BSC_S_CLKT | BSC_S_ERR | BSC_S_DONE;

    /* Set slave address */
    *BSC1_A = addr;

    /* Set data length */
    *BSC1_DLEN = len;

    /* Start read transfer */
    *BSC1_C = BSC_C_I2CEN | BSC_C_ST | BSC_C_CLEAR | BSC_C_READ;

    /* Read data from FIFO */
    for (u32 i = 0; i < len; i++) {
        /* Wait for data available */
        u64 start = timer_get_us();
        while (!(*BSC1_S & BSC_S_RXD)) {
            if (*BSC1_S & (BSC_S_ERR | BSC_S_CLKT)) {
                return -2;
            }
            if (timer_elapsed_us(start) > I2C_TIMEOUT_US) {
                return -1;
            }
        }
        data[i] = *BSC1_FIFO & 0xFF;
    }

    /* Wait for completion */
    return i2c_wait_done();
}

/*
 * Write to register then read (common I2C pattern)
 * addr: 7-bit I2C address
 * reg: register address to write first
 * data: buffer for read data
 * len: number of bytes to read
 * Returns: 0 on success, negative on error
 */
int i2c_write_read(u8 addr, u8 reg, u8* data, u32 len) {
    int ret;

    /* Write register address */
    ret = i2c_write(addr, &reg, 1);
    if (ret < 0) return ret;

    /* Short delay between write and read */
    timer_delay_us(10);

    /* Read data */
    return i2c_read(addr, data, len);
}

/*
 * Write to register (single byte)
 */
int i2c_write_reg(u8 addr, u8 reg, u8 value) {
    u8 buf[2] = { reg, value };
    return i2c_write(addr, buf, 2);
}

/*
 * Read from register (single byte)
 */
int i2c_read_reg(u8 addr, u8 reg, u8* value) {
    return i2c_write_read(addr, reg, value, 1);
}

/*
 * Scan for devices on I2C bus
 * Returns bitmask of found addresses
 */
void i2c_scan(u8* found, int max_found) {
    int count = 0;

    for (u8 addr = 0x08; addr < 0x78 && count < max_found; addr++) {
        /* Try to read a single byte */
        u8 dummy;
        *BSC1_S = BSC_S_CLKT | BSC_S_ERR | BSC_S_DONE;
        *BSC1_A = addr;
        *BSC1_DLEN = 1;
        *BSC1_C = BSC_C_I2CEN | BSC_C_ST | BSC_C_CLEAR | BSC_C_READ;

        /* Wait for completion or error */
        u64 start = timer_get_us();
        while (!(*BSC1_S & (BSC_S_DONE | BSC_S_ERR | BSC_S_CLKT))) {
            if (timer_elapsed_us(start) > 10000) break;
        }

        if (*BSC1_S & BSC_S_DONE) {
            if (!(*BSC1_S & BSC_S_ERR)) {
                dummy = *BSC1_FIFO;
                (void)dummy;
                found[count++] = addr;
            }
        }

        /* Clear status */
        *BSC1_S = BSC_S_CLKT | BSC_S_ERR | BSC_S_DONE;
    }

    /* Mark end */
    if (count < max_found) {
        found[count] = 0;
    }
}
