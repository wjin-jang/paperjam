/*
 * PaperJam Bare-Metal OS - E-Paper Display Driver Header
 */

#ifndef EPD_2IN13_V4_H
#define EPD_2IN13_V4_H

#include "hal/bcm2837.h"
#include "sys/heap.h"

/* Display dimensions */
#define EPD_WIDTH       122
#define EPD_HEIGHT      250
#define EPD_WIDTH_BYTES ((EPD_WIDTH + 7) / 8)
#define EPD_BUFFER_SIZE (EPD_WIDTH_BYTES * EPD_HEIGHT)

/* Function prototypes */
void epd_init(void);
void epd_init_partial(void);
void epd_clear(void);
void epd_display(const u8* image);
void epd_display_partial(const u8* image);
void epd_sleep(void);
void epd_wake(void);
int  epd_get_width(void);
int  epd_get_height(void);
int  epd_get_width_bytes(void);
int  epd_get_partial_count(void);
void epd_reset_partial_count(void);
int  epd_is_initialized(void);

#endif /* EPD_2IN13_V4_H */
