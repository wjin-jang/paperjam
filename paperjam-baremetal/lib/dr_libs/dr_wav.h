/*
 * dr_wav.h - Single-header WAV decoder
 *
 * This is a minimal implementation for PaperJam bare-metal OS.
 * For the full library, see: https://github.com/mackron/dr_libs
 *
 * Usage:
 *   #define DR_WAV_IMPLEMENTATION
 *   #include "dr_wav.h"
 */

#ifndef DR_WAV_H
#define DR_WAV_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int32_t drwav_int32;
typedef uint32_t drwav_uint32;
typedef int64_t drwav_int64;
typedef uint64_t drwav_uint64;
typedef uint8_t drwav_uint8;
typedef int16_t drwav_int16;
typedef drwav_uint8 drwav_bool8;
typedef drwav_uint32 drwav_bool32;

#define DRWAV_TRUE     1
#define DRWAV_FALSE    0

/* Format codes */
#define DR_WAVE_FORMAT_PCM          0x0001
#define DR_WAVE_FORMAT_IEEE_FLOAT   0x0003
#define DR_WAVE_FORMAT_ALAW         0x0006
#define DR_WAVE_FORMAT_MULAW        0x0007
#define DR_WAVE_FORMAT_EXTENSIBLE   0xFFFE

/* Read callback */
typedef size_t (*drwav_read_proc)(void* pUserData, void* pBufferOut, size_t bytesToRead);

/* Seek callback */
typedef drwav_bool32 (*drwav_seek_proc)(void* pUserData, int offset, int origin);

#define drwav_seek_origin_start    0
#define drwav_seek_origin_current  1

/* WAV format */
typedef struct {
    drwav_uint16 formatTag;
    drwav_uint16 channels;
    drwav_uint32 sampleRate;
    drwav_uint32 avgBytesPerSec;
    drwav_uint16 blockAlign;
    drwav_uint16 bitsPerSample;
    drwav_uint16 extendedSize;
    drwav_uint16 validBitsPerSample;
    drwav_uint32 channelMask;
    drwav_uint8 subFormat[16];
} drwav_fmt;

/* Main WAV structure */
typedef struct {
    drwav_read_proc onRead;
    drwav_seek_proc onSeek;
    void* pUserData;

    drwav_fmt fmt;
    drwav_uint32 sampleRate;
    drwav_uint16 channels;
    drwav_uint16 bitsPerSample;
    drwav_uint16 translatedFormatTag;
    drwav_uint64 totalPCMFrameCount;
    drwav_uint64 dataChunkDataSize;
    drwav_uint64 dataChunkDataPos;
    drwav_uint64 bytesRemaining;
    drwav_uint64 readCursorInPCMFrames;
} drwav;

/* API Functions */
drwav_bool32 drwav_init(drwav* pWav, drwav_read_proc onRead, drwav_seek_proc onSeek, void* pUserData, void* pAllocationCallbacks);
void drwav_uninit(drwav* pWav);
drwav_uint64 drwav_read_pcm_frames_s16(drwav* pWav, drwav_uint64 framesToRead, drwav_int16* pBufferOut);
drwav_uint64 drwav_read_pcm_frames_s32(drwav* pWav, drwav_uint64 framesToRead, drwav_int32* pBufferOut);
drwav_bool32 drwav_seek_to_pcm_frame(drwav* pWav, drwav_uint64 targetFrameIndex);

#ifdef __cplusplus
}
#endif

#endif /* DR_WAV_H */

/*
 * Implementation
 */
#ifdef DR_WAV_IMPLEMENTATION

#ifndef DRWAV_MALLOC
extern void* heap_alloc(uint32_t size);
extern void heap_free(void* ptr);
#define DRWAV_MALLOC(sz) heap_alloc(sz)
#define DRWAV_FREE(p) heap_free(p)
#endif

#ifndef DRWAV_COPY_MEMORY
extern void* memcpy(void* dst, const void* src, uint32_t n);
#define DRWAV_COPY_MEMORY(dst, src, sz) memcpy(dst, src, sz)
#endif

#ifndef DRWAV_ZERO_MEMORY
extern void* memset(void* dst, int c, uint32_t n);
#define DRWAV_ZERO_MEMORY(p, sz) memset(p, 0, sz)
#endif

/* Chunk IDs */
#define DRWAV_RIFF_ID   0x46464952  /* "RIFF" */
#define DRWAV_WAVE_ID   0x45564157  /* "WAVE" */
#define DRWAV_FMT_ID    0x20746D66  /* "fmt " */
#define DRWAV_DATA_ID   0x61746164  /* "data" */

/* Read little-endian values */
static drwav_uint32 drwav__read_u32_le(const drwav_uint8* p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | (p[3] << 24);
}

static drwav_uint16 drwav__read_u16_le(const drwav_uint8* p) {
    return p[0] | (p[1] << 8);
}

drwav_bool32 drwav_init(drwav* pWav, drwav_read_proc onRead, drwav_seek_proc onSeek, void* pUserData, void* pAllocationCallbacks) {
    (void)pAllocationCallbacks;

    if (!pWav || !onRead) return DRWAV_FALSE;

    DRWAV_ZERO_MEMORY(pWav, sizeof(drwav));
    pWav->onRead = onRead;
    pWav->onSeek = onSeek;
    pWav->pUserData = pUserData;

    /* Read RIFF header */
    drwav_uint8 header[12];
    if (onRead(pUserData, header, 12) != 12) {
        return DRWAV_FALSE;
    }

    /* Verify RIFF/WAVE */
    if (drwav__read_u32_le(&header[0]) != DRWAV_RIFF_ID ||
        drwav__read_u32_le(&header[8]) != DRWAV_WAVE_ID) {
        return DRWAV_FALSE;
    }

    /* Find fmt and data chunks */
    drwav_bool32 foundFmt = DRWAV_FALSE;
    drwav_bool32 foundData = DRWAV_FALSE;

    while (!foundData) {
        drwav_uint8 chunkHeader[8];
        if (onRead(pUserData, chunkHeader, 8) != 8) {
            break;
        }

        drwav_uint32 chunkId = drwav__read_u32_le(&chunkHeader[0]);
        drwav_uint32 chunkSize = drwav__read_u32_le(&chunkHeader[4]);

        if (chunkId == DRWAV_FMT_ID) {
            /* Read format chunk */
            drwav_uint8 fmtData[40];
            drwav_uint32 fmtSize = (chunkSize > 40) ? 40 : chunkSize;

            if (onRead(pUserData, fmtData, fmtSize) != fmtSize) {
                return DRWAV_FALSE;
            }

            pWav->fmt.formatTag = drwav__read_u16_le(&fmtData[0]);
            pWav->fmt.channels = drwav__read_u16_le(&fmtData[2]);
            pWav->fmt.sampleRate = drwav__read_u32_le(&fmtData[4]);
            pWav->fmt.avgBytesPerSec = drwav__read_u32_le(&fmtData[8]);
            pWav->fmt.blockAlign = drwav__read_u16_le(&fmtData[12]);
            pWav->fmt.bitsPerSample = drwav__read_u16_le(&fmtData[14]);

            pWav->sampleRate = pWav->fmt.sampleRate;
            pWav->channels = pWav->fmt.channels;
            pWav->bitsPerSample = pWav->fmt.bitsPerSample;
            pWav->translatedFormatTag = pWav->fmt.formatTag;

            /* Skip remaining format data */
            if (chunkSize > fmtSize) {
                drwav_uint8 skip[256];
                drwav_uint32 remaining = chunkSize - fmtSize;
                while (remaining > 0) {
                    drwav_uint32 toSkip = (remaining > 256) ? 256 : remaining;
                    onRead(pUserData, skip, toSkip);
                    remaining -= toSkip;
                }
            }

            foundFmt = DRWAV_TRUE;

        } else if (chunkId == DRWAV_DATA_ID) {
            /* Found data chunk */
            pWav->dataChunkDataSize = chunkSize;
            pWav->bytesRemaining = chunkSize;
            foundData = DRWAV_TRUE;

        } else {
            /* Skip unknown chunk */
            drwav_uint8 skip[256];
            drwav_uint32 remaining = chunkSize;
            while (remaining > 0) {
                drwav_uint32 toSkip = (remaining > 256) ? 256 : remaining;
                if (onRead(pUserData, skip, toSkip) != toSkip) break;
                remaining -= toSkip;
            }
        }
    }

    if (!foundFmt || !foundData) {
        return DRWAV_FALSE;
    }

    /* Calculate total frames */
    drwav_uint32 bytesPerFrame = pWav->channels * pWav->bitsPerSample / 8;
    if (bytesPerFrame > 0) {
        pWav->totalPCMFrameCount = pWav->dataChunkDataSize / bytesPerFrame;
    }

    pWav->readCursorInPCMFrames = 0;

    return DRWAV_TRUE;
}

void drwav_uninit(drwav* pWav) {
    if (pWav) {
        DRWAV_ZERO_MEMORY(pWav, sizeof(drwav));
    }
}

drwav_uint64 drwav_read_pcm_frames_s16(drwav* pWav, drwav_uint64 framesToRead, drwav_int16* pBufferOut) {
    if (!pWav || !pBufferOut || framesToRead == 0) return 0;

    drwav_uint64 framesRead = 0;
    drwav_uint32 bytesPerFrame = pWav->channels * pWav->bitsPerSample / 8;

    if (bytesPerFrame == 0) return 0;

    /* Limit to remaining frames */
    drwav_uint64 framesRemaining = pWav->totalPCMFrameCount - pWav->readCursorInPCMFrames;
    if (framesToRead > framesRemaining) {
        framesToRead = framesRemaining;
    }

    if (pWav->bitsPerSample == 16 && pWav->translatedFormatTag == DR_WAVE_FORMAT_PCM) {
        /* Direct read for 16-bit PCM */
        size_t bytesToRead = (size_t)(framesToRead * bytesPerFrame);
        size_t bytesRead = pWav->onRead(pWav->pUserData, pBufferOut, bytesToRead);
        framesRead = bytesRead / bytesPerFrame;

    } else if (pWav->bitsPerSample == 8 && pWav->translatedFormatTag == DR_WAVE_FORMAT_PCM) {
        /* 8-bit unsigned PCM -> 16-bit signed */
        drwav_uint8 temp[256];
        drwav_uint64 remaining = framesToRead;
        drwav_int16* pOut = pBufferOut;

        while (remaining > 0) {
            drwav_uint64 toRead = remaining;
            if (toRead > 256 / pWav->channels) toRead = 256 / pWav->channels;

            size_t bytesRead = pWav->onRead(pWav->pUserData, temp, (size_t)(toRead * pWav->channels));
            drwav_uint64 samplesRead = bytesRead;

            for (drwav_uint64 i = 0; i < samplesRead; i++) {
                *pOut++ = ((drwav_int16)temp[i] - 128) << 8;
            }

            framesRead += bytesRead / pWav->channels;
            remaining -= bytesRead / pWav->channels;
            if (bytesRead == 0) break;
        }

    } else if (pWav->bitsPerSample == 24 && pWav->translatedFormatTag == DR_WAVE_FORMAT_PCM) {
        /* 24-bit PCM -> 16-bit signed */
        drwav_uint8 temp[768];  /* 256 samples * 3 bytes */
        drwav_uint64 remaining = framesToRead;
        drwav_int16* pOut = pBufferOut;

        while (remaining > 0) {
            drwav_uint64 toRead = remaining;
            if (toRead > 256 / pWav->channels) toRead = 256 / pWav->channels;

            size_t bytesPerSample = 3 * pWav->channels;
            size_t bytesToRead = (size_t)(toRead * bytesPerSample);
            size_t bytesRead = pWav->onRead(pWav->pUserData, temp, bytesToRead);

            drwav_uint64 samplesRead = bytesRead / 3;
            for (drwav_uint64 i = 0; i < samplesRead; i++) {
                drwav_int32 sample = temp[i*3] | (temp[i*3+1] << 8) | (temp[i*3+2] << 16);
                if (sample & 0x800000) sample |= 0xFF000000;
                *pOut++ = (drwav_int16)(sample >> 8);
            }

            framesRead += bytesRead / bytesPerFrame;
            remaining -= bytesRead / bytesPerFrame;
            if (bytesRead == 0) break;
        }

    } else if (pWav->bitsPerSample == 32 && pWav->translatedFormatTag == DR_WAVE_FORMAT_IEEE_FLOAT) {
        /* 32-bit float -> 16-bit signed */
        float temp[256];
        drwav_uint64 remaining = framesToRead;
        drwav_int16* pOut = pBufferOut;

        while (remaining > 0) {
            drwav_uint64 toRead = remaining;
            if (toRead > 256 / pWav->channels) toRead = 256 / pWav->channels;

            size_t bytesToRead = (size_t)(toRead * pWav->channels * 4);
            size_t bytesRead = pWav->onRead(pWav->pUserData, temp, bytesToRead);

            drwav_uint64 samplesRead = bytesRead / 4;
            for (drwav_uint64 i = 0; i < samplesRead; i++) {
                float f = temp[i];
                if (f > 1.0f) f = 1.0f;
                if (f < -1.0f) f = -1.0f;
                *pOut++ = (drwav_int16)(f * 32767.0f);
            }

            framesRead += bytesRead / bytesPerFrame;
            remaining -= bytesRead / bytesPerFrame;
            if (bytesRead == 0) break;
        }

    } else {
        /* Unsupported format - fill with silence */
        for (drwav_uint64 i = 0; i < framesToRead * pWav->channels; i++) {
            pBufferOut[i] = 0;
        }
        framesRead = framesToRead;
    }

    pWav->readCursorInPCMFrames += framesRead;
    pWav->bytesRemaining -= framesRead * bytesPerFrame;

    return framesRead;
}

drwav_uint64 drwav_read_pcm_frames_s32(drwav* pWav, drwav_uint64 framesToRead, drwav_int32* pBufferOut) {
    /* Read as s16 and expand */
    drwav_int16* temp = (drwav_int16*)DRWAV_MALLOC((size_t)(framesToRead * pWav->channels * sizeof(drwav_int16)));
    if (!temp) return 0;

    drwav_uint64 framesRead = drwav_read_pcm_frames_s16(pWav, framesToRead, temp);

    for (drwav_uint64 i = 0; i < framesRead * pWav->channels; i++) {
        pBufferOut[i] = temp[i] << 16;
    }

    DRWAV_FREE(temp);
    return framesRead;
}

drwav_bool32 drwav_seek_to_pcm_frame(drwav* pWav, drwav_uint64 targetFrameIndex) {
    if (!pWav || !pWav->onSeek) return DRWAV_FALSE;

    if (targetFrameIndex > pWav->totalPCMFrameCount) {
        targetFrameIndex = pWav->totalPCMFrameCount;
    }

    drwav_uint32 bytesPerFrame = pWav->channels * pWav->bitsPerSample / 8;
    drwav_uint64 byteOffset = targetFrameIndex * bytesPerFrame;

    /* Seek from data chunk start */
    if (pWav->onSeek(pWav->pUserData, (int)(pWav->dataChunkDataPos + byteOffset), drwav_seek_origin_start)) {
        pWav->readCursorInPCMFrames = targetFrameIndex;
        pWav->bytesRemaining = pWav->dataChunkDataSize - byteOffset;
        return DRWAV_TRUE;
    }

    return DRWAV_FALSE;
}

#endif /* DR_WAV_IMPLEMENTATION */
