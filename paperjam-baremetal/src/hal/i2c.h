/*
 * PaperJam Bare-Metal OS - I2C Driver Header
 */

#ifndef I2C_H
#define I2C_H

#include "bcm2837.h"

/* PiSugar 3 I2C address */
#define I2C_ADDR_PISUGAR   0x57

/* Function prototypes */
void i2c_init(void);
void i2c_set_clock(u32 freq_hz);
int  i2c_write(u8 addr, const u8* data, u32 len);
int  i2c_read(u8 addr, u8* data, u32 len);
int  i2c_write_read(u8 addr, u8 reg, u8* data, u32 len);
int  i2c_write_reg(u8 addr, u8 reg, u8 value);
int  i2c_read_reg(u8 addr, u8 reg, u8* value);
void i2c_scan(u8* found, int max_found);

#endif /* I2C_H */
