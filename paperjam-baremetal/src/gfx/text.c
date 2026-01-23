/*
 * PaperJam Bare-Metal OS - Text Rendering Utilities
 *
 * Higher-level text rendering with word wrap, alignment, etc.
 */

#include "hal/bcm2837.h"
#include "text.h"
#include "fonts.h"
#include "framebuffer.h"
#include "sys/heap.h"

/*
 * Draw text with alignment
 */
void text_draw_aligned(int x, int y, int width, const char* str,
                       text_align_t align, int color) {
    int text_width = font_string_width(str);
    int draw_x = x;

    switch (align) {
        case TEXT_ALIGN_LEFT:
            draw_x = x;
            break;
        case TEXT_ALIGN_CENTER:
            draw_x = x + (width - text_width) / 2;
            break;
        case TEXT_ALIGN_RIGHT:
            draw_x = x + width - text_width;
            break;
    }

    font_draw_string(draw_x, y, str, color);
}

/*
 * Draw text with word wrap
 * Returns number of lines drawn
 */
int text_draw_wrapped(int x, int y, int width, int max_lines,
                      const char* str, int color) {
    int line = 0;
    int char_width = font_get_width();
    int char_height = font_get_height();
    int chars_per_line = width / char_width;

    if (chars_per_line < 1) chars_per_line = 1;

    const char* p = str;
    char line_buf[128];

    while (*p && (max_lines == 0 || line < max_lines)) {
        /* Find end of line */
        int len = 0;
        const char* word_start = p;
        const char* last_space = NULL;

        while (*p && len < chars_per_line) {
            if (*p == '\n') {
                p++;
                break;
            }
            if (*p == ' ') {
                last_space = p;
            }
            len++;
            p++;
        }

        /* If we didn't reach end or newline, break at last space */
        if (*p && *p != '\n' && last_space && last_space > word_start) {
            len = last_space - word_start;
            p = last_space + 1;
        }

        /* Copy line to buffer */
        for (int i = 0; i < len && i < 127; i++) {
            line_buf[i] = word_start[i];
        }
        line_buf[len] = '\0';

        /* Draw line */
        font_draw_string(x, y + line * (char_height + 1), line_buf, color);
        line++;

        /* Skip leading spaces on next line */
        while (*p == ' ') p++;
    }

    return line;
}

/*
 * Draw text that scrolls if too wide
 * scroll_offset: pixel offset for scrolling (0 = start)
 */
void text_draw_scrolling(int x, int y, int width, const char* str,
                         int scroll_offset, int color) {
    int text_width = font_string_width(str);

    if (text_width <= width) {
        /* No scrolling needed */
        font_draw_string(x, y, str, color);
        return;
    }

    /* Calculate visible portion */
    int char_width = font_get_width();
    int max_chars = width / char_width;
    int total_chars = strlen(str);

    int start_char = scroll_offset / char_width;
    if (start_char >= total_chars) {
        start_char = 0;
    }

    /* Draw visible characters */
    char buf[64];
    int len = 0;
    for (int i = start_char; i < total_chars && len < max_chars && len < 63; i++) {
        buf[len++] = str[i];
    }
    buf[len] = '\0';

    /* Clip drawing area */
    int draw_x = x - (scroll_offset % char_width);
    font_draw_string(draw_x, y, buf, color);
}

/*
 * Draw truncated text with ellipsis
 */
void text_draw_ellipsis(int x, int y, int width, const char* str, int color) {
    int text_width = font_string_width(str);

    if (text_width <= width) {
        font_draw_string(x, y, str, color);
        return;
    }

    /* Calculate how many characters fit with ellipsis */
    int char_width = font_get_width();
    int ellipsis_width = char_width * 3;  /* "..." */
    int available = width - ellipsis_width;
    int chars = available / char_width;

    if (chars < 1) {
        font_draw_string(x, y, "...", color);
        return;
    }

    /* Draw truncated text */
    char buf[64];
    int len = 0;
    while (str[len] && len < chars && len < 60) {
        buf[len] = str[len];
        len++;
    }
    buf[len++] = '.';
    buf[len++] = '.';
    buf[len++] = '.';
    buf[len] = '\0';

    font_draw_string(x, y, buf, color);
}

/*
 * Draw number as string
 */
void text_draw_number(int x, int y, int num, int color) {
    char buf[16];
    int i = 0;
    int negative = 0;

    if (num < 0) {
        negative = 1;
        num = -num;
    }

    if (num == 0) {
        buf[i++] = '0';
    } else {
        while (num > 0) {
            buf[i++] = '0' + (num % 10);
            num /= 10;
        }
    }

    if (negative) {
        buf[i++] = '-';
    }

    /* Reverse string */
    char reversed[16];
    int j = 0;
    while (i > 0) {
        reversed[j++] = buf[--i];
    }
    reversed[j] = '\0';

    font_draw_string(x, y, reversed, color);
}

/*
 * Draw time in MM:SS format
 */
void text_draw_time(int x, int y, int seconds, int color) {
    char buf[8];
    int mins = seconds / 60;
    int secs = seconds % 60;

    buf[0] = '0' + (mins / 10);
    buf[1] = '0' + (mins % 10);
    buf[2] = ':';
    buf[3] = '0' + (secs / 10);
    buf[4] = '0' + (secs % 10);
    buf[5] = '\0';

    font_draw_string(x, y, buf, color);
}

/*
 * Draw progress bar
 */
void text_draw_progress_bar(int x, int y, int width, int height,
                            int progress, int color) {
    /* Draw outline */
    fb_rect(x, y, width, height, color ? 0 : 1);

    /* Draw fill */
    int fill_width = (width - 2) * progress / 100;
    if (fill_width > 0) {
        fb_fill_rect(x + 1, y + 1, fill_width, height - 2, color ? 0 : 1);
    }
}

/*
 * Calculate text height for wrapped text
 */
int text_calc_wrapped_height(int width, const char* str) {
    int char_width = font_get_width();
    int char_height = font_get_height();
    int chars_per_line = width / char_width;

    if (chars_per_line < 1) chars_per_line = 1;

    int lines = 1;
    int col = 0;

    while (*str) {
        if (*str == '\n') {
            lines++;
            col = 0;
        } else {
            col++;
            if (col >= chars_per_line) {
                lines++;
                col = 0;
            }
        }
        str++;
    }

    return lines * (char_height + 1);
}
