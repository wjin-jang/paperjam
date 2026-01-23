/*
 * PaperJam Bare-Metal OS - UART Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 *
 * Uses Mini UART (UART1) for debugging output
 * GPIO 14 = TXD, GPIO 15 = RXD
 */

#include "bcm2837.h"
#include "gpio.h"
#include "uart.h"

/* Mini UART baud rate calculation: baud = system_clock / (8 * (reg + 1)) */
/* For 250MHz core clock: reg = 250000000 / (8 * 115200) - 1 = 270 */
#define UART_BAUD_REG   270

/*
 * Initialize Mini UART for 115200 8N1
 */
void uart_init(void) {
    /* Enable Mini UART */
    *AUX_ENABLES = 1;

    /* Disable TX/RX during configuration */
    *AUX_MU_CNTL = 0;

    /* Disable interrupts */
    *AUX_MU_IER = 0;

    /* Set 8-bit mode */
    *AUX_MU_LCR = 3;

    /* Set RTS line high */
    *AUX_MU_MCR = 0;

    /* Clear FIFOs */
    *AUX_MU_IIR = 0xC6;

    /* Set baud rate */
    *AUX_MU_BAUD = UART_BAUD_REG;

    /* Configure GPIO 14/15 for Mini UART (ALT5) */
    gpio_set_function(14, GPIO_FUNC_ALT5);
    gpio_set_function(15, GPIO_FUNC_ALT5);

    /* Disable pull-up/down on UART pins */
    gpio_set_pull(14, GPIO_PULL_NONE);
    gpio_set_pull(15, GPIO_PULL_NONE);

    /* Enable TX and RX */
    *AUX_MU_CNTL = 3;
}

/*
 * Send a single character
 */
void uart_putc(char c) {
    /* Wait for transmitter to be ready */
    while (!(*AUX_MU_LSR & 0x20)) {
        /* Busy wait */
    }
    *AUX_MU_IO = c;
}

/*
 * Receive a single character (blocking)
 */
char uart_getc(void) {
    /* Wait for data to be available */
    while (!(*AUX_MU_LSR & 0x01)) {
        /* Busy wait */
    }
    return (char)(*AUX_MU_IO & 0xFF);
}

/*
 * Check if data is available to read
 */
int uart_data_available(void) {
    return (*AUX_MU_LSR & 0x01) != 0;
}

/*
 * Check if transmitter is ready
 */
int uart_tx_ready(void) {
    return (*AUX_MU_LSR & 0x20) != 0;
}

/*
 * Send a string
 */
void uart_puts(const char* str) {
    while (*str) {
        if (*str == '\n') {
            uart_putc('\r');
        }
        uart_putc(*str++);
    }
}

/*
 * Send a hex byte
 */
void uart_put_hex_byte(u8 val) {
    static const char hex[] = "0123456789ABCDEF";
    uart_putc(hex[(val >> 4) & 0x0F]);
    uart_putc(hex[val & 0x0F]);
}

/*
 * Send a hex word (32-bit)
 */
void uart_put_hex(u32 val) {
    uart_puts("0x");
    for (int i = 28; i >= 0; i -= 4) {
        static const char hex[] = "0123456789ABCDEF";
        uart_putc(hex[(val >> i) & 0x0F]);
    }
}

/*
 * Send a decimal number
 */
void uart_put_dec(u32 val) {
    char buf[12];
    int i = 0;

    if (val == 0) {
        uart_putc('0');
        return;
    }

    while (val > 0) {
        buf[i++] = '0' + (val % 10);
        val /= 10;
    }

    while (i > 0) {
        uart_putc(buf[--i]);
    }
}

/*
 * Send a signed decimal number
 */
void uart_put_int(i32 val) {
    if (val < 0) {
        uart_putc('-');
        val = -val;
    }
    uart_put_dec((u32)val);
}

/*
 * Formatted print (simple implementation)
 */
void uart_printf(const char* fmt, ...) {
    /* Note: This is a simplified printf without full format specifier support */
    /* For bare-metal, we'll use explicit uart_puts/uart_put_hex/uart_put_dec */
    uart_puts(fmt);
}

/*
 * Read a line into buffer
 */
int uart_gets(char* buf, int maxlen) {
    int i = 0;

    while (i < maxlen - 1) {
        char c = uart_getc();

        if (c == '\r' || c == '\n') {
            uart_puts("\r\n");
            break;
        }

        if (c == '\b' || c == 0x7F) {
            if (i > 0) {
                uart_puts("\b \b");
                i--;
            }
            continue;
        }

        buf[i++] = c;
        uart_putc(c);
    }

    buf[i] = '\0';
    return i;
}
