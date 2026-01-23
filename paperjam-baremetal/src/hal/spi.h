/*
 * PaperJam Bare-Metal OS - SPI Driver Header
 */

#ifndef SPI_H
#define SPI_H

#include "bcm2837.h"

/* SPI chip select */
#define SPI_CS_EPAPER   0   /* E-paper on CE0 */
#define SPI_CS_1        1   /* CE1 */

/* SPI modes */
#define SPI_MODE_0      0   /* CPOL=0, CPHA=0 */
#define SPI_MODE_1      1   /* CPOL=0, CPHA=1 */
#define SPI_MODE_2      2   /* CPOL=1, CPHA=0 */
#define SPI_MODE_3      3   /* CPOL=1, CPHA=1 */

/* Function prototypes */
void spi_init(void);
void spi_set_clock(u32 freq_hz);
void spi_set_mode(int mode);
void spi_select(int cs);
void spi_begin(void);
void spi_end(void);
u8   spi_transfer(u8 data);
void spi_write(u8 data);
u8   spi_read(void);
void spi_write_bytes(const u8* data, u32 len);
void spi_read_bytes(u8* data, u32 len);
void spi_transfer_bytes(const u8* tx, u8* rx, u32 len);
void spi_write_then_read(const u8* tx, u32 tx_len, u8* rx, u32 rx_len);

#endif /* SPI_H */
