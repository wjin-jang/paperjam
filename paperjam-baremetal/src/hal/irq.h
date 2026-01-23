/*
 * PaperJam Bare-Metal OS - IRQ Driver Header
 */

#ifndef IRQ_H
#define IRQ_H

#include "bcm2837.h"

/* IRQ numbers */
#define IRQ_TIMER1      1
#define IRQ_TIMER3      3
#define IRQ_USB         9
#define IRQ_GPIO0       49
#define IRQ_GPIO1       50
#define IRQ_GPIO2       51
#define IRQ_GPIO3       52
#define IRQ_I2C         53
#define IRQ_SPI         54
#define IRQ_UART        57

/* Handler function type */
typedef void (*irq_handler_t)(void);

/* Function prototypes */
void irq_init(void);
void irq_enable(int irq);
void irq_disable(int irq);
void irq_register_handler(int irq, irq_handler_t handler);
void irq_unregister_handler(int irq);
void irq_global_enable(void);
void irq_global_disable(void);
void irq_setup_timer(void);

/* Exception handlers (called from assembly) */
void handle_sync_exception(u64 esr, u64 elr, u64 far);
void handle_irq(void);
void handle_fiq(void);
void handle_serror(u64 esr);

#endif /* IRQ_H */
