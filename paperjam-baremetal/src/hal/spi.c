/*
 * PaperJam Bare-Metal OS - SPI Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 *
 * SPI0: GPIO 7-11 (main SPI for e-paper display)
 * - GPIO 7  = CE1 (chip select 1)
 * - GPIO 8  = CE0 (chip select 0) - e-paper
 * - GPIO 9  = MISO
 * - GPIO 10 = MOSI
 * - GPIO 11 = SCLK
 */

#include "bcm2837.h"
#include "gpio.h"
#include "spi.h"
#include "timer.h"

/* SPI core clock is 250MHz (or 400MHz on Pi4) */
#define SPI_CORE_CLOCK  250000000

/*
 * Initialize SPI0 for e-paper display
 * Default: 4MHz clock, mode 0 (CPOL=0, CPHA=0)
 */
void spi_init(void) {
    /* Configure GPIO pins for SPI0 (ALT0) */
    gpio_set_function(7,  GPIO_FUNC_ALT0);  /* CE1 */
    gpio_set_function(8,  GPIO_FUNC_ALT0);  /* CE0 */
    gpio_set_function(9,  GPIO_FUNC_ALT0);  /* MISO */
    gpio_set_function(10, GPIO_FUNC_ALT0);  /* MOSI */
    gpio_set_function(11, GPIO_FUNC_ALT0);  /* SCLK */

    /* Clear FIFOs and set default mode */
    *SPI0_CS = SPI_CS_CLEAR_RX | SPI_CS_CLEAR_TX;

    /* Set clock divider for 4MHz: 250MHz / 4MHz = 62.5, round to 64 */
    *SPI0_CLK = 64;
}

/*
 * Set SPI clock speed
 * freq_hz: desired frequency in Hz
 */
void spi_set_clock(u32 freq_hz) {
    u32 divider = SPI_CORE_CLOCK / freq_hz;
    if (divider < 2) divider = 2;
    if (divider > 65536) divider = 65536;
    /* Round up to even number */
    divider = (divider + 1) & ~1;
    *SPI0_CLK = divider;
}

/*
 * Set SPI mode (CPOL, CPHA)
 * mode 0: CPOL=0, CPHA=0
 * mode 1: CPOL=0, CPHA=1
 * mode 2: CPOL=1, CPHA=0
 * mode 3: CPOL=1, CPHA=1
 */
void spi_set_mode(int mode) {
    u32 cs = *SPI0_CS;
    cs &= ~(SPI_CS_CPOL | SPI_CS_CPHA);

    switch (mode) {
        case 0: break;
        case 1: cs |= SPI_CS_CPHA; break;
        case 2: cs |= SPI_CS_CPOL; break;
        case 3: cs |= SPI_CS_CPOL | SPI_CS_CPHA; break;
    }

    *SPI0_CS = cs;
}

/*
 * Select chip (assert CS)
 * cs: 0 or 1 for CE0/CE1
 */
void spi_select(int cs) {
    u32 val = *SPI0_CS;
    val &= ~3;
    val |= (cs & 1);
    *SPI0_CS = val;
}

/*
 * Begin SPI transaction
 */
void spi_begin(void) {
    /* Clear FIFOs */
    *SPI0_CS = (*SPI0_CS & ~(SPI_CS_TA)) | SPI_CS_CLEAR_RX | SPI_CS_CLEAR_TX;
    /* Set transfer active */
    *SPI0_CS |= SPI_CS_TA;
}

/*
 * End SPI transaction
 */
void spi_end(void) {
    /* Wait for done */
    while (!(*SPI0_CS & SPI_CS_DONE)) {
        /* Busy wait */
    }
    /* Clear transfer active */
    *SPI0_CS &= ~SPI_CS_TA;
}

/*
 * Transfer a single byte (full duplex)
 */
u8 spi_transfer(u8 data) {
    /* Wait for TX FIFO to have space */
    while (!(*SPI0_CS & SPI_CS_TXD)) {
        /* Busy wait */
    }

    /* Write data */
    *SPI0_FIFO = data;

    /* Wait for transfer complete */
    while (!(*SPI0_CS & SPI_CS_DONE)) {
        /* Busy wait */
    }

    /* Read received data */
    return *SPI0_FIFO & 0xFF;
}

/*
 * Write a single byte (ignore received data)
 */
void spi_write(u8 data) {
    (void)spi_transfer(data);
}

/*
 * Read a single byte (send dummy 0xFF)
 */
u8 spi_read(void) {
    return spi_transfer(0xFF);
}

/*
 * Write multiple bytes
 */
void spi_write_bytes(const u8* data, u32 len) {
    for (u32 i = 0; i < len; i++) {
        /* Wait for TX FIFO space */
        while (!(*SPI0_CS & SPI_CS_TXD)) {
            /* Busy wait */
        }
        *SPI0_FIFO = data[i];
    }

    /* Wait for all data to be sent */
    while (!(*SPI0_CS & SPI_CS_DONE)) {
        /* Busy wait */
    }

    /* Drain RX FIFO */
    while (*SPI0_CS & SPI_CS_RXD) {
        (void)*SPI0_FIFO;
    }
}

/*
 * Read multiple bytes
 */
void spi_read_bytes(u8* data, u32 len) {
    for (u32 i = 0; i < len; i++) {
        data[i] = spi_transfer(0xFF);
    }
}

/*
 * Transfer multiple bytes (full duplex)
 */
void spi_transfer_bytes(const u8* tx, u8* rx, u32 len) {
    for (u32 i = 0; i < len; i++) {
        rx[i] = spi_transfer(tx[i]);
    }
}

/*
 * Write then read (common SPI pattern)
 */
void spi_write_then_read(const u8* tx, u32 tx_len, u8* rx, u32 rx_len) {
    spi_begin();
    spi_write_bytes(tx, tx_len);
    spi_read_bytes(rx, rx_len);
    spi_end();
}
