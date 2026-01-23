/*
 * PaperJam Bare-Metal OS - JPEG Decoder Header
 */

#ifndef JPEG_H
#define JPEG_H

#include "hal/bcm2837.h"

/*
 * Decode JPEG image to 8-bit grayscale
 *
 * data: Input JPEG data
 * size: Size of input data
 * output: Output buffer for grayscale pixels (caller must allocate)
 * out_width: Receives actual output width
 * out_height: Receives actual output height
 * max_width: Maximum output width (will scale down if needed)
 * max_height: Maximum output height (will scale down if needed)
 *
 * Returns: 0 on success, -1 on error
 */
int jpeg_decode(const u8* data, u32 size, u8* output,
                int* out_width, int* out_height,
                int max_width, int max_height);

/*
 * Check if data appears to be a JPEG image
 */
int jpeg_is_jpeg(const u8* data, u32 size);

#endif /* JPEG_H */
