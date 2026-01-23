/*
 * PaperJam Bare-Metal OS - Heap Allocator
 *
 * Simple first-fit allocator with block coalescing
 * Good enough for embedded use with limited allocations
 */

#include "hal/bcm2837.h"
#include "heap.h"

/* Heap boundaries (defined in linker script) */
extern u8 __heap_start;
extern u8 __stack_start;

/* Block header structure */
typedef struct block_header {
    u32 size;           /* Size of data area (not including header) */
    u32 is_free;        /* 1 if free, 0 if allocated */
    struct block_header* next;
    struct block_header* prev;
} block_header_t;

/* Minimum block size (header + 16 bytes data) */
#define MIN_BLOCK_SIZE  (sizeof(block_header_t) + 16)

/* Alignment */
#define ALIGN_SIZE      16
#define ALIGN(x)        (((x) + ALIGN_SIZE - 1) & ~(ALIGN_SIZE - 1))

/* Heap state */
static block_header_t* heap_head = NULL;
static u8* heap_end = NULL;
static u32 heap_total = 0;
static u32 heap_used = 0;

/*
 * Initialize the heap
 */
void heap_init(void) {
    u8* start = &__heap_start;
    u8* end = &__stack_start - 0x10000;  /* Leave 64KB for stack */

    /* Align start */
    start = (u8*)ALIGN((u64)start);

    heap_head = (block_header_t*)start;
    heap_end = end;
    heap_total = end - start - sizeof(block_header_t);

    /* Create single free block */
    heap_head->size = heap_total;
    heap_head->is_free = 1;
    heap_head->next = NULL;
    heap_head->prev = NULL;

    heap_used = 0;
}

/*
 * Allocate memory
 */
void* heap_alloc(u32 size) {
    if (size == 0) return NULL;

    /* Align size */
    size = ALIGN(size);

    /* Find first fit */
    block_header_t* block = heap_head;

    while (block) {
        if (block->is_free && block->size >= size) {
            /* Found a suitable block */

            /* Split if block is large enough */
            if (block->size >= size + MIN_BLOCK_SIZE) {
                block_header_t* new_block = (block_header_t*)((u8*)block + sizeof(block_header_t) + size);
                new_block->size = block->size - size - sizeof(block_header_t);
                new_block->is_free = 1;
                new_block->next = block->next;
                new_block->prev = block;

                if (block->next) {
                    block->next->prev = new_block;
                }
                block->next = new_block;
                block->size = size;
            }

            block->is_free = 0;
            heap_used += block->size + sizeof(block_header_t);

            return (void*)((u8*)block + sizeof(block_header_t));
        }
        block = block->next;
    }

    /* No suitable block found */
    return NULL;
}

/*
 * Free memory
 */
void heap_free(void* ptr) {
    if (!ptr) return;

    block_header_t* block = (block_header_t*)((u8*)ptr - sizeof(block_header_t));

    /* Sanity check */
    if ((u8*)block < (u8*)heap_head || (u8*)block >= heap_end) {
        return;
    }

    block->is_free = 1;
    heap_used -= block->size + sizeof(block_header_t);

    /* Coalesce with next block */
    if (block->next && block->next->is_free) {
        block->size += block->next->size + sizeof(block_header_t);
        block->next = block->next->next;
        if (block->next) {
            block->next->prev = block;
        }
    }

    /* Coalesce with previous block */
    if (block->prev && block->prev->is_free) {
        block->prev->size += block->size + sizeof(block_header_t);
        block->prev->next = block->next;
        if (block->next) {
            block->next->prev = block->prev;
        }
    }
}

/*
 * Reallocate memory
 */
void* heap_realloc(void* ptr, u32 size) {
    if (!ptr) return heap_alloc(size);
    if (size == 0) {
        heap_free(ptr);
        return NULL;
    }

    block_header_t* block = (block_header_t*)((u8*)ptr - sizeof(block_header_t));
    u32 old_size = block->size;

    /* If new size fits in current block, return same pointer */
    size = ALIGN(size);
    if (size <= old_size) {
        return ptr;
    }

    /* Try to expand into next free block */
    if (block->next && block->next->is_free) {
        u32 combined = old_size + block->next->size + sizeof(block_header_t);
        if (combined >= size) {
            heap_used += block->next->size + sizeof(block_header_t);
            block->size = combined;
            block->next = block->next->next;
            if (block->next) {
                block->next->prev = block;
            }
            return ptr;
        }
    }

    /* Allocate new block and copy */
    void* new_ptr = heap_alloc(size);
    if (!new_ptr) return NULL;

    /* Copy data */
    u8* src = (u8*)ptr;
    u8* dst = (u8*)new_ptr;
    for (u32 i = 0; i < old_size; i++) {
        dst[i] = src[i];
    }

    heap_free(ptr);
    return new_ptr;
}

/*
 * Allocate zeroed memory
 */
void* heap_calloc(u32 count, u32 size) {
    u32 total = count * size;
    void* ptr = heap_alloc(total);
    if (ptr) {
        u8* p = (u8*)ptr;
        for (u32 i = 0; i < total; i++) {
            p[i] = 0;
        }
    }
    return ptr;
}

/*
 * Get heap statistics
 */
u32 heap_get_total(void) {
    return heap_total;
}

u32 heap_get_used(void) {
    return heap_used;
}

u32 heap_get_free(void) {
    return heap_total - heap_used;
}

/*
 * Get largest free block
 */
u32 heap_get_largest_free(void) {
    u32 largest = 0;
    block_header_t* block = heap_head;

    while (block) {
        if (block->is_free && block->size > largest) {
            largest = block->size;
        }
        block = block->next;
    }

    return largest;
}

/*
 * Memory copy
 */
void* memcpy(void* dst, const void* src, u32 n) {
    u8* d = (u8*)dst;
    const u8* s = (const u8*)src;
    while (n--) {
        *d++ = *s++;
    }
    return dst;
}

/*
 * Memory set
 */
void* memset(void* dst, int c, u32 n) {
    u8* d = (u8*)dst;
    while (n--) {
        *d++ = (u8)c;
    }
    return dst;
}

/*
 * Memory compare
 */
int memcmp(const void* s1, const void* s2, u32 n) {
    const u8* p1 = (const u8*)s1;
    const u8* p2 = (const u8*)s2;
    while (n--) {
        if (*p1 != *p2) {
            return *p1 - *p2;
        }
        p1++;
        p2++;
    }
    return 0;
}

/*
 * String length
 */
u32 strlen(const char* s) {
    u32 len = 0;
    while (*s++) len++;
    return len;
}

/*
 * String copy
 */
char* strcpy(char* dst, const char* src) {
    char* d = dst;
    while ((*d++ = *src++));
    return dst;
}

/*
 * String compare
 */
int strcmp(const char* s1, const char* s2) {
    while (*s1 && (*s1 == *s2)) {
        s1++;
        s2++;
    }
    return *(u8*)s1 - *(u8*)s2;
}

/*
 * String n-compare
 */
int strncmp(const char* s1, const char* s2, u32 n) {
    while (n && *s1 && (*s1 == *s2)) {
        s1++;
        s2++;
        n--;
    }
    if (n == 0) return 0;
    return *(u8*)s1 - *(u8*)s2;
}
