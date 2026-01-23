/*
 * PaperJam Bare-Metal OS - Heap Allocator Header
 */

#ifndef HEAP_H
#define HEAP_H

#include "hal/bcm2837.h"

/* Heap management */
void  heap_init(void);
void* heap_alloc(u32 size);
void  heap_free(void* ptr);
void* heap_realloc(void* ptr, u32 size);
void* heap_calloc(u32 count, u32 size);

/* Heap statistics */
u32   heap_get_total(void);
u32   heap_get_used(void);
u32   heap_get_free(void);
u32   heap_get_largest_free(void);

/* Standard C library replacements */
void* memcpy(void* dst, const void* src, u32 n);
void* memset(void* dst, int c, u32 n);
int   memcmp(const void* s1, const void* s2, u32 n);
u32   strlen(const char* s);
char* strcpy(char* dst, const char* src);
int   strcmp(const char* s1, const char* s2);
int   strncmp(const char* s1, const char* s2, u32 n);

/* Convenience macros */
#define malloc(size)        heap_alloc(size)
#define free(ptr)           heap_free(ptr)
#define realloc(ptr, size)  heap_realloc(ptr, size)
#define calloc(n, size)     heap_calloc(n, size)

#endif /* HEAP_H */
