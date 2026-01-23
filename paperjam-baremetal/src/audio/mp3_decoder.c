/*
 * PaperJam Bare-Metal OS - MP3 Decoder
 *
 * Uses libmad for MP3 decoding
 * http://www.underbit.com/products/mad/
 *
 * Note: This is a stub implementation. Actual implementation requires
 * the libmad library to be properly integrated.
 */

#include "hal/bcm2837.h"
#include "decoder.h"
#include "sys/heap.h"
#include "fatfs/ff.h"

/* MP3 frame constants */
#define MP3_BUFFER_SIZE     8192
#define MP3_SAMPLES_PER_FRAME 1152

/* ID3v2 tag detection */
#define ID3V2_HEADER_SIZE   10

/* MP3 decoder state */
typedef struct {
    FIL* file;
    u8 input_buffer[MP3_BUFFER_SIZE];
    u32 buffer_size;
    u32 buffer_pos;
    u32 sample_rate;
    u32 channels;
    u32 bitrate;
    u32 total_samples;
    u32 current_sample;
    u32 data_start;         /* Start of MP3 data (after ID3 tag) */
    u32 file_size;
} mp3_state_t;

/*
 * Parse ID3v2 tag header to find start of MP3 data
 */
static u32 mp3_skip_id3v2(FIL* file) {
    u8 header[ID3V2_HEADER_SIZE];
    UINT br;

    if (f_read(file, header, ID3V2_HEADER_SIZE, &br) != FR_OK || br < ID3V2_HEADER_SIZE) {
        f_lseek(file, 0);
        return 0;
    }

    /* Check ID3v2 signature */
    if (header[0] == 'I' && header[1] == 'D' && header[2] == '3') {
        /* Parse syncsafe integer (tag size) */
        u32 size = ((header[6] & 0x7F) << 21) |
                   ((header[7] & 0x7F) << 14) |
                   ((header[8] & 0x7F) << 7) |
                   (header[9] & 0x7F);
        return ID3V2_HEADER_SIZE + size;
    }

    f_lseek(file, 0);
    return 0;
}

/*
 * Find first valid MP3 frame and extract info
 */
static int mp3_find_first_frame(mp3_state_t* mp3) {
    u8 header[4];
    UINT br;

    f_lseek(mp3->file, mp3->data_start);

    /* Search for sync word */
    while (f_tell(mp3->file) < mp3->file_size - 4) {
        if (f_read(mp3->file, header, 4, &br) != FR_OK || br < 4) {
            return -1;
        }

        /* Check frame sync (11 bits set) */
        if (header[0] == 0xFF && (header[1] & 0xE0) == 0xE0) {
            /* Parse header */
            int version = (header[1] >> 3) & 0x03;
            int layer = (header[1] >> 1) & 0x03;
            int bitrate_idx = (header[2] >> 4) & 0x0F;
            int sample_rate_idx = (header[2] >> 2) & 0x03;
            int channel_mode = (header[3] >> 6) & 0x03;

            /* Bitrate table for MPEG1 Layer III */
            static const u16 bitrates[] = {
                0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0
            };

            /* Sample rate table for MPEG1 */
            static const u16 sample_rates[] = { 44100, 48000, 32000, 0 };

            if (layer == 1 && version == 3) {  /* MPEG1 Layer III */
                mp3->bitrate = bitrates[bitrate_idx] * 1000;
                mp3->sample_rate = sample_rates[sample_rate_idx];
                mp3->channels = (channel_mode == 3) ? 1 : 2;

                /* Estimate total samples from file size and bitrate */
                if (mp3->bitrate > 0) {
                    u32 data_size = mp3->file_size - mp3->data_start;
                    u32 duration_ms = (u64)data_size * 8 * 1000 / mp3->bitrate;
                    mp3->total_samples = (u64)duration_ms * mp3->sample_rate / 1000;
                }

                f_lseek(mp3->file, mp3->data_start);
                return 0;
            }
        }

        /* Back up and try next byte */
        f_lseek(mp3->file, f_tell(mp3->file) - 3);
    }

    return -1;
}

/*
 * Open MP3 file
 */
static int mp3_open(decoder_context_t* ctx, FIL* file) {
    mp3_state_t* mp3 = (mp3_state_t*)heap_alloc(sizeof(mp3_state_t));
    if (!mp3) return -1;

    memset(mp3, 0, sizeof(mp3_state_t));
    mp3->file = file;
    mp3->file_size = f_size(file);
    ctx->decoder_data = mp3;

    /* Skip ID3v2 tag */
    mp3->data_start = mp3_skip_id3v2(file);

    /* Find first frame and get format info */
    if (mp3_find_first_frame(mp3) < 0) {
        heap_free(mp3);
        return -2;
    }

    ctx->sample_rate = mp3->sample_rate;
    ctx->channels = mp3->channels;
    ctx->total_samples = mp3->total_samples;
    ctx->current_sample = 0;
    ctx->state = DECODER_STATE_READY;

    return 0;
}

/*
 * Close MP3 decoder
 */
static void mp3_close(decoder_context_t* ctx) {
    if (ctx->decoder_data) {
        heap_free(ctx->decoder_data);
        ctx->decoder_data = NULL;
    }
    ctx->state = DECODER_STATE_IDLE;
}

/*
 * Decode MP3 samples
 * Note: Stub implementation - requires libmad for actual decoding
 */
static int mp3_decode(decoder_context_t* ctx, i16* buffer, u32 max_samples) {
    mp3_state_t* mp3 = (mp3_state_t*)ctx->decoder_data;
    if (!mp3) return -1;

    /* Check EOF */
    if (mp3->current_sample >= mp3->total_samples) {
        return 0;
    }

    /*
     * Actual implementation would:
     * 1. Read data into input buffer
     * 2. Call mad_stream_buffer() to set input
     * 3. Call mad_frame_decode() to decode frame
     * 4. Call mad_synth_frame() to synthesize PCM
     * 5. Convert MAD fixed-point to 16-bit PCM
     */

    /* Stub: Return silence */
    u32 samples = max_samples;
    if (mp3->current_sample + samples / mp3->channels > mp3->total_samples) {
        samples = (mp3->total_samples - mp3->current_sample) * mp3->channels;
    }

    for (u32 i = 0; i < samples; i++) {
        buffer[i] = 0;
    }

    mp3->current_sample += samples / mp3->channels;
    ctx->current_sample = mp3->current_sample;

    return samples;
}

/*
 * Seek to position
 */
static int mp3_seek(decoder_context_t* ctx, u32 sample_pos) {
    mp3_state_t* mp3 = (mp3_state_t*)ctx->decoder_data;
    if (!mp3) return -1;

    /* Calculate byte position (approximate for VBR) */
    if (mp3->bitrate > 0 && mp3->sample_rate > 0) {
        u32 time_ms = (u64)sample_pos * 1000 / mp3->sample_rate;
        u32 byte_pos = (u64)time_ms * mp3->bitrate / 8 / 1000;
        f_lseek(mp3->file, mp3->data_start + byte_pos);
    }

    mp3->current_sample = sample_pos;
    ctx->current_sample = sample_pos;
    return 0;
}

/*
 * Get metadata
 */
static int mp3_get_metadata(decoder_context_t* ctx, audio_metadata_t* meta) {
    mp3_state_t* mp3 = (mp3_state_t*)ctx->decoder_data;
    if (!mp3) return -1;

    memset(meta, 0, sizeof(audio_metadata_t));
    meta->sample_rate = mp3->sample_rate;
    meta->channels = mp3->channels;
    meta->bitrate = mp3->bitrate;
    if (mp3->sample_rate > 0) {
        meta->duration_ms = (u64)mp3->total_samples * 1000 / mp3->sample_rate;
    }

    /* TODO: Parse ID3 tags for title, artist, etc. */

    return 0;
}

static u32 mp3_get_position(decoder_context_t* ctx) {
    mp3_state_t* mp3 = (mp3_state_t*)ctx->decoder_data;
    return mp3 ? mp3->current_sample : 0;
}

static u32 mp3_get_total_samples(decoder_context_t* ctx) {
    mp3_state_t* mp3 = (mp3_state_t*)ctx->decoder_data;
    return mp3 ? mp3->total_samples : 0;
}

/* MP3 decoder operations */
const decoder_ops_t mp3_decoder_ops = {
    .open = mp3_open,
    .close = mp3_close,
    .decode = mp3_decode,
    .seek = mp3_seek,
    .get_metadata = mp3_get_metadata,
    .get_position = mp3_get_position,
    .get_total_samples = mp3_get_total_samples
};

/*
 * Decoder helper functions
 */
extern const decoder_ops_t wav_decoder_ops;
extern const decoder_ops_t flac_decoder_ops;

audio_format_t decoder_detect_format(const char* filename) {
    /* Find extension */
    const char* ext = filename;
    const char* p = filename;
    while (*p) {
        if (*p == '.') ext = p + 1;
        p++;
    }

    if (strcmp(ext, "mp3") == 0 || strcmp(ext, "MP3") == 0) {
        return AUDIO_FORMAT_MP3;
    }
    if (strcmp(ext, "flac") == 0 || strcmp(ext, "FLAC") == 0) {
        return AUDIO_FORMAT_FLAC;
    }
    if (strcmp(ext, "wav") == 0 || strcmp(ext, "WAV") == 0) {
        return AUDIO_FORMAT_WAV;
    }

    return AUDIO_FORMAT_UNKNOWN;
}

const char* decoder_format_name(audio_format_t format) {
    switch (format) {
        case AUDIO_FORMAT_MP3:  return "MP3";
        case AUDIO_FORMAT_FLAC: return "FLAC";
        case AUDIO_FORMAT_WAV:  return "WAV";
        default:                return "Unknown";
    }
}

int decoder_init(decoder_context_t* ctx, const char* filename) {
    memset(ctx, 0, sizeof(decoder_context_t));

    ctx->format = decoder_detect_format(filename);

    switch (ctx->format) {
        case AUDIO_FORMAT_MP3:
            ctx->ops = &mp3_decoder_ops;
            break;
        case AUDIO_FORMAT_FLAC:
            ctx->ops = &flac_decoder_ops;
            break;
        case AUDIO_FORMAT_WAV:
            ctx->ops = &wav_decoder_ops;
            break;
        default:
            return -1;
    }

    return 0;
}

void decoder_cleanup(decoder_context_t* ctx) {
    memset(ctx, 0, sizeof(decoder_context_t));
}
