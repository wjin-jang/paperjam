/*
 * PaperJam Bare-Metal OS - Unified Decoder Interface
 */

#ifndef DECODER_H
#define DECODER_H

#include "hal/bcm2837.h"
#include "fatfs/ff.h"

/* Audio format types */
typedef enum {
    AUDIO_FORMAT_UNKNOWN = 0,
    AUDIO_FORMAT_MP3,
    AUDIO_FORMAT_FLAC,
    AUDIO_FORMAT_WAV
} audio_format_t;

/* Decoder state */
typedef enum {
    DECODER_STATE_IDLE = 0,
    DECODER_STATE_READY,
    DECODER_STATE_PLAYING,
    DECODER_STATE_PAUSED,
    DECODER_STATE_FINISHED,
    DECODER_STATE_ERROR
} decoder_state_t;

/* Audio metadata */
typedef struct {
    char title[128];
    char artist[128];
    char album[128];
    char genre[32];
    u32  year;
    u32  track;
    u32  duration_ms;
    u32  sample_rate;
    u32  channels;
    u32  bits_per_sample;
    u32  bitrate;
    bool has_cover_art;
    u32  cover_art_offset;
    u32  cover_art_size;
} audio_metadata_t;

/* Decoder context (opaque) */
typedef struct decoder_context decoder_context_t;

/* Decoder interface */
typedef struct {
    /* Open file and prepare for decoding */
    int (*open)(decoder_context_t* ctx, FIL* file);

    /* Close and cleanup */
    void (*close)(decoder_context_t* ctx);

    /* Decode samples (returns number of samples decoded, 0 at EOF, <0 on error) */
    int (*decode)(decoder_context_t* ctx, i16* buffer, u32 max_samples);

    /* Seek to position (in samples) */
    int (*seek)(decoder_context_t* ctx, u32 sample_pos);

    /* Get metadata */
    int (*get_metadata)(decoder_context_t* ctx, audio_metadata_t* meta);

    /* Get current position (in samples) */
    u32 (*get_position)(decoder_context_t* ctx);

    /* Get total samples */
    u32 (*get_total_samples)(decoder_context_t* ctx);
} decoder_ops_t;

/* Decoder context structure */
struct decoder_context {
    FIL* file;
    audio_format_t format;
    decoder_state_t state;
    audio_metadata_t metadata;
    const decoder_ops_t* ops;
    void* decoder_data;     /* Format-specific data */
    u32 sample_rate;
    u32 channels;
    u32 total_samples;
    u32 current_sample;
};

/* Helper functions */
audio_format_t decoder_detect_format(const char* filename);
const char* decoder_format_name(audio_format_t format);
int decoder_init(decoder_context_t* ctx, const char* filename);
void decoder_cleanup(decoder_context_t* ctx);

#endif /* DECODER_H */
