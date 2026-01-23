/*
 * PaperJam Bare-Metal OS - GPIO Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 */

#include "bcm2837.h"
#include "gpio.h"

/* Delay for pull-up/down sequence */
static void gpio_delay(int count) {
    while (count--) {
        __asm__ volatile("nop");
    }
}

/*
 * Set GPIO pin function
 * pin: GPIO pin number (0-53)
 * func: GPIO_FUNC_INPUT, GPIO_FUNC_OUTPUT, GPIO_FUNC_ALTx
 */
void gpio_set_function(int pin, int func) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gpfsel = GPFSEL0 + (pin / 10);
    int shift = (pin % 10) * 3;

    uint32_t val = *gpfsel;
    val &= ~(0x7 << shift);
    val |= (func & 0x7) << shift;
    *gpfsel = val;
}

/*
 * Get GPIO pin function
 */
int gpio_get_function(int pin) {
    if (pin < 0 || pin > 53) return -1;

    volatile uint32_t* gpfsel = GPFSEL0 + (pin / 10);
    int shift = (pin % 10) * 3;

    return (*gpfsel >> shift) & 0x7;
}

/*
 * Set GPIO pull-up/down
 * pin: GPIO pin number
 * pull: GPIO_PULL_NONE, GPIO_PULL_DOWN, GPIO_PULL_UP
 */
void gpio_set_pull(int pin, int pull) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gppudclk = (pin < 32) ? GPPUDCLK0 : GPPUDCLK1;
    int shift = pin % 32;

    /* Set pull mode */
    *GPPUD = pull;
    gpio_delay(150);

    /* Clock the control signal into the GPIO */
    *gppudclk = (1 << shift);
    gpio_delay(150);

    /* Clear control signal */
    *GPPUD = 0;
    *gppudclk = 0;
}

/*
 * Set GPIO output high
 */
void gpio_set(int pin) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gpset = (pin < 32) ? GPSET0 : GPSET1;
    *gpset = (1 << (pin % 32));
}

/*
 * Set GPIO output low
 */
void gpio_clear(int pin) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gpclr = (pin < 32) ? GPCLR0 : GPCLR1;
    *gpclr = (1 << (pin % 32));
}

/*
 * Write GPIO output
 */
void gpio_write(int pin, int value) {
    if (value) {
        gpio_set(pin);
    } else {
        gpio_clear(pin);
    }
}

/*
 * Read GPIO input
 */
int gpio_read(int pin) {
    if (pin < 0 || pin > 53) return 0;

    volatile uint32_t* gplev = (pin < 32) ? GPLEV0 : GPLEV1;
    return (*gplev >> (pin % 32)) & 1;
}

/*
 * Configure GPIO as input with pull-up
 */
void gpio_input_pullup(int pin) {
    gpio_set_function(pin, GPIO_FUNC_INPUT);
    gpio_set_pull(pin, GPIO_PULL_UP);
}

/*
 * Configure GPIO as input with pull-down
 */
void gpio_input_pulldown(int pin) {
    gpio_set_function(pin, GPIO_FUNC_INPUT);
    gpio_set_pull(pin, GPIO_PULL_DOWN);
}

/*
 * Configure GPIO as output
 */
void gpio_output(int pin) {
    gpio_set_function(pin, GPIO_FUNC_OUTPUT);
}

/*
 * Enable rising edge detect
 */
void gpio_enable_rising_edge(int pin) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gpren = (pin < 32) ? GPREN0 : GPREN1;
    *gpren |= (1 << (pin % 32));
}

/*
 * Enable falling edge detect
 */
void gpio_enable_falling_edge(int pin) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gpfen = (pin < 32) ? GPFEN0 : GPFEN1;
    *gpfen |= (1 << (pin % 32));
}

/*
 * Check event detect status
 */
int gpio_event_detected(int pin) {
    if (pin < 0 || pin > 53) return 0;

    volatile uint32_t* gpeds = (pin < 32) ? GPEDS0 : GPEDS1;
    return (*gpeds >> (pin % 32)) & 1;
}

/*
 * Clear event detect status
 */
void gpio_clear_event(int pin) {
    if (pin < 0 || pin > 53) return;

    volatile uint32_t* gpeds = (pin < 32) ? GPEDS0 : GPEDS1;
    *gpeds = (1 << (pin % 32));
}

/*
 * Initialize GPIO subsystem
 */
void gpio_init(void) {
    /* Nothing special needed for basic GPIO */
    /* Just ensure any previous pull settings are cleared */
    *GPPUD = 0;
}
