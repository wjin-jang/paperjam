/*
 * PaperJam Bare-Metal OS - UART Driver Header
 */

#ifndef UART_H
#define UART_H

#include "bcm2837.h"

/* Function prototypes */
void uart_init(void);
void uart_putc(char c);
char uart_getc(void);
int  uart_data_available(void);
int  uart_tx_ready(void);
void uart_puts(const char* str);
void uart_put_hex_byte(u8 val);
void uart_put_hex(u32 val);
void uart_put_dec(u32 val);
void uart_put_int(i32 val);
void uart_printf(const char* fmt, ...);
int  uart_gets(char* buf, int maxlen);

#endif /* UART_H */
