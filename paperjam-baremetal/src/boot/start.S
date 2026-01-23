/*
 * PaperJam Bare-Metal OS - Boot Code
 * Raspberry Pi Zero 2 W (BCM2710, ARM Cortex-A53)
 *
 * This is the entry point for the kernel. The GPU bootloader
 * loads us at 0x80000 and jumps here with:
 * - x0 = 32-bit pointer to DTB in memory
 * - x1 = 0 (reserved)
 * - x2 = 0 (reserved)
 * - x3 = 0 (reserved)
 */

.section ".text.boot"

.global _start

_start:
    /* Check processor ID - only core 0 should continue */
    mrs     x1, mpidr_el1
    and     x1, x1, #3
    cbz     x1, core0_boot

    /* Other cores: park in WFI loop */
core_park:
    wfi
    b       core_park

core0_boot:
    /* Save DTB pointer */
    mov     x19, x0

    /* Set up exception level */
    /* We should be in EL2, drop to EL1 */
    mrs     x0, CurrentEL
    and     x0, x0, #0x0C
    cmp     x0, #0x08           /* EL2? */
    b.ne    el1_entry

    /* Configure EL2 -> EL1 transition */
    mov     x0, #(1 << 31)      /* EL1 is AArch64 */
    msr     hcr_el2, x0

    mov     x0, #0x3C5          /* EL1h, IRQ/FIQ/Abort masked */
    msr     spsr_el2, x0

    adr     x0, el1_entry
    msr     elr_el2, x0
    eret

el1_entry:
    /* Disable MMU and caches for now */
    mov     x0, #0
    msr     sctlr_el1, x0

    /* Set up stack pointer (4MB mark, grows down) */
    ldr     x0, =__stack_start
    mov     sp, x0

    /* Clear BSS section */
    ldr     x0, =__bss_start
    ldr     x1, =__bss_end
    cmp     x0, x1
    b.ge    bss_done

bss_clear:
    str     xzr, [x0], #8
    cmp     x0, x1
    b.lt    bss_clear

bss_done:
    /* Set up exception vectors */
    ldr     x0, =exception_vectors
    msr     vbar_el1, x0

    /* Enable IRQ */
    msr     daifclr, #2

    /* Restore DTB pointer as argument */
    mov     x0, x19

    /* Jump to C main */
    bl      kernel_main

    /* If main returns, halt */
halt:
    wfi
    b       halt

/*
 * Exception Vector Table
 * Each entry is 128 bytes (32 instructions)
 * 4 exception types x 4 sources = 16 entries
 */
.balign 0x800
.global exception_vectors
exception_vectors:

/* Current EL with SP0 */
.balign 0x80
curr_el_sp0_sync:
    b       sync_handler

.balign 0x80
curr_el_sp0_irq:
    b       irq_handler

.balign 0x80
curr_el_sp0_fiq:
    b       fiq_handler

.balign 0x80
curr_el_sp0_serror:
    b       serror_handler

/* Current EL with SPx */
.balign 0x80
curr_el_spx_sync:
    b       sync_handler

.balign 0x80
curr_el_spx_irq:
    b       irq_handler

.balign 0x80
curr_el_spx_fiq:
    b       fiq_handler

.balign 0x80
curr_el_spx_serror:
    b       serror_handler

/* Lower EL using AArch64 */
.balign 0x80
lower_el_a64_sync:
    b       sync_handler

.balign 0x80
lower_el_a64_irq:
    b       irq_handler

.balign 0x80
lower_el_a64_fiq:
    b       fiq_handler

.balign 0x80
lower_el_a64_serror:
    b       serror_handler

/* Lower EL using AArch32 */
.balign 0x80
lower_el_a32_sync:
    b       sync_handler

.balign 0x80
lower_el_a32_irq:
    b       irq_handler

.balign 0x80
lower_el_a32_fiq:
    b       fiq_handler

.balign 0x80
lower_el_a32_serror:
    b       serror_handler
