/*
 * PaperJam Bare-Metal OS - Text Utilities Header
 */

#ifndef TEXT_H
#define TEXT_H

#include "hal/bcm2837.h"

/* Text alignment */
typedef enum {
    TEXT_ALIGN_LEFT,
    TEXT_ALIGN_CENTER,
    TEXT_ALIGN_RIGHT
} text_align_t;

/* Function prototypes */
void text_draw_aligned(int x, int y, int width, const char* str,
                       text_align_t align, int color);
int  text_draw_wrapped(int x, int y, int width, int max_lines,
                       const char* str, int color);
void text_draw_scrolling(int x, int y, int width, const char* str,
                         int scroll_offset, int color);
void text_draw_ellipsis(int x, int y, int width, const char* str, int color);
void text_draw_number(int x, int y, int num, int color);
void text_draw_time(int x, int y, int seconds, int color);
void text_draw_progress_bar(int x, int y, int width, int height,
                            int progress, int color);
int  text_calc_wrapped_height(int width, const char* str);

#endif /* TEXT_H */
