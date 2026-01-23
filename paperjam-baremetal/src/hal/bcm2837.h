/*
 * PaperJam Bare-Metal OS - BCM2837 Register Definitions
 * Raspberry Pi Zero 2 W (BCM2710/BCM2837)
 *
 * Peripheral base address: 0x3F000000 (mapped from 0x7E000000)
 */

#ifndef BCM2837_H
#define BCM2837_H

#include <stdint.h>

/* Peripheral base address for BCM2837 */
#define PERIPHERAL_BASE     0x3F000000

/* GPIO registers */
#define GPIO_BASE           (PERIPHERAL_BASE + 0x200000)
#define GPFSEL0             ((volatile uint32_t*)(GPIO_BASE + 0x00))
#define GPFSEL1             ((volatile uint32_t*)(GPIO_BASE + 0x04))
#define GPFSEL2             ((volatile uint32_t*)(GPIO_BASE + 0x08))
#define GPFSEL3             ((volatile uint32_t*)(GPIO_BASE + 0x0C))
#define GPFSEL4             ((volatile uint32_t*)(GPIO_BASE + 0x10))
#define GPFSEL5             ((volatile uint32_t*)(GPIO_BASE + 0x14))
#define GPSET0              ((volatile uint32_t*)(GPIO_BASE + 0x1C))
#define GPSET1              ((volatile uint32_t*)(GPIO_BASE + 0x20))
#define GPCLR0              ((volatile uint32_t*)(GPIO_BASE + 0x28))
#define GPCLR1              ((volatile uint32_t*)(GPIO_BASE + 0x2C))
#define GPLEV0              ((volatile uint32_t*)(GPIO_BASE + 0x34))
#define GPLEV1              ((volatile uint32_t*)(GPIO_BASE + 0x38))
#define GPEDS0              ((volatile uint32_t*)(GPIO_BASE + 0x40))
#define GPEDS1              ((volatile uint32_t*)(GPIO_BASE + 0x44))
#define GPREN0              ((volatile uint32_t*)(GPIO_BASE + 0x4C))
#define GPREN1              ((volatile uint32_t*)(GPIO_BASE + 0x50))
#define GPFEN0              ((volatile uint32_t*)(GPIO_BASE + 0x58))
#define GPFEN1              ((volatile uint32_t*)(GPIO_BASE + 0x5C))
#define GPHEN0              ((volatile uint32_t*)(GPIO_BASE + 0x64))
#define GPHEN1              ((volatile uint32_t*)(GPIO_BASE + 0x68))
#define GPLEN0              ((volatile uint32_t*)(GPIO_BASE + 0x70))
#define GPLEN1              ((volatile uint32_t*)(GPIO_BASE + 0x74))
#define GPAREN0             ((volatile uint32_t*)(GPIO_BASE + 0x7C))
#define GPAREN1             ((volatile uint32_t*)(GPIO_BASE + 0x80))
#define GPAFEN0             ((volatile uint32_t*)(GPIO_BASE + 0x88))
#define GPAFEN1             ((volatile uint32_t*)(GPIO_BASE + 0x8C))
#define GPPUD               ((volatile uint32_t*)(GPIO_BASE + 0x94))
#define GPPUDCLK0           ((volatile uint32_t*)(GPIO_BASE + 0x98))
#define GPPUDCLK1           ((volatile uint32_t*)(GPIO_BASE + 0x9C))

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

/* System Timer registers */
#define SYSTIMER_BASE       (PERIPHERAL_BASE + 0x3000)
#define SYSTIMER_CS         ((volatile uint32_t*)(SYSTIMER_BASE + 0x00))
#define SYSTIMER_CLO        ((volatile uint32_t*)(SYSTIMER_BASE + 0x04))
#define SYSTIMER_CHI        ((volatile uint32_t*)(SYSTIMER_BASE + 0x08))
#define SYSTIMER_C0         ((volatile uint32_t*)(SYSTIMER_BASE + 0x0C))
#define SYSTIMER_C1         ((volatile uint32_t*)(SYSTIMER_BASE + 0x10))
#define SYSTIMER_C2         ((volatile uint32_t*)(SYSTIMER_BASE + 0x14))
#define SYSTIMER_C3         ((volatile uint32_t*)(SYSTIMER_BASE + 0x18))

/* UART0 (PL011) registers */
#define UART0_BASE          (PERIPHERAL_BASE + 0x201000)
#define UART0_DR            ((volatile uint32_t*)(UART0_BASE + 0x00))
#define UART0_RSRECR        ((volatile uint32_t*)(UART0_BASE + 0x04))
#define UART0_FR            ((volatile uint32_t*)(UART0_BASE + 0x18))
#define UART0_ILPR          ((volatile uint32_t*)(UART0_BASE + 0x20))
#define UART0_IBRD          ((volatile uint32_t*)(UART0_BASE + 0x24))
#define UART0_FBRD          ((volatile uint32_t*)(UART0_BASE + 0x28))
#define UART0_LCRH          ((volatile uint32_t*)(UART0_BASE + 0x2C))
#define UART0_CR            ((volatile uint32_t*)(UART0_BASE + 0x30))
#define UART0_IFLS          ((volatile uint32_t*)(UART0_BASE + 0x34))
#define UART0_IMSC          ((volatile uint32_t*)(UART0_BASE + 0x38))
#define UART0_RIS           ((volatile uint32_t*)(UART0_BASE + 0x3C))
#define UART0_MIS           ((volatile uint32_t*)(UART0_BASE + 0x40))
#define UART0_ICR           ((volatile uint32_t*)(UART0_BASE + 0x44))
#define UART0_DMACR         ((volatile uint32_t*)(UART0_BASE + 0x48))
#define UART0_ITCR          ((volatile uint32_t*)(UART0_BASE + 0x80))
#define UART0_ITIP          ((volatile uint32_t*)(UART0_BASE + 0x84))
#define UART0_ITOP          ((volatile uint32_t*)(UART0_BASE + 0x88))
#define UART0_TDR           ((volatile uint32_t*)(UART0_BASE + 0x8C))

/* UART flag register bits */
#define UART_FR_RXFE        (1 << 4)    /* Receive FIFO empty */
#define UART_FR_TXFF        (1 << 5)    /* Transmit FIFO full */
#define UART_FR_TXFE        (1 << 7)    /* Transmit FIFO empty */
#define UART_FR_BUSY        (1 << 3)    /* UART busy */

/* Mini UART (UART1) registers */
#define AUX_BASE            (PERIPHERAL_BASE + 0x215000)
#define AUX_ENABLES         ((volatile uint32_t*)(AUX_BASE + 0x04))
#define AUX_MU_IO           ((volatile uint32_t*)(AUX_BASE + 0x40))
#define AUX_MU_IER          ((volatile uint32_t*)(AUX_BASE + 0x44))
#define AUX_MU_IIR          ((volatile uint32_t*)(AUX_BASE + 0x48))
#define AUX_MU_LCR          ((volatile uint32_t*)(AUX_BASE + 0x4C))
#define AUX_MU_MCR          ((volatile uint32_t*)(AUX_BASE + 0x50))
#define AUX_MU_LSR          ((volatile uint32_t*)(AUX_BASE + 0x54))
#define AUX_MU_MSR          ((volatile uint32_t*)(AUX_BASE + 0x58))
#define AUX_MU_SCRATCH      ((volatile uint32_t*)(AUX_BASE + 0x5C))
#define AUX_MU_CNTL         ((volatile uint32_t*)(AUX_BASE + 0x60))
#define AUX_MU_STAT         ((volatile uint32_t*)(AUX_BASE + 0x64))
#define AUX_MU_BAUD         ((volatile uint32_t*)(AUX_BASE + 0x68))

/* SPI0 registers (main SPI for e-paper) */
#define SPI0_BASE           (PERIPHERAL_BASE + 0x204000)
#define SPI0_CS             ((volatile uint32_t*)(SPI0_BASE + 0x00))
#define SPI0_FIFO           ((volatile uint32_t*)(SPI0_BASE + 0x04))
#define SPI0_CLK            ((volatile uint32_t*)(SPI0_BASE + 0x08))
#define SPI0_DLEN           ((volatile uint32_t*)(SPI0_BASE + 0x0C))
#define SPI0_LTOH           ((volatile uint32_t*)(SPI0_BASE + 0x10))
#define SPI0_DC             ((volatile uint32_t*)(SPI0_BASE + 0x14))

/* SPI CS register bits */
#define SPI_CS_LEN_LONG     (1 << 25)
#define SPI_CS_DMA_LEN      (1 << 24)
#define SPI_CS_CSPOL2       (1 << 23)
#define SPI_CS_CSPOL1       (1 << 22)
#define SPI_CS_CSPOL0       (1 << 21)
#define SPI_CS_RXF          (1 << 20)
#define SPI_CS_RXR          (1 << 19)
#define SPI_CS_TXD          (1 << 18)
#define SPI_CS_RXD          (1 << 17)
#define SPI_CS_DONE         (1 << 16)
#define SPI_CS_LEN          (1 << 13)
#define SPI_CS_REN          (1 << 12)
#define SPI_CS_ADCS         (1 << 11)
#define SPI_CS_INTR         (1 << 10)
#define SPI_CS_INTD         (1 << 9)
#define SPI_CS_DMAEN        (1 << 8)
#define SPI_CS_TA           (1 << 7)
#define SPI_CS_CSPOL        (1 << 6)
#define SPI_CS_CLEAR_RX     (1 << 5)
#define SPI_CS_CLEAR_TX     (1 << 4)
#define SPI_CS_CPOL         (1 << 3)
#define SPI_CS_CPHA         (1 << 2)
#define SPI_CS_CS1          (1 << 1)
#define SPI_CS_CS0          (1 << 0)

/* I2C (BSC) registers */
#define BSC1_BASE           (PERIPHERAL_BASE + 0x804000)
#define BSC1_C              ((volatile uint32_t*)(BSC1_BASE + 0x00))
#define BSC1_S              ((volatile uint32_t*)(BSC1_BASE + 0x04))
#define BSC1_DLEN           ((volatile uint32_t*)(BSC1_BASE + 0x08))
#define BSC1_A              ((volatile uint32_t*)(BSC1_BASE + 0x0C))
#define BSC1_FIFO           ((volatile uint32_t*)(BSC1_BASE + 0x10))
#define BSC1_DIV            ((volatile uint32_t*)(BSC1_BASE + 0x14))
#define BSC1_DEL            ((volatile uint32_t*)(BSC1_BASE + 0x18))
#define BSC1_CLKT           ((volatile uint32_t*)(BSC1_BASE + 0x1C))

/* I2C control register bits */
#define BSC_C_I2CEN         (1 << 15)
#define BSC_C_INTR          (1 << 10)
#define BSC_C_INTT          (1 << 9)
#define BSC_C_INTD          (1 << 8)
#define BSC_C_ST            (1 << 7)
#define BSC_C_CLEAR         (1 << 4)
#define BSC_C_READ          (1 << 0)

/* I2C status register bits */
#define BSC_S_CLKT          (1 << 9)
#define BSC_S_ERR           (1 << 8)
#define BSC_S_RXF           (1 << 7)
#define BSC_S_TXE           (1 << 6)
#define BSC_S_RXD           (1 << 5)
#define BSC_S_TXD           (1 << 4)
#define BSC_S_RXR           (1 << 3)
#define BSC_S_TXW           (1 << 2)
#define BSC_S_DONE          (1 << 1)
#define BSC_S_TA            (1 << 0)

/* PWM registers */
#define PWM_BASE            (PERIPHERAL_BASE + 0x20C000)
#define PWM_CTL             ((volatile uint32_t*)(PWM_BASE + 0x00))
#define PWM_STA             ((volatile uint32_t*)(PWM_BASE + 0x04))
#define PWM_DMAC            ((volatile uint32_t*)(PWM_BASE + 0x08))
#define PWM_RNG1            ((volatile uint32_t*)(PWM_BASE + 0x10))
#define PWM_DAT1            ((volatile uint32_t*)(PWM_BASE + 0x14))
#define PWM_FIF1            ((volatile uint32_t*)(PWM_BASE + 0x18))
#define PWM_RNG2            ((volatile uint32_t*)(PWM_BASE + 0x20))
#define PWM_DAT2            ((volatile uint32_t*)(PWM_BASE + 0x24))

/* PWM control register bits */
#define PWM_CTL_MSEN2       (1 << 15)
#define PWM_CTL_USEF2       (1 << 13)
#define PWM_CTL_POLA2       (1 << 12)
#define PWM_CTL_SBIT2       (1 << 11)
#define PWM_CTL_RPTL2       (1 << 10)
#define PWM_CTL_MODE2       (1 << 9)
#define PWM_CTL_PWEN2       (1 << 8)
#define PWM_CTL_MSEN1       (1 << 7)
#define PWM_CTL_CLRF1       (1 << 6)
#define PWM_CTL_USEF1       (1 << 5)
#define PWM_CTL_POLA1       (1 << 4)
#define PWM_CTL_SBIT1       (1 << 3)
#define PWM_CTL_RPTL1       (1 << 2)
#define PWM_CTL_MODE1       (1 << 1)
#define PWM_CTL_PWEN1       (1 << 0)

/* Clock manager registers */
#define CM_BASE             (PERIPHERAL_BASE + 0x101000)
#define CM_PWMCTL           ((volatile uint32_t*)(CM_BASE + 0xA0))
#define CM_PWMDIV           ((volatile uint32_t*)(CM_BASE + 0xA4))

/* Clock manager password */
#define CM_PASSWORD         0x5A000000

/* EMMC/SD card registers */
#define EMMC_BASE           (PERIPHERAL_BASE + 0x300000)
#define EMMC_ARG2           ((volatile uint32_t*)(EMMC_BASE + 0x00))
#define EMMC_BLKSIZECNT     ((volatile uint32_t*)(EMMC_BASE + 0x04))
#define EMMC_ARG1           ((volatile uint32_t*)(EMMC_BASE + 0x08))
#define EMMC_CMDTM          ((volatile uint32_t*)(EMMC_BASE + 0x0C))
#define EMMC_RESP0          ((volatile uint32_t*)(EMMC_BASE + 0x10))
#define EMMC_RESP1          ((volatile uint32_t*)(EMMC_BASE + 0x14))
#define EMMC_RESP2          ((volatile uint32_t*)(EMMC_BASE + 0x18))
#define EMMC_RESP3          ((volatile uint32_t*)(EMMC_BASE + 0x1C))
#define EMMC_DATA           ((volatile uint32_t*)(EMMC_BASE + 0x20))
#define EMMC_STATUS         ((volatile uint32_t*)(EMMC_BASE + 0x24))
#define EMMC_CONTROL0       ((volatile uint32_t*)(EMMC_BASE + 0x28))
#define EMMC_CONTROL1       ((volatile uint32_t*)(EMMC_BASE + 0x2C))
#define EMMC_INTERRUPT      ((volatile uint32_t*)(EMMC_BASE + 0x30))
#define EMMC_IRPT_MASK      ((volatile uint32_t*)(EMMC_BASE + 0x34))
#define EMMC_IRPT_EN        ((volatile uint32_t*)(EMMC_BASE + 0x38))
#define EMMC_CONTROL2       ((volatile uint32_t*)(EMMC_BASE + 0x3C))
#define EMMC_FORCE_IRPT     ((volatile uint32_t*)(EMMC_BASE + 0x50))
#define EMMC_BOOT_TIMEOUT   ((volatile uint32_t*)(EMMC_BASE + 0x70))
#define EMMC_DBG_SEL        ((volatile uint32_t*)(EMMC_BASE + 0x74))
#define EMMC_EXRDFIFO_CFG   ((volatile uint32_t*)(EMMC_BASE + 0x80))
#define EMMC_EXRDFIFO_EN    ((volatile uint32_t*)(EMMC_BASE + 0x84))
#define EMMC_TUNE_STEP      ((volatile uint32_t*)(EMMC_BASE + 0x88))
#define EMMC_TUNE_STEPS_STD ((volatile uint32_t*)(EMMC_BASE + 0x8C))
#define EMMC_TUNE_STEPS_DDR ((volatile uint32_t*)(EMMC_BASE + 0x90))
#define EMMC_SPI_INT_SPT    ((volatile uint32_t*)(EMMC_BASE + 0xF0))
#define EMMC_SLOTISR_VER    ((volatile uint32_t*)(EMMC_BASE + 0xFC))

/* Interrupt controller registers */
#define IRQ_BASE            (PERIPHERAL_BASE + 0xB200)
#define IRQ_BASIC_PENDING   ((volatile uint32_t*)(IRQ_BASE + 0x00))
#define IRQ_PENDING1        ((volatile uint32_t*)(IRQ_BASE + 0x04))
#define IRQ_PENDING2        ((volatile uint32_t*)(IRQ_BASE + 0x08))
#define IRQ_FIQ_CTRL        ((volatile uint32_t*)(IRQ_BASE + 0x0C))
#define IRQ_ENABLE1         ((volatile uint32_t*)(IRQ_BASE + 0x10))
#define IRQ_ENABLE2         ((volatile uint32_t*)(IRQ_BASE + 0x14))
#define IRQ_ENABLE_BASIC    ((volatile uint32_t*)(IRQ_BASE + 0x18))
#define IRQ_DISABLE1        ((volatile uint32_t*)(IRQ_BASE + 0x1C))
#define IRQ_DISABLE2        ((volatile uint32_t*)(IRQ_BASE + 0x20))
#define IRQ_DISABLE_BASIC   ((volatile uint32_t*)(IRQ_BASE + 0x24))

/* Mailbox registers (for VideoCore communication) */
#define MAILBOX_BASE        (PERIPHERAL_BASE + 0xB880)
#define MAILBOX_READ        ((volatile uint32_t*)(MAILBOX_BASE + 0x00))
#define MAILBOX_STATUS      ((volatile uint32_t*)(MAILBOX_BASE + 0x18))
#define MAILBOX_WRITE       ((volatile uint32_t*)(MAILBOX_BASE + 0x20))

#define MAILBOX_FULL        0x80000000
#define MAILBOX_EMPTY       0x40000000

/* Power management */
#define PM_BASE             (PERIPHERAL_BASE + 0x100000)
#define PM_RSTC             ((volatile uint32_t*)(PM_BASE + 0x1C))
#define PM_WDOG             ((volatile uint32_t*)(PM_BASE + 0x24))
#define PM_PASSWORD         0x5A000000

/* Helper macros */
#define BIT(n)              (1UL << (n))
#define ARRAY_SIZE(a)       (sizeof(a) / sizeof((a)[0]))

/* Memory barrier macros */
static inline void dmb(void) { __asm__ volatile("dmb sy" ::: "memory"); }
static inline void dsb(void) { __asm__ volatile("dsb sy" ::: "memory"); }
static inline void isb(void) { __asm__ volatile("isb" ::: "memory"); }

/* Standard types */
typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int8_t   i8;
typedef int16_t  i16;
typedef int32_t  i32;
typedef int64_t  i64;

/* Boolean type */
typedef int bool;
#define true  1
#define false 0

/* NULL */
#ifndef NULL
#define NULL ((void*)0)
#endif

#endif /* BCM2837_H */
