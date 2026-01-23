/*
 * PaperJam Bare-Metal OS - SD/MMC Card Driver
 * Raspberry Pi Zero 2 W (BCM2837)
 *
 * Implements SD card access via EMMC controller
 * Supports SD 2.0 (SDHC) cards
 */

#include "bcm2837.h"
#include "mmc.h"
#include "gpio.h"
#include "timer.h"
#include "uart.h"

/* SD Commands */
#define CMD_GO_IDLE         0
#define CMD_ALL_SEND_CID    2
#define CMD_SEND_REL_ADDR   3
#define CMD_SELECT_CARD     7
#define CMD_SEND_IF_COND    8
#define CMD_STOP_TRANS      12
#define CMD_SET_BLOCKLEN    16
#define CMD_READ_SINGLE     17
#define CMD_READ_MULTI      18
#define CMD_WRITE_SINGLE    24
#define CMD_WRITE_MULTI     25
#define CMD_APP_CMD         55
#define CMD_READ_OCR        58

/* App Commands (preceded by CMD55) */
#define ACMD_SET_BUS_WIDTH  6
#define ACMD_SD_STATUS      13
#define ACMD_SEND_OP_COND   41
#define ACMD_SEND_SCR       51

/* Command flags */
#define CMD_NEED_APP        0x80000000
#define CMD_RSPNS_48        0x00020000
#define CMD_ERRORS_MASK     0xFFF9C004
#define CMD_RCA_MASK        0xFFFF0000
#define CMD_RSPNS_136       0x00010000
#define CMD_RSPNS_48B       0x00030000
#define CMD_DATA_READ       0x00000010
#define CMD_DATA_WRITE      0x00000000
#define CMD_IS_DATA         0x00200000
#define CMD_CRCCHK_EN       0x00080000
#define CMD_IXCHK_EN        0x00100000

/* Status bits */
#define SR_READ_AVAILABLE   0x00000800
#define SR_WRITE_AVAILABLE  0x00000400
#define SR_DAT_INHIBIT      0x00000002
#define SR_CMD_INHIBIT      0x00000001

/* Interrupt bits */
#define INT_DATA_TIMEOUT    0x00100000
#define INT_CMD_TIMEOUT     0x00010000
#define INT_READ_RDY        0x00000020
#define INT_WRITE_RDY       0x00000010
#define INT_DATA_DONE       0x00000002
#define INT_CMD_DONE        0x00000001
#define INT_ERROR_MASK      0x017F8000

/* Card state */
static u32 sd_rca = 0;
static u32 sd_ocr = 0;
static int sd_hcs = 0;     /* High Capacity Support */
static int sd_initialized = 0;

/* Block size */
#define SD_BLOCK_SIZE       512

/*
 * Wait for command inhibit to clear
 */
static int mmc_wait_cmd_ready(void) {
    u64 start = timer_get_ms();
    while (*EMMC_STATUS & SR_CMD_INHIBIT) {
        if (timer_elapsed_ms(start) > 1000) {
            return -1;
        }
    }
    return 0;
}

/*
 * Wait for data inhibit to clear
 */
static int mmc_wait_data_ready(void) {
    u64 start = timer_get_ms();
    while (*EMMC_STATUS & SR_DAT_INHIBIT) {
        if (timer_elapsed_ms(start) > 1000) {
            return -1;
        }
    }
    return 0;
}

/*
 * Send a command to the SD card
 */
static int mmc_send_cmd(u32 cmd, u32 arg) {
    /* Handle app commands */
    if (cmd & CMD_NEED_APP) {
        /* Send CMD55 first */
        if (mmc_send_cmd(CMD_APP_CMD | CMD_RSPNS_48, sd_rca) < 0) {
            return -1;
        }
        cmd &= ~CMD_NEED_APP;
    }

    /* Wait for command ready */
    if (mmc_wait_cmd_ready() < 0) {
        return -1;
    }

    /* Clear interrupt status */
    *EMMC_INTERRUPT = *EMMC_INTERRUPT;

    /* Set argument and issue command */
    *EMMC_ARG1 = arg;
    *EMMC_CMDTM = cmd;

    /* Wait for command complete */
    u64 start = timer_get_ms();
    while (!(*EMMC_INTERRUPT & (INT_CMD_DONE | INT_CMD_TIMEOUT | INT_ERROR_MASK))) {
        if (timer_elapsed_ms(start) > 1000) {
            return -2;
        }
    }

    u32 irq = *EMMC_INTERRUPT;
    *EMMC_INTERRUPT = irq;

    if (irq & INT_CMD_TIMEOUT) {
        return -3;
    }
    if (irq & INT_ERROR_MASK) {
        return -4;
    }

    return 0;
}

/*
 * Get command response
 */
static u32 mmc_get_response(int n) {
    switch (n) {
        case 0: return *EMMC_RESP0;
        case 1: return *EMMC_RESP1;
        case 2: return *EMMC_RESP2;
        case 3: return *EMMC_RESP3;
        default: return 0;
    }
}

/*
 * Reset EMMC controller
 */
static int mmc_reset(void) {
    /* Reset host controller */
    *EMMC_CONTROL0 = 0;
    *EMMC_CONTROL1 = 0x01000000;  /* Reset all */

    /* Wait for reset to complete */
    u64 start = timer_get_ms();
    while (*EMMC_CONTROL1 & 0x07000000) {
        if (timer_elapsed_ms(start) > 100) {
            return -1;
        }
    }

    /* Enable internal clock */
    *EMMC_CONTROL1 = 0x000E0001;

    /* Wait for clock stable */
    start = timer_get_ms();
    while (!(*EMMC_CONTROL1 & 0x00000002)) {
        if (timer_elapsed_ms(start) > 100) {
            return -1;
        }
    }

    /* Enable SD clock */
    *EMMC_CONTROL1 |= 0x00000004;

    /* Clear interrupts */
    *EMMC_INTERRUPT = 0xFFFFFFFF;
    *EMMC_IRPT_MASK = 0xFFFFFFFF;

    return 0;
}

/*
 * Initialize SD card
 */
int mmc_init(void) {
    sd_initialized = 0;

    /* Reset controller */
    if (mmc_reset() < 0) {
        uart_puts("MMC: Reset failed\n");
        return -1;
    }

    timer_delay_ms(10);

    /* CMD0: Go idle */
    mmc_send_cmd(CMD_GO_IDLE, 0);
    timer_delay_ms(10);

    /* CMD8: Send interface condition */
    int ret = mmc_send_cmd(CMD_SEND_IF_COND | CMD_RSPNS_48 | CMD_CRCCHK_EN, 0x1AA);
    if (ret < 0) {
        uart_puts("MMC: CMD8 failed (SD 1.x card?)\n");
        sd_hcs = 0;
    } else {
        u32 resp = mmc_get_response(0);
        if ((resp & 0xFFF) != 0x1AA) {
            uart_puts("MMC: CMD8 pattern mismatch\n");
            return -2;
        }
        sd_hcs = 1;
    }

    /* ACMD41: Send operating condition */
    u32 ocr_arg = 0x00FF8000;
    if (sd_hcs) {
        ocr_arg |= 0x40000000;  /* HCS bit */
    }

    u64 start = timer_get_ms();
    do {
        ret = mmc_send_cmd(CMD_NEED_APP | ACMD_SEND_OP_COND | CMD_RSPNS_48, ocr_arg);
        if (ret < 0) {
            uart_puts("MMC: ACMD41 failed\n");
            return -3;
        }
        sd_ocr = mmc_get_response(0);
        if (timer_elapsed_ms(start) > 1000) {
            uart_puts("MMC: Card init timeout\n");
            return -4;
        }
        timer_delay_ms(10);
    } while (!(sd_ocr & 0x80000000));

    /* Check if SDHC */
    sd_hcs = (sd_ocr & 0x40000000) ? 1 : 0;

    /* CMD2: Get CID */
    ret = mmc_send_cmd(CMD_ALL_SEND_CID | CMD_RSPNS_136, 0);
    if (ret < 0) {
        uart_puts("MMC: CMD2 failed\n");
        return -5;
    }

    /* CMD3: Get relative address */
    ret = mmc_send_cmd(CMD_SEND_REL_ADDR | CMD_RSPNS_48, 0);
    if (ret < 0) {
        uart_puts("MMC: CMD3 failed\n");
        return -6;
    }
    sd_rca = mmc_get_response(0) & CMD_RCA_MASK;

    /* CMD7: Select card */
    ret = mmc_send_cmd(CMD_SELECT_CARD | CMD_RSPNS_48B, sd_rca);
    if (ret < 0) {
        uart_puts("MMC: CMD7 failed\n");
        return -7;
    }

    /* Set block size to 512 */
    *EMMC_BLKSIZECNT = (1 << 16) | SD_BLOCK_SIZE;

    /* CMD16: Set block length (for non-SDHC) */
    if (!sd_hcs) {
        ret = mmc_send_cmd(CMD_SET_BLOCKLEN | CMD_RSPNS_48, SD_BLOCK_SIZE);
        if (ret < 0) {
            uart_puts("MMC: CMD16 failed\n");
            return -8;
        }
    }

    sd_initialized = 1;
    uart_puts("MMC: SD card initialized\n");
    return 0;
}

/*
 * Read a single block
 * lba: logical block address (512-byte blocks)
 * buffer: destination buffer (512 bytes)
 */
int mmc_read_block(u32 lba, u8* buffer) {
    if (!sd_initialized) return -1;

    /* For non-SDHC, convert to byte address */
    u32 addr = sd_hcs ? lba : (lba * SD_BLOCK_SIZE);

    /* Wait for data ready */
    if (mmc_wait_data_ready() < 0) {
        return -2;
    }

    /* Set block size and count */
    *EMMC_BLKSIZECNT = (1 << 16) | SD_BLOCK_SIZE;

    /* Send read command */
    int ret = mmc_send_cmd(CMD_READ_SINGLE | CMD_RSPNS_48 | CMD_IS_DATA | CMD_DATA_READ | CMD_CRCCHK_EN, addr);
    if (ret < 0) {
        return -3;
    }

    /* Read data */
    u32* buf32 = (u32*)buffer;
    u64 start = timer_get_ms();

    for (int i = 0; i < SD_BLOCK_SIZE / 4; i++) {
        /* Wait for read available */
        while (!(*EMMC_INTERRUPT & INT_READ_RDY)) {
            if (*EMMC_INTERRUPT & INT_ERROR_MASK) {
                return -4;
            }
            if (timer_elapsed_ms(start) > 1000) {
                return -5;
            }
        }
        buf32[i] = *EMMC_DATA;
    }

    /* Wait for data done */
    start = timer_get_ms();
    while (!(*EMMC_INTERRUPT & INT_DATA_DONE)) {
        if (timer_elapsed_ms(start) > 1000) {
            return -6;
        }
    }

    *EMMC_INTERRUPT = INT_DATA_DONE | INT_READ_RDY;
    return 0;
}

/*
 * Write a single block
 * lba: logical block address
 * buffer: source buffer (512 bytes)
 */
int mmc_write_block(u32 lba, const u8* buffer) {
    if (!sd_initialized) return -1;

    u32 addr = sd_hcs ? lba : (lba * SD_BLOCK_SIZE);

    if (mmc_wait_data_ready() < 0) {
        return -2;
    }

    *EMMC_BLKSIZECNT = (1 << 16) | SD_BLOCK_SIZE;

    int ret = mmc_send_cmd(CMD_WRITE_SINGLE | CMD_RSPNS_48 | CMD_IS_DATA | CMD_DATA_WRITE | CMD_CRCCHK_EN, addr);
    if (ret < 0) {
        return -3;
    }

    const u32* buf32 = (const u32*)buffer;
    u64 start = timer_get_ms();

    for (int i = 0; i < SD_BLOCK_SIZE / 4; i++) {
        while (!(*EMMC_INTERRUPT & INT_WRITE_RDY)) {
            if (*EMMC_INTERRUPT & INT_ERROR_MASK) {
                return -4;
            }
            if (timer_elapsed_ms(start) > 1000) {
                return -5;
            }
        }
        *EMMC_DATA = buf32[i];
    }

    start = timer_get_ms();
    while (!(*EMMC_INTERRUPT & INT_DATA_DONE)) {
        if (timer_elapsed_ms(start) > 1000) {
            return -6;
        }
    }

    *EMMC_INTERRUPT = INT_DATA_DONE | INT_WRITE_RDY;
    return 0;
}

/*
 * Read multiple blocks
 */
int mmc_read_blocks(u32 lba, u8* buffer, u32 count) {
    for (u32 i = 0; i < count; i++) {
        int ret = mmc_read_block(lba + i, buffer + (i * SD_BLOCK_SIZE));
        if (ret < 0) return ret;
    }
    return 0;
}

/*
 * Write multiple blocks
 */
int mmc_write_blocks(u32 lba, const u8* buffer, u32 count) {
    for (u32 i = 0; i < count; i++) {
        int ret = mmc_write_block(lba + i, buffer + (i * SD_BLOCK_SIZE));
        if (ret < 0) return ret;
    }
    return 0;
}

/*
 * Get card status
 */
int mmc_is_initialized(void) {
    return sd_initialized;
}

int mmc_is_sdhc(void) {
    return sd_hcs;
}
