/*
 * PaperJam Bare-Metal OS - Main Entry Point
 * Raspberry Pi Zero 2 W Music Player
 *
 * A bare-metal music player with:
 * - E-paper display (250x122, 1-bit)
 * - MP3/FLAC/WAV playback via PWM
 * - PiSugar 3 battery management
 * - GPIO button input
 */

#include "hal/bcm2837.h"
#include "hal/gpio.h"
#include "hal/timer.h"
#include "hal/uart.h"
#include "hal/spi.h"
#include "hal/i2c.h"
#include "hal/pwm.h"
#include "hal/irq.h"
#include "hal/mmc.h"
#include "sys/heap.h"
#include "sys/scheduler.h"
#include "sys/power.h"
#include "drivers/epd_2in13_v4.h"
#include "drivers/pisugar3.h"
#include "drivers/buttons.h"
#include "drivers/audio.h"
#include "lib/fatfs/ff.h"
#include "gfx/framebuffer.h"
#include "gfx/fonts.h"
#include "gfx/text.h"
#include "ui/renderer.h"
#include "ui/music_view.h"
#include "app/player.h"
#include "app/library.h"
#include "app/playlist.h"
#include "app/favorites.h"
#include "app/settings.h"
#include "ui/volume_overlay.h"
#include "ui/context_menu.h"
#include "ui/settings_view.h"
#include "gfx/icons.h"

/* FatFS filesystem object */
static FATFS fatfs;

/* Version info */
#define VERSION_STRING  "PaperJam v1.0"

/*
 * Show boot screen
 */
static void show_boot_screen(void) {
    fb_clear(1);

    /* Draw logo/title */
    text_draw_aligned(0, 100, FB_WIDTH, VERSION_STRING, TEXT_ALIGN_CENTER, 1);
    text_draw_aligned(0, 120, FB_WIDTH, "Bare-Metal OS", TEXT_ALIGN_CENTER, 1);
    text_draw_aligned(0, 140, FB_WIDTH, "Loading...", TEXT_ALIGN_CENTER, 1);

    epd_display(fb_get_buffer());
}

/*
 * Show error screen
 */
static void show_error(const char* msg) {
    fb_clear(1);
    text_draw_aligned(0, 100, FB_WIDTH, "ERROR", TEXT_ALIGN_CENTER, 1);
    text_draw_aligned(0, 120, FB_WIDTH, msg, TEXT_ALIGN_CENTER, 1);
    epd_display(fb_get_buffer());

    /* Wait for button press */
    while (!buttons_any_pressed()) {
        buttons_poll();
        timer_delay_ms(10);
    }
}

/*
 * Button press handler
 */
static void on_button_press(int button) {
    power_activity();
    renderer_handle_button(button);
}

/*
 * Button long press handler
 */
static void on_button_long_press(int button) {
    power_activity();
    renderer_handle_long_press(button);
}

/*
 * Player update task
 */
static void task_player_update(void* data) {
    (void)data;
    player_update();
}

/*
 * UI update task
 */
static void task_ui_update(void* data) {
    (void)data;
    renderer_update();
}

/*
 * Button poll task
 */
static void task_buttons(void* data) {
    (void)data;
    buttons_poll();
}

/*
 * Initialize all hardware
 */
static int init_hardware(void) {
    uart_puts("Initializing hardware...\n");

    /* Initialize GPIO */
    gpio_init();
    uart_puts("  GPIO: OK\n");

    /* Initialize SPI (for e-paper) */
    spi_init();
    uart_puts("  SPI: OK\n");

    /* Initialize I2C (for battery) */
    i2c_init();
    uart_puts("  I2C: OK\n");

    /* Initialize e-paper display */
    epd_init();
    uart_puts("  E-Paper: OK\n");

    /* Show boot screen */
    show_boot_screen();

    /* Initialize PWM audio */
    pwm_init();
    uart_puts("  PWM Audio: OK\n");

    /* Initialize buttons */
    buttons_init();
    buttons_set_press_callback(on_button_press);
    buttons_set_long_press_callback(on_button_long_press);
    uart_puts("  Buttons: OK\n");

    /* Initialize battery monitor */
    if (pisugar_init() < 0) {
        uart_puts("  Battery: FAIL (continuing)\n");
    } else {
        uart_puts("  Battery: OK (");
        uart_put_dec(pisugar_get_battery_level());
        uart_puts("%)\n");
    }

    /* Initialize SD card */
    if (mmc_init() < 0) {
        uart_puts("  SD Card: FAIL\n");
        return -1;
    }
    uart_puts("  SD Card: OK\n");

    /* Mount filesystem */
    if (f_mount(&fatfs, "", 1) != FR_OK) {
        uart_puts("  Filesystem: FAIL\n");
        return -2;
    }
    uart_puts("  Filesystem: OK\n");

    return 0;
}

/*
 * Initialize application
 */
static int init_application(void) {
    uart_puts("Initializing application...\n");

    /* Initialize heap */
    heap_init();
    uart_puts("  Heap: OK (");
    uart_put_dec(heap_get_total() / 1024);
    uart_puts(" KB)\n");

    /* Initialize scheduler */
    scheduler_init();
    uart_puts("  Scheduler: OK\n");

    /* Initialize icons */
    icons_init();

    /* Initialize UI */
    renderer_init();
    volume_overlay_init();
    context_menu_init();
    settings_view_init();
    uart_puts("  UI: OK\n");

    /* Initialize settings */
    settings_init();
    if (settings_load() == 0) {
        uart_puts("  Settings: Loaded\n");
    } else {
        uart_puts("  Settings: Using defaults\n");
    }

    /* Initialize audio */
    audio_init();
    audio_set_volume(settings_get_volume());
    uart_puts("  Audio: OK\n");

    /* Initialize player */
    player_init();
    player_set_shuffle(settings_get_shuffle());
    player_set_repeat(settings_get_repeat_mode());
    uart_puts("  Player: OK\n");

    /* Initialize library */
    library_init();
    uart_puts("  Library: Scanning...\n");
    library_scan();
    uart_puts("    Found ");
    uart_put_dec(library_count_entries());
    uart_puts(" tracks\n");

    /* Initialize queue */
    queue_init();
    uart_puts("  Queue: OK\n");

    /* Load favorites */
    favorites_init();
    favorites_load();
    uart_puts("  Favorites: ");
    uart_put_dec(favorites_count_entries());
    uart_puts(" items\n");

    /* Initialize power management */
    power_init();
    uart_puts("  Power: OK\n");

    return 0;
}

/*
 * Register scheduler tasks
 */
static void register_tasks(void) {
    /* Audio/player update - high priority, fast */
    scheduler_add_task("player", task_player_update, NULL, 5);

    /* Button polling - responsive */
    scheduler_add_task("buttons", task_buttons, NULL, 10);

    /* UI update - moderate */
    scheduler_add_task("ui", task_ui_update, NULL, 50);
}

/*
 * Main kernel entry point
 */
void kernel_main(u64 dtb_ptr) {
    (void)dtb_ptr;

    /* Initialize UART first for debugging */
    uart_init();
    uart_puts("\n\n");
    uart_puts("=================================\n");
    uart_puts("  PaperJam Bare-Metal OS v1.0\n");
    uart_puts("  Raspberry Pi Zero 2 W\n");
    uart_puts("=================================\n\n");

    /* Initialize timer */
    timer_init();
    uart_puts("Timer: OK\n");

    /* Initialize IRQ */
    irq_init();
    irq_setup_timer();
    irq_global_enable();
    uart_puts("IRQ: OK\n\n");

    /* Initialize hardware */
    if (init_hardware() < 0) {
        show_error("Hardware Init Failed");
        power_shutdown();
    }

    /* Initialize application */
    if (init_application() < 0) {
        show_error("App Init Failed");
        power_shutdown();
    }

    uart_puts("\nInitialization complete!\n\n");

    /* Add all tracks to queue */
    queue_add_all();
    uart_puts("Queue: ");
    uart_put_dec(queue_count());
    uart_puts(" tracks\n");

    /* Start playing first track if available */
    if (queue_count() > 0) {
        uart_puts("Starting playback...\n");
        player_play_track(0);
    }

    /* Update display */
    music_view_update_metadata();
    renderer_request_full_refresh();
    renderer_render();

    /* Register scheduler tasks */
    register_tasks();

    uart_puts("Entering main loop...\n\n");

    /* Main loop */
    scheduler_run();

    /* Should never reach here */
    uart_puts("Scheduler stopped - halting\n");
    power_shutdown();
}
