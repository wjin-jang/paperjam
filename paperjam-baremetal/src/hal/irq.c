/*
 * PaperJam Bare-Metal OS - Interrupt Controller Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 */

#include "bcm2837.h"
#include "irq.h"
#include "timer.h"
#include "uart.h"

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

/* IRQ handler callbacks */
static irq_handler_t irq_handlers[64] = { NULL };

/* Timer tick interval in microseconds */
#define TIMER_TICK_US   1000    /* 1ms ticks */

/*
 * Initialize interrupt controller
 */
void irq_init(void) {
    /* Disable all interrupts */
    *IRQ_DISABLE1 = 0xFFFFFFFF;
    *IRQ_DISABLE2 = 0xFFFFFFFF;
    *IRQ_DISABLE_BASIC = 0xFFFFFFFF;
}

/*
 * Enable an IRQ
 */
void irq_enable(int irq) {
    if (irq < 32) {
        *IRQ_ENABLE1 = (1 << irq);
    } else if (irq < 64) {
        *IRQ_ENABLE2 = (1 << (irq - 32));
    }
}

/*
 * Disable an IRQ
 */
void irq_disable(int irq) {
    if (irq < 32) {
        *IRQ_DISABLE1 = (1 << irq);
    } else if (irq < 64) {
        *IRQ_DISABLE2 = (1 << (irq - 32));
    }
}

/*
 * Register an IRQ handler
 */
void irq_register_handler(int irq, irq_handler_t handler) {
    if (irq >= 0 && irq < 64) {
        irq_handlers[irq] = handler;
    }
}

/*
 * Unregister an IRQ handler
 */
void irq_unregister_handler(int irq) {
    if (irq >= 0 && irq < 64) {
        irq_handlers[irq] = NULL;
    }
}

/*
 * Enable global interrupts
 */
void irq_global_enable(void) {
    __asm__ volatile("msr daifclr, #2" ::: "memory");
}

/*
 * Disable global interrupts
 */
void irq_global_disable(void) {
    __asm__ volatile("msr daifset, #2" ::: "memory");
}

/*
 * Setup system timer interrupt (timer 1)
 */
void irq_setup_timer(void) {
    /* Clear any pending timer match */
    timer_clear_match(TIMER_CHANNEL_1);

    /* Set up first timer interrupt */
    timer_setup_periodic(TIMER_CHANNEL_1, TIMER_TICK_US);

    /* Enable timer 1 interrupt */
    irq_enable(IRQ_TIMER1);
}

/*
 * C handler for synchronous exceptions
 */
void handle_sync_exception(u64 esr, u64 elr, u64 far) {
    uart_puts("\n*** SYNC EXCEPTION ***\n");
    uart_puts("ESR: "); uart_put_hex((u32)(esr >> 32)); uart_put_hex((u32)esr); uart_puts("\n");
    uart_puts("ELR: "); uart_put_hex((u32)(elr >> 32)); uart_put_hex((u32)elr); uart_puts("\n");
    uart_puts("FAR: "); uart_put_hex((u32)(far >> 32)); uart_put_hex((u32)far); uart_puts("\n");

    /* Halt on exception */
    while (1) {
        __asm__ volatile("wfi");
    }
}

/*
 * C handler for IRQ
 */
void handle_irq(void) {
    u32 pending1 = *IRQ_PENDING1;
    u32 pending2 = *IRQ_PENDING2;

    /* Check timer 1 */
    if (pending1 & (1 << IRQ_TIMER1)) {
        if (irq_handlers[IRQ_TIMER1]) {
            irq_handlers[IRQ_TIMER1]();
        } else {
            /* Default: advance timer for next tick */
            timer_advance_periodic(TIMER_CHANNEL_1, TIMER_TICK_US);
        }
    }

    /* Check timer 3 */
    if (pending1 & (1 << IRQ_TIMER3)) {
        if (irq_handlers[IRQ_TIMER3]) {
            irq_handlers[IRQ_TIMER3]();
        } else {
            timer_clear_match(TIMER_CHANNEL_3);
        }
    }

    /* Check other interrupts in pending1 */
    for (int i = 0; i < 32; i++) {
        if ((pending1 & (1 << i)) && irq_handlers[i]) {
            irq_handlers[i]();
        }
    }

    /* Check interrupts in pending2 */
    for (int i = 0; i < 32; i++) {
        if ((pending2 & (1 << i)) && irq_handlers[32 + i]) {
            irq_handlers[32 + i]();
        }
    }
}

/*
 * C handler for FIQ (unused)
 */
void handle_fiq(void) {
    /* FIQ not used */
}

/*
 * C handler for system error
 */
void handle_serror(u64 esr) {
    uart_puts("\n*** SYSTEM ERROR ***\n");
    uart_puts("ESR: "); uart_put_hex((u32)esr); uart_puts("\n");

    while (1) {
        __asm__ volatile("wfi");
    }
}
