/*
 * PaperJam Bare-Metal OS - FLAC Decoder
 *
 * Uses dr_flac single-header library for decoding
 * https://github.com/mackron/dr_libs
 */

#include "hal/bcm2837.h"
#include "decoder.h"
#include "sys/heap.h"
#include "fatfs/ff.h"

/* Define size_t for bare-metal */
typedef unsigned long size_t;

/* dr_flac configuration */
#define DR_FLAC_NO_STDIO
#define DR_FLAC_NO_OGG
#define DRFLAC_MALLOC(sz)           heap_alloc(sz)
#define DRFLAC_REALLOC(p, sz)       heap_realloc(p, sz)
#define DRFLAC_FREE(p)              heap_free(p)
#define DRFLAC_COPY_MEMORY(dst, src, sz) memcpy(dst, src, sz)
#define DRFLAC_ZERO_MEMORY(p, sz)   memset(p, 0, sz)

/* Forward declarations for dr_flac callbacks */
typedef struct drflac drflac;

/* FLAC decoder state */
typedef struct {
    FIL* file;
    drflac* flac;
    u32 sample_rate;
    u32 channels;
    u32 total_samples;
    u32 current_sample;
} flac_state_t;

/*
 * dr_flac read callback
 */
static size_t drflac_read_callback(void* pUserData, void* pBufferOut, size_t bytesToRead) {
    FIL* file = (FIL*)pUserData;
    UINT br;
    if (f_read(file, pBufferOut, bytesToRead, &br) != FR_OK) {
        return 0;
    }
    return br;
}

/*
 * dr_flac seek callback
 */
static int drflac_seek_callback(void* pUserData, int offset, int origin) {
    FIL* file = (FIL*)pUserData;
    DWORD new_pos;

    switch (origin) {
        case 0:  /* SEEK_SET */
            new_pos = offset;
            break;
        case 1:  /* SEEK_CUR */
            new_pos = f_tell(file) + offset;
            break;
        case 2:  /* SEEK_END */
            new_pos = f_size(file) + offset;
            break;
        default:
            return 0;
    }

    return f_lseek(file, new_pos) == FR_OK ? 1 : 0;
}

/*
 * Open FLAC file
 * Note: This is a stub - actual implementation requires dr_flac.h
 */
static int flac_open(decoder_context_t* ctx, FIL* file) {
    flac_state_t* flac = (flac_state_t*)heap_alloc(sizeof(flac_state_t));
    if (!flac) return -1;

    memset(flac, 0, sizeof(flac_state_t));
    flac->file = file;
    ctx->decoder_data = flac;

    /*
     * In actual implementation:
     * flac->flac = drflac_open(drflac_read_callback, drflac_seek_callback, file, NULL);
     * if (!flac->flac) { ... }
     * flac->sample_rate = flac->flac->sampleRate;
     * flac->channels = flac->flac->channels;
     * flac->total_samples = flac->flac->totalPCMFrameCount;
     */

    /* Stub: Try to parse FLAC header manually */
    u8 header[42];
    UINT br;
    if (f_read(file, header, 42, &br) != FR_OK || br < 42) {
        heap_free(flac);
        return -2;
    }

    /* Check FLAC signature */
    if (header[0] != 'f' || header[1] != 'L' ||
        header[2] != 'a' || header[3] != 'C') {
        heap_free(flac);
        return -3;
    }

    /* Parse STREAMINFO block (minimal parsing) */
    /* Bytes 18-20: sample rate (20 bits), channels (3 bits), bits per sample (5 bits) */
    flac->sample_rate = ((header[18] << 12) | (header[19] << 4) | (header[20] >> 4));
    flac->channels = ((header[20] >> 1) & 0x07) + 1;

    /* Total samples (36 bits at bytes 21-25, we only use lower 32 bits) */
    flac->total_samples = ((u32)header[22] << 24) |
                          ((u32)header[23] << 16) |
                          ((u32)header[24] << 8) |
                          header[25];

    ctx->sample_rate = flac->sample_rate;
    ctx->channels = flac->channels;
    ctx->total_samples = flac->total_samples;
    ctx->current_sample = 0;
    ctx->state = DECODER_STATE_READY;

    /* Reset file position for actual decoding */
    f_lseek(file, 0);

    return 0;
}

/*
 * Close FLAC decoder
 */
static void flac_close(decoder_context_t* ctx) {
    flac_state_t* flac = (flac_state_t*)ctx->decoder_data;
    if (flac) {
        /* drflac_close(flac->flac); */
        heap_free(flac);
        ctx->decoder_data = NULL;
    }
    ctx->state = DECODER_STATE_IDLE;
}

/*
 * Decode FLAC samples
 * Note: Stub implementation - requires dr_flac for actual decoding
 */
static int flac_decode(decoder_context_t* ctx, i16* buffer, u32 max_samples) {
    flac_state_t* flac = (flac_state_t*)ctx->decoder_data;
    if (!flac) return -1;

    /* Check EOF */
    if (flac->current_sample >= flac->total_samples) {
        return 0;
    }

    /*
     * Actual implementation:
     * u64 frames_read = drflac_read_pcm_frames_s16(flac->flac, max_samples / flac->channels, buffer);
     * return frames_read * flac->channels;
     */

    /* Stub: Return silence for now */
    u32 samples = max_samples;
    if (flac->current_sample + samples > flac->total_samples * flac->channels) {
        samples = (flac->total_samples * flac->channels) - flac->current_sample;
    }
    for (u32 i = 0; i < samples; i++) {
        buffer[i] = 0;
    }
    flac->current_sample += samples / flac->channels;
    ctx->current_sample = flac->current_sample;

    return samples;
}

/*
 * Seek to position
 */
static int flac_seek(decoder_context_t* ctx, u32 sample_pos) {
    flac_state_t* flac = (flac_state_t*)ctx->decoder_data;
    if (!flac) return -1;

    /*
     * Actual implementation:
     * drflac_seek_to_pcm_frame(flac->flac, sample_pos);
     */

    flac->current_sample = sample_pos;
    ctx->current_sample = sample_pos;
    return 0;
}

/*
 * Get metadata
 */
static int flac_get_metadata(decoder_context_t* ctx, audio_metadata_t* meta) {
    flac_state_t* flac = (flac_state_t*)ctx->decoder_data;
    if (!flac) return -1;

    memset(meta, 0, sizeof(audio_metadata_t));
    meta->sample_rate = flac->sample_rate;
    meta->channels = flac->channels;
    meta->duration_ms = (u64)flac->total_samples * 1000 / flac->sample_rate;

    return 0;
}

static u32 flac_get_position(decoder_context_t* ctx) {
    flac_state_t* flac = (flac_state_t*)ctx->decoder_data;
    return flac ? flac->current_sample : 0;
}

static u32 flac_get_total_samples(decoder_context_t* ctx) {
    flac_state_t* flac = (flac_state_t*)ctx->decoder_data;
    return flac ? flac->total_samples : 0;
}

/* FLAC decoder operations */
const decoder_ops_t flac_decoder_ops = {
    .open = flac_open,
    .close = flac_close,
    .decode = flac_decode,
    .seek = flac_seek,
    .get_metadata = flac_get_metadata,
    .get_position = flac_get_position,
    .get_total_samples = flac_get_total_samples
};
