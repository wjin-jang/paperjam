/*
 * PaperJam Bare-Metal OS - Waveshare 2.13" V4 E-Paper Driver
 * 250x122 pixels, 1-bit, SPI interface
 *
 * Pins: RST=17, DC=25, CS=8, BUSY=24
 */

#include "hal/bcm2837.h"
#include "hal/gpio.h"
#include "hal/spi.h"
#include "hal/timer.h"
#include "epd_2in13_v4.h"

/* Display dimensions */
#define EPD_WIDTH       122
#define EPD_HEIGHT      250
#define EPD_WIDTH_BYTES ((EPD_WIDTH + 7) / 8)

/* GPIO pins */
#define PIN_RST         17
#define PIN_DC          25
#define PIN_CS          8
#define PIN_BUSY        24

/* Commands */
#define CMD_DRIVER_OUTPUT       0x01
#define CMD_GATE_VOLTAGE        0x03
#define CMD_SOURCE_VOLTAGE      0x04
#define CMD_DEEP_SLEEP          0x10
#define CMD_DATA_ENTRY_MODE     0x11
#define CMD_SW_RESET            0x12
#define CMD_TEMP_SENSOR         0x18
#define CMD_MASTER_ACTIVATION   0x20
#define CMD_DISPLAY_UPDATE_1    0x21
#define CMD_DISPLAY_UPDATE_2    0x22
#define CMD_WRITE_RAM           0x24
#define CMD_WRITE_RAM_RED       0x26
#define CMD_VCOM_SENSE          0x28
#define CMD_VCOM_DURATION       0x29
#define CMD_WRITE_VCOM          0x2C
#define CMD_WRITE_LUT           0x32
#define CMD_OTP_READ            0x33
#define CMD_OTP_SELECTION       0x37
#define CMD_SET_RAM_X           0x44
#define CMD_SET_RAM_Y           0x45
#define CMD_SET_RAM_X_POS       0x4E
#define CMD_SET_RAM_Y_POS       0x4F

/* Display state */
static int epd_initialized = 0;
static int partial_refresh_count = 0;
#define MAX_PARTIAL_REFRESHES   120

/* Framebuffer (internal copy for partial updates) */
static u8 epd_framebuffer[EPD_WIDTH_BYTES * EPD_HEIGHT];

/*
 * Send command to display
 */
static void epd_send_command(u8 cmd) {
    gpio_clear(PIN_DC);     /* Command mode */
    gpio_clear(PIN_CS);
    spi_write(cmd);
    gpio_set(PIN_CS);
}

/*
 * Send data to display
 */
static void epd_send_data(u8 data) {
    gpio_set(PIN_DC);       /* Data mode */
    gpio_clear(PIN_CS);
    spi_write(data);
    gpio_set(PIN_CS);
}

/*
 * Send multiple data bytes
 */
static void epd_send_data_array(const u8* data, u32 len) {
    gpio_set(PIN_DC);
    gpio_clear(PIN_CS);
    spi_write_bytes(data, len);
    gpio_set(PIN_CS);
}

/*
 * Wait for display to be ready
 */
static void epd_wait_busy(void) {
    u64 start = timer_get_ms();
    while (gpio_read(PIN_BUSY)) {
        if (timer_elapsed_ms(start) > 10000) {
            /* Timeout after 10 seconds */
            break;
        }
        timer_delay_ms(10);
    }
}

/*
 * Hardware reset
 */
static void epd_reset(void) {
    gpio_set(PIN_RST);
    timer_delay_ms(20);
    gpio_clear(PIN_RST);
    timer_delay_ms(2);
    gpio_set(PIN_RST);
    timer_delay_ms(20);
}

/*
 * Set display window
 */
static void epd_set_window(u8 x_start, u8 x_end, u16 y_start, u16 y_end) {
    epd_send_command(CMD_SET_RAM_X);
    epd_send_data(x_start);
    epd_send_data(x_end);

    epd_send_command(CMD_SET_RAM_Y);
    epd_send_data(y_start & 0xFF);
    epd_send_data((y_start >> 8) & 0xFF);
    epd_send_data(y_end & 0xFF);
    epd_send_data((y_end >> 8) & 0xFF);
}

/*
 * Set cursor position
 */
static void epd_set_cursor(u8 x, u16 y) {
    epd_send_command(CMD_SET_RAM_X_POS);
    epd_send_data(x);

    epd_send_command(CMD_SET_RAM_Y_POS);
    epd_send_data(y & 0xFF);
    epd_send_data((y >> 8) & 0xFF);
}

/*
 * Turn on display
 */
static void epd_turn_on_display(void) {
    epd_send_command(CMD_DISPLAY_UPDATE_2);
    epd_send_data(0xF7);
    epd_send_command(CMD_MASTER_ACTIVATION);
    epd_wait_busy();
}

/*
 * Turn on display (partial mode)
 */
static void epd_turn_on_display_partial(void) {
    epd_send_command(CMD_DISPLAY_UPDATE_2);
    epd_send_data(0xFF);
    epd_send_command(CMD_MASTER_ACTIVATION);
    epd_wait_busy();
}

/*
 * Initialize display for full update
 */
void epd_init(void) {
    /* Configure GPIO pins */
    gpio_output(PIN_RST);
    gpio_output(PIN_DC);
    gpio_output(PIN_CS);
    gpio_set_function(PIN_BUSY, GPIO_FUNC_INPUT);
    gpio_set_pull(PIN_BUSY, GPIO_PULL_NONE);

    gpio_set(PIN_CS);
    gpio_set(PIN_RST);

    /* Initialize SPI */
    spi_init();
    spi_set_clock(4000000);  /* 4MHz */

    /* Hardware reset */
    epd_reset();
    epd_wait_busy();

    /* Software reset */
    epd_send_command(CMD_SW_RESET);
    epd_wait_busy();

    /* Driver output control */
    epd_send_command(CMD_DRIVER_OUTPUT);
    epd_send_data((EPD_HEIGHT - 1) & 0xFF);
    epd_send_data(((EPD_HEIGHT - 1) >> 8) & 0xFF);
    epd_send_data(0x00);

    /* Data entry mode: X increment, Y increment */
    epd_send_command(CMD_DATA_ENTRY_MODE);
    epd_send_data(0x03);

    /* Set window */
    epd_set_window(0, EPD_WIDTH_BYTES - 1, 0, EPD_HEIGHT - 1);

    /* Set cursor */
    epd_set_cursor(0, 0);

    /* Use internal temperature sensor */
    epd_send_command(CMD_TEMP_SENSOR);
    epd_send_data(0x80);

    /* Display update control */
    epd_send_command(CMD_DISPLAY_UPDATE_1);
    epd_send_data(0x00);
    epd_send_data(0x80);

    /* Clear framebuffer */
    memset(epd_framebuffer, 0xFF, sizeof(epd_framebuffer));

    epd_initialized = 1;
    partial_refresh_count = 0;
}

/*
 * Initialize for partial update mode
 */
void epd_init_partial(void) {
    epd_reset();
    epd_wait_busy();

    epd_send_command(0x3C);  /* Border waveform */
    epd_send_data(0x80);

    epd_send_command(CMD_DRIVER_OUTPUT);
    epd_send_data((EPD_HEIGHT - 1) & 0xFF);
    epd_send_data(((EPD_HEIGHT - 1) >> 8) & 0xFF);
    epd_send_data(0x00);

    epd_send_command(CMD_DATA_ENTRY_MODE);
    epd_send_data(0x03);

    epd_set_window(0, EPD_WIDTH_BYTES - 1, 0, EPD_HEIGHT - 1);
    epd_set_cursor(0, 0);

    epd_send_command(CMD_TEMP_SENSOR);
    epd_send_data(0x80);

    epd_send_command(CMD_DISPLAY_UPDATE_1);
    epd_send_data(0x00);
    epd_send_data(0x80);
}

/*
 * Clear display to white
 */
void epd_clear(void) {
    u8 white = 0xFF;

    epd_set_window(0, EPD_WIDTH_BYTES - 1, 0, EPD_HEIGHT - 1);
    epd_set_cursor(0, 0);

    epd_send_command(CMD_WRITE_RAM);
    for (int i = 0; i < EPD_WIDTH_BYTES * EPD_HEIGHT; i++) {
        epd_send_data(white);
    }

    epd_turn_on_display();
    memset(epd_framebuffer, 0xFF, sizeof(epd_framebuffer));
    partial_refresh_count = 0;
}

/*
 * Display framebuffer (full refresh)
 */
void epd_display(const u8* image) {
    epd_set_window(0, EPD_WIDTH_BYTES - 1, 0, EPD_HEIGHT - 1);
    epd_set_cursor(0, 0);

    epd_send_command(CMD_WRITE_RAM);
    epd_send_data_array(image, EPD_WIDTH_BYTES * EPD_HEIGHT);

    epd_turn_on_display();

    /* Save to internal buffer for partial updates */
    memcpy(epd_framebuffer, image, EPD_WIDTH_BYTES * EPD_HEIGHT);
    partial_refresh_count = 0;
}

/*
 * Display framebuffer (partial refresh)
 */
void epd_display_partial(const u8* image) {
    /* Check if full refresh needed */
    if (partial_refresh_count >= MAX_PARTIAL_REFRESHES) {
        epd_display(image);
        return;
    }

    epd_init_partial();

    /* Write old data */
    epd_set_window(0, EPD_WIDTH_BYTES - 1, 0, EPD_HEIGHT - 1);
    epd_set_cursor(0, 0);
    epd_send_command(CMD_WRITE_RAM);
    epd_send_data_array(epd_framebuffer, EPD_WIDTH_BYTES * EPD_HEIGHT);

    /* Write new data */
    epd_send_command(CMD_WRITE_RAM_RED);
    epd_send_data_array(image, EPD_WIDTH_BYTES * EPD_HEIGHT);

    epd_turn_on_display_partial();

    /* Save new data */
    memcpy(epd_framebuffer, image, EPD_WIDTH_BYTES * EPD_HEIGHT);
    partial_refresh_count++;
}

/*
 * Enter deep sleep mode
 */
void epd_sleep(void) {
    epd_send_command(CMD_DEEP_SLEEP);
    epd_send_data(0x01);
    timer_delay_ms(100);
    epd_initialized = 0;
}

/*
 * Wake from sleep
 */
void epd_wake(void) {
    epd_init();
}

/*
 * Get display dimensions
 */
int epd_get_width(void) {
    return EPD_WIDTH;
}

int epd_get_height(void) {
    return EPD_HEIGHT;
}

int epd_get_width_bytes(void) {
    return EPD_WIDTH_BYTES;
}

/*
 * Get partial refresh count
 */
int epd_get_partial_count(void) {
    return partial_refresh_count;
}

/*
 * Reset partial refresh count (forces next refresh to be full)
 */
void epd_reset_partial_count(void) {
    partial_refresh_count = MAX_PARTIAL_REFRESHES;
}

/*
 * Check if display is initialized
 */
int epd_is_initialized(void) {
    return epd_initialized;
}
