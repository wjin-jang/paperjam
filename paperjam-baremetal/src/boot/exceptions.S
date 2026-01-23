/*
 * PaperJam Bare-Metal OS - Exception Handlers
 * Raspberry Pi Zero 2 W (BCM2710, ARM Cortex-A53)
 */

.section ".text.exceptions"

.global sync_handler
.global irq_handler
.global fiq_handler
.global serror_handler

/*
 * Register save/restore macros
 */
.macro save_registers
    sub     sp, sp, #256
    stp     x0, x1, [sp, #0]
    stp     x2, x3, [sp, #16]
    stp     x4, x5, [sp, #32]
    stp     x6, x7, [sp, #48]
    stp     x8, x9, [sp, #64]
    stp     x10, x11, [sp, #80]
    stp     x12, x13, [sp, #96]
    stp     x14, x15, [sp, #112]
    stp     x16, x17, [sp, #128]
    stp     x18, x19, [sp, #144]
    stp     x20, x21, [sp, #160]
    stp     x22, x23, [sp, #176]
    stp     x24, x25, [sp, #192]
    stp     x26, x27, [sp, #208]
    stp     x28, x29, [sp, #224]
    str     x30, [sp, #240]
.endm

.macro restore_registers
    ldp     x0, x1, [sp, #0]
    ldp     x2, x3, [sp, #16]
    ldp     x4, x5, [sp, #32]
    ldp     x6, x7, [sp, #48]
    ldp     x8, x9, [sp, #64]
    ldp     x10, x11, [sp, #80]
    ldp     x12, x13, [sp, #96]
    ldp     x14, x15, [sp, #112]
    ldp     x16, x17, [sp, #128]
    ldp     x18, x19, [sp, #144]
    ldp     x20, x21, [sp, #160]
    ldp     x22, x23, [sp, #176]
    ldp     x24, x25, [sp, #192]
    ldp     x26, x27, [sp, #208]
    ldp     x28, x29, [sp, #224]
    ldr     x30, [sp, #240]
    add     sp, sp, #256
.endm

/*
 * Synchronous exception handler
 * Called for: SVC, undefined instruction, data abort, etc.
 */
sync_handler:
    save_registers

    /* Get exception syndrome register */
    mrs     x0, esr_el1
    mrs     x1, elr_el1
    mrs     x2, far_el1

    /* Call C handler */
    bl      handle_sync_exception

    restore_registers
    eret

/*
 * IRQ handler
 * Called for: Timer, GPIO, UART, etc.
 */
irq_handler:
    save_registers

    /* Call C handler */
    bl      handle_irq

    restore_registers
    eret

/*
 * FIQ handler (not used, but must be defined)
 */
fiq_handler:
    save_registers
    bl      handle_fiq
    restore_registers
    eret

/*
 * System error handler
 */
serror_handler:
    save_registers
    mrs     x0, esr_el1
    bl      handle_serror
    restore_registers
    eret

/*
 * Simple spin delay (for early boot)
 * x0 = iterations
 */
.global spin_delay
spin_delay:
    subs    x0, x0, #1
    bne     spin_delay
    ret
