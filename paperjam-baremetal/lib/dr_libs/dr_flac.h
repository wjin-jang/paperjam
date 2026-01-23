/*
 * dr_flac.h - Single-header FLAC decoder
 *
 * This is a minimal implementation for PaperJam bare-metal OS.
 * For the full library, see: https://github.com/mackron/dr_libs
 *
 * Usage:
 *   #define DR_FLAC_IMPLEMENTATION
 *   #include "dr_flac.h"
 */

#ifndef DR_FLAC_H
#define DR_FLAC_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int32_t drflac_int32;
typedef uint32_t drflac_uint32;
typedef int64_t drflac_int64;
typedef uint64_t drflac_uint64;
typedef uint8_t drflac_uint8;
typedef int16_t drflac_int16;
typedef drflac_uint8 drflac_bool8;
typedef drflac_uint32 drflac_bool32;

#define DRFLAC_TRUE     1
#define DRFLAC_FALSE    0

/* Read callback */
typedef size_t (*drflac_read_proc)(void* pUserData, void* pBufferOut, size_t bytesToRead);

/* Seek callback */
typedef drflac_bool32 (*drflac_seek_proc)(void* pUserData, int offset, int origin);

#define drflac_seek_origin_start    0
#define drflac_seek_origin_current  1

/* FLAC stream info */
typedef struct {
    drflac_uint16 minBlockSizeInPCMFrames;
    drflac_uint16 maxBlockSizeInPCMFrames;
    drflac_uint32 minFrameSizeInPCMFrames;
    drflac_uint32 maxFrameSizeInPCMFrames;
    drflac_uint32 sampleRate;
    drflac_uint8 channels;
    drflac_uint8 bitsPerSample;
    drflac_uint64 totalPCMFrameCount;
    drflac_uint8 md5[16];
} drflac_streaminfo;

/* Main FLAC structure */
typedef struct {
    drflac_read_proc onRead;
    drflac_seek_proc onSeek;
    void* pUserData;

    drflac_uint32 sampleRate;
    drflac_uint8 channels;
    drflac_uint8 bitsPerSample;
    drflac_uint64 totalPCMFrameCount;
    drflac_uint64 currentPCMFrame;

    /* Internal state */
    drflac_uint64 firstFramePos;
    drflac_uint64 dataSize;

    /* Decode buffer */
    drflac_int32* pDecodedSamples;
    drflac_uint32 decodedSampleCount;
} drflac;

/* API Functions */
drflac* drflac_open(drflac_read_proc onRead, drflac_seek_proc onSeek, void* pUserData, void* pAllocationCallbacks);
void drflac_close(drflac* pFlac);
drflac_uint64 drflac_read_pcm_frames_s16(drflac* pFlac, drflac_uint64 framesToRead, drflac_int16* pBufferOut);
drflac_uint64 drflac_read_pcm_frames_s32(drflac* pFlac, drflac_uint64 framesToRead, drflac_int32* pBufferOut);
drflac_bool32 drflac_seek_to_pcm_frame(drflac* pFlac, drflac_uint64 pcmFrameIndex);

#ifdef __cplusplus
}
#endif

#endif /* DR_FLAC_H */

/*
 * Implementation
 */
#ifdef DR_FLAC_IMPLEMENTATION

#ifndef DRFLAC_MALLOC
extern void* heap_alloc(uint32_t size);
extern void heap_free(void* ptr);
#define DRFLAC_MALLOC(sz) heap_alloc(sz)
#define DRFLAC_FREE(p) heap_free(p)
#endif

#ifndef DRFLAC_COPY_MEMORY
extern void* memcpy(void* dst, const void* src, uint32_t n);
#define DRFLAC_COPY_MEMORY(dst, src, sz) memcpy(dst, src, sz)
#endif

#ifndef DRFLAC_ZERO_MEMORY
extern void* memset(void* dst, int c, uint32_t n);
#define DRFLAC_ZERO_MEMORY(p, sz) memset(p, 0, sz)
#endif

/* Read big-endian values */
static drflac_uint32 drflac__read_uint32_be(const drflac_uint8* p) {
    return ((drflac_uint32)p[0] << 24) | ((drflac_uint32)p[1] << 16) |
           ((drflac_uint32)p[2] << 8) | p[3];
}

static drflac_uint16 drflac__read_uint16_be(const drflac_uint8* p) {
    return ((drflac_uint16)p[0] << 8) | p[1];
}

/* Parse STREAMINFO block */
static drflac_bool32 drflac__read_streaminfo(drflac* pFlac) {
    drflac_uint8 header[38];

    /* Read "fLaC" marker and STREAMINFO */
    if (pFlac->onRead(pFlac->pUserData, header, 38) != 38) {
        return DRFLAC_FALSE;
    }

    /* Check marker */
    if (header[0] != 'f' || header[1] != 'L' || header[2] != 'a' || header[3] != 'C') {
        return DRFLAC_FALSE;
    }

    /* Parse STREAMINFO (starts at byte 8 after marker + block header) */
    drflac_uint8* si = &header[8];

    pFlac->sampleRate = (si[10] << 12) | (si[11] << 4) | (si[12] >> 4);
    pFlac->channels = ((si[12] >> 1) & 0x07) + 1;
    pFlac->bitsPerSample = ((si[12] & 0x01) << 4) | (si[13] >> 4) + 1;

    pFlac->totalPCMFrameCount =
        ((drflac_uint64)(si[13] & 0x0F) << 32) |
        ((drflac_uint64)si[14] << 24) |
        ((drflac_uint64)si[15] << 16) |
        ((drflac_uint64)si[16] << 8) |
        si[17];

    return DRFLAC_TRUE;
}

/* Skip metadata blocks to find first audio frame */
static drflac_bool32 drflac__skip_metadata(drflac* pFlac) {
    drflac_uint8 blockHeader[4];
    drflac_bool32 isLastBlock = DRFLAC_FALSE;

    /* Skip remaining metadata blocks after STREAMINFO */
    while (!isLastBlock) {
        if (pFlac->onRead(pFlac->pUserData, blockHeader, 4) != 4) {
            return DRFLAC_FALSE;
        }

        isLastBlock = (blockHeader[0] & 0x80) != 0;
        drflac_uint32 blockSize = ((blockHeader[1] << 16) | (blockHeader[2] << 8) | blockHeader[3]);

        /* Skip block content */
        drflac_uint8 dummy[256];
        while (blockSize > 0) {
            drflac_uint32 toRead = (blockSize > 256) ? 256 : blockSize;
            if (pFlac->onRead(pFlac->pUserData, dummy, toRead) != toRead) {
                return DRFLAC_FALSE;
            }
            blockSize -= toRead;
        }
    }

    return DRFLAC_TRUE;
}

drflac* drflac_open(drflac_read_proc onRead, drflac_seek_proc onSeek, void* pUserData, void* pAllocationCallbacks) {
    (void)pAllocationCallbacks;

    if (!onRead) return NULL;

    drflac* pFlac = (drflac*)DRFLAC_MALLOC(sizeof(drflac));
    if (!pFlac) return NULL;

    DRFLAC_ZERO_MEMORY(pFlac, sizeof(drflac));
    pFlac->onRead = onRead;
    pFlac->onSeek = onSeek;
    pFlac->pUserData = pUserData;

    /* Parse header */
    if (!drflac__read_streaminfo(pFlac)) {
        DRFLAC_FREE(pFlac);
        return NULL;
    }

    /* Skip metadata to find audio data */
    if (!drflac__skip_metadata(pFlac)) {
        DRFLAC_FREE(pFlac);
        return NULL;
    }

    pFlac->currentPCMFrame = 0;

    return pFlac;
}

void drflac_close(drflac* pFlac) {
    if (pFlac) {
        if (pFlac->pDecodedSamples) {
            DRFLAC_FREE(pFlac->pDecodedSamples);
        }
        DRFLAC_FREE(pFlac);
    }
}

/*
 * NOTE: Full FLAC decoding requires implementing:
 * - Frame sync detection (0xFF 0xF8/0xF9)
 * - Frame header parsing
 * - Subframe decoding (constant, verbatim, fixed, LPC)
 * - Rice coding for residuals
 * - CRC validation
 *
 * This is complex (~3000 lines in full dr_flac).
 * For production, use the complete dr_flac.h from dr_libs.
 */

drflac_uint64 drflac_read_pcm_frames_s16(drflac* pFlac, drflac_uint64 framesToRead, drflac_int16* pBufferOut) {
    if (!pFlac || !pBufferOut || framesToRead == 0) return 0;

    /* Stub: Read raw bytes and convert (won't work for real FLAC) */
    /* This needs full frame decoding implementation */

    drflac_uint64 framesRead = 0;

    /* Fill with silence as placeholder */
    for (drflac_uint64 i = 0; i < framesToRead * pFlac->channels; i++) {
        pBufferOut[i] = 0;
    }

    pFlac->currentPCMFrame += framesToRead;
    if (pFlac->currentPCMFrame > pFlac->totalPCMFrameCount) {
        framesRead = framesToRead - (pFlac->currentPCMFrame - pFlac->totalPCMFrameCount);
        pFlac->currentPCMFrame = pFlac->totalPCMFrameCount;
    } else {
        framesRead = framesToRead;
    }

    return framesRead;
}

drflac_uint64 drflac_read_pcm_frames_s32(drflac* pFlac, drflac_uint64 framesToRead, drflac_int32* pBufferOut) {
    if (!pFlac || !pBufferOut || framesToRead == 0) return 0;

    for (drflac_uint64 i = 0; i < framesToRead * pFlac->channels; i++) {
        pBufferOut[i] = 0;
    }

    pFlac->currentPCMFrame += framesToRead;
    return framesToRead;
}

drflac_bool32 drflac_seek_to_pcm_frame(drflac* pFlac, drflac_uint64 pcmFrameIndex) {
    if (!pFlac) return DRFLAC_FALSE;

    /* Stub: Just update position counter */
    /* Real implementation needs seek table or brute-force search */
    pFlac->currentPCMFrame = pcmFrameIndex;

    return DRFLAC_TRUE;
}

#endif /* DR_FLAC_IMPLEMENTATION */
