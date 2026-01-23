/*
 * PaperJam Bare-Metal OS - GPIO Driver Header
 */

#ifndef GPIO_H
#define GPIO_H

/* GPIO function select values */
#define GPIO_FUNC_INPUT     0
#define GPIO_FUNC_OUTPUT    1
#define GPIO_FUNC_ALT0      4
#define GPIO_FUNC_ALT1      5
#define GPIO_FUNC_ALT2      6
#define GPIO_FUNC_ALT3      7
#define GPIO_FUNC_ALT4      3
#define GPIO_FUNC_ALT5      2

/* GPIO pull-up/down values */
#define GPIO_PULL_NONE      0
#define GPIO_PULL_DOWN      1
#define GPIO_PULL_UP        2

/* Function prototypes */
void gpio_init(void);
void gpio_set_function(int pin, int func);
int  gpio_get_function(int pin);
void gpio_set_pull(int pin, int pull);
void gpio_set(int pin);
void gpio_clear(int pin);
void gpio_write(int pin, int value);
int  gpio_read(int pin);
void gpio_input_pullup(int pin);
void gpio_input_pulldown(int pin);
void gpio_output(int pin);
void gpio_enable_rising_edge(int pin);
void gpio_enable_falling_edge(int pin);
int  gpio_event_detected(int pin);
void gpio_clear_event(int pin);

#endif /* GPIO_H */
