/*
 * PaperJam Bare-Metal OS Linker Script
 * Raspberry Pi Zero 2 W (BCM2710)
 *
 * Memory Map:
 * 0x00000000 - 0x00007FFF: Exception vectors (32KB)
 * 0x00008000 - 0x0007FFFF: Reserved
 * 0x00080000 - 0x????????: Kernel code and data
 * Top 16MB: GPU memory (configured in config.txt)
 */

ENTRY(_start)

MEMORY
{
    /* 512MB RAM, minus 16MB for GPU */
    RAM (rwx) : ORIGIN = 0x80000, LENGTH = 496M
}

SECTIONS
{
    /* Code section - starts at 0x80000 for AArch64 */
    .text 0x80000 : {
        KEEP(*(.text.boot))     /* Boot code first */
        *(.text.exceptions)     /* Exception handlers */
        *(.text*)               /* All other code */
    } > RAM

    /* Read-only data */
    .rodata : {
        *(.rodata*)
    } > RAM

    /* Initialized data */
    .data : {
        __data_start = .;
        *(.data*)
        __data_end = .;
    } > RAM

    /* Uninitialized data (BSS) */
    .bss : {
        __bss_start = .;
        *(.bss*)
        *(COMMON)
        __bss_end = .;
    } > RAM

    /* Heap starts after BSS */
    . = ALIGN(4096);
    __heap_start = .;

    /* Stack at 4MB mark (grows down) */
    . = 0x400000;
    __stack_start = .;

    /* End of kernel space */
    __kernel_end = .;
}

/* Symbols for startup code */
__bss_size = (__bss_end - __bss_start) >> 3;
