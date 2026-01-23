/*
 * PaperJam Bare-Metal OS - Font Header
 */

#ifndef FONTS_H
#define FONTS_H

#include "hal/bcm2837.h"

/* Font structure */
typedef struct {
    const u8* data;
    u8 char_width;
    u8 char_height;
    u8 first_char;
    u8 last_char;
    u8 bytes_per_char;
} font_t;

/* Function prototypes */
void font_set(const font_t* font);
const font_t* font_get(void);
const font_t* font_get_default(void);
int font_draw_char(int x, int y, char c, int color);
int font_draw_string(int x, int y, const char* str, int color);
int font_draw_string_bg(int x, int y, const char* str, int fg, int bg);
int font_string_width(const char* str);
int font_get_height(void);
int font_get_width(void);

#endif /* FONTS_H */
