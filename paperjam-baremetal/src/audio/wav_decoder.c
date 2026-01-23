/*
 * PaperJam Bare-Metal OS - WAV Decoder
 *
 * Simple WAV/RIFF parser for uncompressed PCM audio
 */

#include "hal/bcm2837.h"
#include "decoder.h"
#include "sys/heap.h"
#include "fatfs/ff.h"

/* WAV file constants */
#define RIFF_ID     0x46464952  /* "RIFF" */
#define WAVE_ID     0x45564157  /* "WAVE" */
#define FMT_ID      0x20746D66  /* "fmt " */
#define DATA_ID     0x61746164  /* "data" */

/* WAV format codes */
#define WAVE_FORMAT_PCM         1
#define WAVE_FORMAT_IEEE_FLOAT  3

/* WAV decoder state */
typedef struct {
    FIL* file;
    u32 sample_rate;
    u16 channels;
    u16 bits_per_sample;
    u32 data_start;
    u32 data_size;
    u32 total_samples;
    u32 current_sample;
    u8 read_buffer[512];
} wav_state_t;

/*
 * Read 32-bit little-endian value
 */
static u32 read_u32_le(const u8* p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | (p[3] << 24);
}

/*
 * Read 16-bit little-endian value
 */
static u16 read_u16_le(const u8* p) {
    return p[0] | (p[1] << 8);
}

/*
 * Open WAV file
 */
static int wav_open(decoder_context_t* ctx, FIL* file) {
    wav_state_t* wav = (wav_state_t*)heap_alloc(sizeof(wav_state_t));
    if (!wav) return -1;

    memset(wav, 0, sizeof(wav_state_t));
    wav->file = file;
    ctx->decoder_data = wav;

    /* Read RIFF header */
    UINT br;
    u8 header[44];
    if (f_read(file, header, 44, &br) != FR_OK || br < 44) {
        heap_free(wav);
        return -2;
    }

    /* Verify RIFF header */
    if (read_u32_le(&header[0]) != RIFF_ID ||
        read_u32_le(&header[8]) != WAVE_ID) {
        heap_free(wav);
        return -3;
    }

    /* Parse fmt chunk */
    if (read_u32_le(&header[12]) != FMT_ID) {
        heap_free(wav);
        return -4;
    }

    u32 fmt_size = read_u32_le(&header[16]);
    u16 format = read_u16_le(&header[20]);

    if (format != WAVE_FORMAT_PCM) {
        heap_free(wav);
        return -5;  /* Only PCM supported */
    }

    wav->channels = read_u16_le(&header[22]);
    wav->sample_rate = read_u32_le(&header[24]);
    wav->bits_per_sample = read_u16_le(&header[34]);

    /* Find data chunk */
    u32 offset = 20 + fmt_size;
    f_lseek(file, offset);

    while (1) {
        u8 chunk_header[8];
        if (f_read(file, chunk_header, 8, &br) != FR_OK || br < 8) {
            heap_free(wav);
            return -6;
        }

        u32 chunk_id = read_u32_le(&chunk_header[0]);
        u32 chunk_size = read_u32_le(&chunk_header[4]);

        if (chunk_id == DATA_ID) {
            wav->data_start = f_tell(file);
            wav->data_size = chunk_size;
            break;
        }

        /* Skip unknown chunk */
        f_lseek(file, f_tell(file) + chunk_size);
        if (f_tell(file) >= f_size(file)) {
            heap_free(wav);
            return -7;
        }
    }

    /* Calculate total samples */
    u32 bytes_per_sample = wav->channels * wav->bits_per_sample / 8;
    wav->total_samples = wav->data_size / bytes_per_sample;

    /* Set decoder context */
    ctx->sample_rate = wav->sample_rate;
    ctx->channels = wav->channels;
    ctx->total_samples = wav->total_samples;
    ctx->current_sample = 0;
    ctx->state = DECODER_STATE_READY;

    return 0;
}

/*
 * Close WAV decoder
 */
static void wav_close(decoder_context_t* ctx) {
    if (ctx->decoder_data) {
        heap_free(ctx->decoder_data);
        ctx->decoder_data = NULL;
    }
    ctx->state = DECODER_STATE_IDLE;
}

/*
 * Decode WAV samples
 */
static int wav_decode(decoder_context_t* ctx, i16* buffer, u32 max_samples) {
    wav_state_t* wav = (wav_state_t*)ctx->decoder_data;
    if (!wav) return -1;

    /* Check EOF */
    if (wav->current_sample >= wav->total_samples) {
        return 0;
    }

    /* Calculate bytes to read */
    u32 bytes_per_sample = wav->channels * wav->bits_per_sample / 8;
    u32 samples_remaining = wav->total_samples - wav->current_sample;
    u32 samples_to_read = max_samples;
    if (samples_to_read > samples_remaining) {
        samples_to_read = samples_remaining;
    }

    /* Limit by buffer size */
    u32 max_read_samples = sizeof(wav->read_buffer) / bytes_per_sample;
    if (samples_to_read > max_read_samples) {
        samples_to_read = max_read_samples;
    }

    /* Read raw data */
    UINT br;
    u32 bytes_to_read = samples_to_read * bytes_per_sample;
    if (f_read(wav->file, wav->read_buffer, bytes_to_read, &br) != FR_OK) {
        return -2;
    }

    u32 samples_read = br / bytes_per_sample;

    /* Convert to 16-bit signed */
    if (wav->bits_per_sample == 16) {
        /* 16-bit PCM - already in correct format */
        i16* src = (i16*)wav->read_buffer;
        for (u32 i = 0; i < samples_read * wav->channels; i++) {
            buffer[i] = src[i];
        }
    } else if (wav->bits_per_sample == 8) {
        /* 8-bit unsigned PCM */
        u8* src = wav->read_buffer;
        for (u32 i = 0; i < samples_read * wav->channels; i++) {
            buffer[i] = ((i16)src[i] - 128) << 8;
        }
    } else if (wav->bits_per_sample == 24) {
        /* 24-bit PCM */
        u8* src = wav->read_buffer;
        for (u32 i = 0; i < samples_read * wav->channels; i++) {
            i32 sample = (src[i*3] | (src[i*3+1] << 8) | (src[i*3+2] << 16));
            if (sample & 0x800000) sample |= 0xFF000000;  /* Sign extend */
            buffer[i] = sample >> 8;
        }
    } else {
        return -3;  /* Unsupported bit depth */
    }

    wav->current_sample += samples_read;
    ctx->current_sample = wav->current_sample;

    return samples_read * wav->channels;
}

/*
 * Seek to position
 */
static int wav_seek(decoder_context_t* ctx, u32 sample_pos) {
    wav_state_t* wav = (wav_state_t*)ctx->decoder_data;
    if (!wav) return -1;

    if (sample_pos >= wav->total_samples) {
        sample_pos = wav->total_samples - 1;
    }

    u32 bytes_per_sample = wav->channels * wav->bits_per_sample / 8;
    u32 offset = wav->data_start + sample_pos * bytes_per_sample;

    if (f_lseek(wav->file, offset) != FR_OK) {
        return -2;
    }

    wav->current_sample = sample_pos;
    ctx->current_sample = sample_pos;
    return 0;
}

/*
 * Get metadata
 */
static int wav_get_metadata(decoder_context_t* ctx, audio_metadata_t* meta) {
    wav_state_t* wav = (wav_state_t*)ctx->decoder_data;
    if (!wav) return -1;

    memset(meta, 0, sizeof(audio_metadata_t));
    meta->sample_rate = wav->sample_rate;
    meta->channels = wav->channels;
    meta->bits_per_sample = wav->bits_per_sample;
    meta->duration_ms = (u64)wav->total_samples * 1000 / wav->sample_rate;
    meta->bitrate = wav->sample_rate * wav->channels * wav->bits_per_sample;

    return 0;
}

/*
 * Get position
 */
static u32 wav_get_position(decoder_context_t* ctx) {
    wav_state_t* wav = (wav_state_t*)ctx->decoder_data;
    return wav ? wav->current_sample : 0;
}

/*
 * Get total samples
 */
static u32 wav_get_total_samples(decoder_context_t* ctx) {
    wav_state_t* wav = (wav_state_t*)ctx->decoder_data;
    return wav ? wav->total_samples : 0;
}

/* WAV decoder operations */
const decoder_ops_t wav_decoder_ops = {
    .open = wav_open,
    .close = wav_close,
    .decode = wav_decode,
    .seek = wav_seek,
    .get_metadata = wav_get_metadata,
    .get_position = wav_get_position,
    .get_total_samples = wav_get_total_samples
};
