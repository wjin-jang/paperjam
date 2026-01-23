/*
 * PaperJam Bare-Metal OS - Minimal JPEG Decoder
 *
 * Simplified JPEG decoder for album art display on e-paper.
 * Supports baseline JPEG only (no progressive, no arithmetic coding).
 * Outputs 8-bit grayscale for dithering.
 *
 * NOTE: This is a minimal implementation. For better quality/compatibility,
 * consider integrating a full library like picojpeg or nanojpeg.
 */

#include "hal/bcm2837.h"
#include "jpeg.h"
#include "sys/heap.h"

/* JPEG markers */
#define JPEG_SOI    0xD8    /* Start of image */
#define JPEG_EOI    0xD9    /* End of image */
#define JPEG_SOF0   0xC0    /* Start of frame (baseline) */
#define JPEG_SOF2   0xC2    /* Start of frame (progressive) */
#define JPEG_DHT    0xC4    /* Define Huffman table */
#define JPEG_DQT    0xDB    /* Define quantization table */
#define JPEG_DRI    0xDD    /* Define restart interval */
#define JPEG_SOS    0xDA    /* Start of scan */
#define JPEG_APP0   0xE0    /* APP0 (JFIF) */
#define JPEG_APP1   0xE1    /* APP1 (EXIF) */
#define JPEG_COM    0xFE    /* Comment */

/* Maximum dimensions for album art */
#define MAX_WIDTH   250
#define MAX_HEIGHT  250
#define MAX_COMPONENTS 3

/* Huffman table */
typedef struct {
    u8 bits[16];
    u8 values[256];
    u16 codes[256];
    u8 sizes[256];
    int num_codes;
} huffman_table_t;

/* JPEG decoder context */
typedef struct {
    const u8* data;
    u32 data_size;
    u32 pos;

    /* Image info */
    u16 width;
    u16 height;
    u8 num_components;
    u8 precision;

    /* Component info */
    struct {
        u8 id;
        u8 h_samp;
        u8 v_samp;
        u8 qt_id;
        u8 dc_table;
        u8 ac_table;
    } components[MAX_COMPONENTS];

    /* Quantization tables */
    u8 quant_tables[4][64];
    int quant_valid[4];

    /* Huffman tables */
    huffman_table_t dc_tables[4];
    huffman_table_t ac_tables[4];

    /* Decode state */
    u32 bit_buffer;
    int bits_in_buffer;
    int restart_interval;

    /* DC predictors */
    i16 dc_pred[MAX_COMPONENTS];

    /* Output buffer */
    u8* output;
    int output_width;
    int output_height;
} jpeg_decoder_t;

/* ZigZag order for DCT coefficients */
static const u8 zigzag[64] = {
     0,  1,  8, 16,  9,  2,  3, 10,
    17, 24, 32, 25, 18, 11,  4,  5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13,  6,  7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63
};

/*
 * Read byte from input
 */
static int jpeg_read_byte(jpeg_decoder_t* ctx) {
    if (ctx->pos >= ctx->data_size) return -1;
    return ctx->data[ctx->pos++];
}

/*
 * Read 16-bit big-endian value
 */
static int jpeg_read_u16(jpeg_decoder_t* ctx) {
    int hi = jpeg_read_byte(ctx);
    int lo = jpeg_read_byte(ctx);
    if (hi < 0 || lo < 0) return -1;
    return (hi << 8) | lo;
}

/*
 * Skip bytes
 */
static void jpeg_skip(jpeg_decoder_t* ctx, int count) {
    ctx->pos += count;
    if (ctx->pos > ctx->data_size) ctx->pos = ctx->data_size;
}

/*
 * Get bits from bitstream
 */
static int jpeg_get_bits(jpeg_decoder_t* ctx, int num_bits) {
    if (num_bits == 0) return 0;

    while (ctx->bits_in_buffer < num_bits) {
        int byte = jpeg_read_byte(ctx);
        if (byte < 0) return -1;

        if (byte == 0xFF) {
            /* Stuffed byte - skip 0x00 */
            int next = jpeg_read_byte(ctx);
            if (next != 0) {
                /* Marker - shouldn't happen in scan data */
                ctx->pos -= 2;
                return -1;
            }
        }

        ctx->bit_buffer = (ctx->bit_buffer << 8) | byte;
        ctx->bits_in_buffer += 8;
    }

    ctx->bits_in_buffer -= num_bits;
    return (ctx->bit_buffer >> ctx->bits_in_buffer) & ((1 << num_bits) - 1);
}

/*
 * Decode Huffman code
 */
static int jpeg_decode_huffman(jpeg_decoder_t* ctx, huffman_table_t* table) {
    int code = 0;

    for (int bits = 1; bits <= 16; bits++) {
        int bit = jpeg_get_bits(ctx, 1);
        if (bit < 0) return -1;

        code = (code << 1) | bit;

        for (int i = 0; i < table->num_codes; i++) {
            if (table->sizes[i] == bits && table->codes[i] == code) {
                return table->values[i];
            }
        }
    }

    return -1;  /* Invalid code */
}

/*
 * Parse Huffman table
 */
static int jpeg_parse_dht(jpeg_decoder_t* ctx, int length) {
    while (length > 0) {
        int info = jpeg_read_byte(ctx);
        if (info < 0) return -1;
        length--;

        int table_class = (info >> 4) & 0x0F;  /* 0=DC, 1=AC */
        int table_id = info & 0x0F;

        if (table_id > 3) return -1;

        huffman_table_t* table = (table_class == 0) ?
            &ctx->dc_tables[table_id] : &ctx->ac_tables[table_id];

        /* Read bit counts */
        int total = 0;
        for (int i = 0; i < 16; i++) {
            table->bits[i] = jpeg_read_byte(ctx);
            total += table->bits[i];
            length--;
        }

        if (total > 256) return -1;

        /* Read values */
        for (int i = 0; i < total; i++) {
            table->values[i] = jpeg_read_byte(ctx);
            length--;
        }

        /* Generate codes */
        int code = 0;
        int idx = 0;
        for (int bits = 1; bits <= 16; bits++) {
            for (int i = 0; i < table->bits[bits - 1]; i++) {
                table->codes[idx] = code;
                table->sizes[idx] = bits;
                idx++;
                code++;
            }
            code <<= 1;
        }
        table->num_codes = idx;
    }

    return 0;
}

/*
 * Parse quantization table
 */
static int jpeg_parse_dqt(jpeg_decoder_t* ctx, int length) {
    while (length > 0) {
        int info = jpeg_read_byte(ctx);
        if (info < 0) return -1;
        length--;

        int precision = (info >> 4) & 0x0F;  /* 0=8-bit, 1=16-bit */
        int table_id = info & 0x0F;

        if (table_id > 3) return -1;

        for (int i = 0; i < 64; i++) {
            if (precision) {
                int val = jpeg_read_u16(ctx);
                ctx->quant_tables[table_id][zigzag[i]] = val > 255 ? 255 : val;
                length -= 2;
            } else {
                ctx->quant_tables[table_id][zigzag[i]] = jpeg_read_byte(ctx);
                length--;
            }
        }

        ctx->quant_valid[table_id] = 1;
    }

    return 0;
}

/*
 * Parse SOF (Start of Frame)
 */
static int jpeg_parse_sof(jpeg_decoder_t* ctx, int length) {
    ctx->precision = jpeg_read_byte(ctx);
    ctx->height = jpeg_read_u16(ctx);
    ctx->width = jpeg_read_u16(ctx);
    ctx->num_components = jpeg_read_byte(ctx);

    if (ctx->num_components > MAX_COMPONENTS) return -1;
    if (ctx->width > MAX_WIDTH || ctx->height > MAX_HEIGHT) return -1;

    for (int i = 0; i < ctx->num_components; i++) {
        ctx->components[i].id = jpeg_read_byte(ctx);
        int sampling = jpeg_read_byte(ctx);
        ctx->components[i].h_samp = (sampling >> 4) & 0x0F;
        ctx->components[i].v_samp = sampling & 0x0F;
        ctx->components[i].qt_id = jpeg_read_byte(ctx);
    }

    (void)length;
    return 0;
}

/*
 * Parse SOS (Start of Scan)
 */
static int jpeg_parse_sos(jpeg_decoder_t* ctx, int length) {
    int num_components = jpeg_read_byte(ctx);
    (void)length;

    for (int i = 0; i < num_components; i++) {
        int id = jpeg_read_byte(ctx);

        /* Find component */
        for (int j = 0; j < ctx->num_components; j++) {
            if (ctx->components[j].id == id) {
                int tables = jpeg_read_byte(ctx);
                ctx->components[j].dc_table = (tables >> 4) & 0x0F;
                ctx->components[j].ac_table = tables & 0x0F;
                break;
            }
        }
    }

    /* Skip Ss, Se, Ah/Al */
    jpeg_skip(ctx, 3);

    return 0;
}

/*
 * Simplified IDCT (converts DCT block to spatial domain)
 * This is a simple but slow implementation
 */
static void jpeg_idct(i16* block) {
    /* For simplicity, just use DC coefficient scaled */
    /* A proper implementation would do full 8x8 IDCT */
    int dc = block[0] / 8;
    for (int i = 0; i < 64; i++) {
        block[i] = dc;
    }
}

/*
 * Decode one 8x8 block
 */
static int jpeg_decode_block(jpeg_decoder_t* ctx, i16* block, int comp_idx) {
    memset(block, 0, 64 * sizeof(i16));

    int dc_table = ctx->components[comp_idx].dc_table;
    int ac_table = ctx->components[comp_idx].ac_table;
    int qt_id = ctx->components[comp_idx].qt_id;

    /* Decode DC coefficient */
    int dc_size = jpeg_decode_huffman(ctx, &ctx->dc_tables[dc_table]);
    if (dc_size < 0) return -1;

    int dc_value = 0;
    if (dc_size > 0) {
        dc_value = jpeg_get_bits(ctx, dc_size);
        if (dc_value < (1 << (dc_size - 1))) {
            dc_value -= (1 << dc_size) - 1;
        }
    }

    ctx->dc_pred[comp_idx] += dc_value;
    block[0] = ctx->dc_pred[comp_idx] * ctx->quant_tables[qt_id][0];

    /* Decode AC coefficients */
    int idx = 1;
    while (idx < 64) {
        int ac_code = jpeg_decode_huffman(ctx, &ctx->ac_tables[ac_table]);
        if (ac_code < 0) return -1;

        if (ac_code == 0) {
            /* End of block */
            break;
        }

        int zeros = (ac_code >> 4) & 0x0F;
        int ac_size = ac_code & 0x0F;

        if (ac_size == 0) {
            if (zeros == 15) {
                /* ZRL - 16 zeros */
                idx += 16;
                continue;
            }
            break;  /* EOB */
        }

        idx += zeros;
        if (idx >= 64) break;

        int ac_value = jpeg_get_bits(ctx, ac_size);
        if (ac_value < (1 << (ac_size - 1))) {
            ac_value -= (1 << ac_size) - 1;
        }

        block[zigzag[idx]] = ac_value * ctx->quant_tables[qt_id][zigzag[idx]];
        idx++;
    }

    /* Apply IDCT */
    jpeg_idct(block);

    return 0;
}

/*
 * Decode JPEG to grayscale
 */
int jpeg_decode(const u8* data, u32 size, u8* output, int* out_width, int* out_height, int max_width, int max_height) {
    if (!data || !output || !out_width || !out_height) return -1;

    jpeg_decoder_t* ctx = (jpeg_decoder_t*)heap_alloc(sizeof(jpeg_decoder_t));
    if (!ctx) return -1;

    memset(ctx, 0, sizeof(jpeg_decoder_t));
    ctx->data = data;
    ctx->data_size = size;
    ctx->pos = 0;

    /* Parse JPEG markers */
    while (ctx->pos < ctx->data_size) {
        int marker = jpeg_read_byte(ctx);
        if (marker != 0xFF) continue;

        marker = jpeg_read_byte(ctx);
        if (marker < 0) break;

        /* Skip padding FF bytes */
        while (marker == 0xFF) {
            marker = jpeg_read_byte(ctx);
        }

        int length;
        switch (marker) {
            case JPEG_SOI:
                break;

            case JPEG_EOI:
                goto done_parsing;

            case JPEG_SOF0:
                length = jpeg_read_u16(ctx);
                if (jpeg_parse_sof(ctx, length - 2) < 0) goto error;
                break;

            case JPEG_SOF2:
                /* Progressive JPEG not supported */
                goto error;

            case JPEG_DHT:
                length = jpeg_read_u16(ctx);
                if (jpeg_parse_dht(ctx, length - 2) < 0) goto error;
                break;

            case JPEG_DQT:
                length = jpeg_read_u16(ctx);
                if (jpeg_parse_dqt(ctx, length - 2) < 0) goto error;
                break;

            case JPEG_DRI:
                length = jpeg_read_u16(ctx);
                ctx->restart_interval = jpeg_read_u16(ctx);
                break;

            case JPEG_SOS:
                length = jpeg_read_u16(ctx);
                if (jpeg_parse_sos(ctx, length - 2) < 0) goto error;
                goto decode_scan;

            default:
                /* Skip unknown marker */
                if (marker >= 0xC0) {
                    length = jpeg_read_u16(ctx);
                    jpeg_skip(ctx, length - 2);
                }
                break;
        }
    }

decode_scan:
    {
        /* Simplified decode: Just extract luminance (Y) channel */
        int width = ctx->width;
        int height = ctx->height;

        /* Scale if too large */
        int scale = 1;
        while (width / scale > max_width || height / scale > max_height) {
            scale *= 2;
        }

        *out_width = width / scale;
        *out_height = height / scale;

        /* Decode MCUs (simplified: grayscale only) */
        i16 block[64];
        int mcu_x = 0, mcu_y = 0;
        int mcu_count = 0;

        while (mcu_y * 8 < height) {
            /* Reset DC predictor at restart */
            if (ctx->restart_interval > 0 && mcu_count > 0 &&
                (mcu_count % ctx->restart_interval) == 0) {
                for (int i = 0; i < ctx->num_components; i++) {
                    ctx->dc_pred[i] = 0;
                }
                ctx->bits_in_buffer = 0;
            }

            /* Decode Y block(s) */
            for (int v = 0; v < ctx->components[0].v_samp; v++) {
                for (int h = 0; h < ctx->components[0].h_samp; h++) {
                    if (jpeg_decode_block(ctx, block, 0) < 0) goto done_parsing;

                    /* Copy block to output (with scaling) */
                    int bx = mcu_x * 8 * ctx->components[0].h_samp + h * 8;
                    int by = mcu_y * 8 * ctx->components[0].v_samp + v * 8;

                    for (int y = 0; y < 8; y++) {
                        for (int x = 0; x < 8; x++) {
                            int px = (bx + x) / scale;
                            int py = (by + y) / scale;

                            if (px < *out_width && py < *out_height) {
                                int val = block[y * 8 + x] + 128;
                                if (val < 0) val = 0;
                                if (val > 255) val = 255;
                                output[py * (*out_width) + px] = val;
                            }
                        }
                    }
                }
            }

            /* Skip Cb/Cr blocks */
            for (int c = 1; c < ctx->num_components; c++) {
                for (int v = 0; v < ctx->components[c].v_samp; v++) {
                    for (int h = 0; h < ctx->components[c].h_samp; h++) {
                        jpeg_decode_block(ctx, block, c);
                    }
                }
            }

            mcu_x++;
            int mcu_per_row = (width + 8 * ctx->components[0].h_samp - 1) / (8 * ctx->components[0].h_samp);
            if (mcu_x >= mcu_per_row) {
                mcu_x = 0;
                mcu_y++;
            }
            mcu_count++;
        }
    }

done_parsing:
    heap_free(ctx);
    return 0;

error:
    heap_free(ctx);
    return -1;
}

/*
 * Check if data is JPEG
 */
int jpeg_is_jpeg(const u8* data, u32 size) {
    if (size < 3) return 0;
    return data[0] == 0xFF && data[1] == 0xD8 && data[2] == 0xFF;
}
