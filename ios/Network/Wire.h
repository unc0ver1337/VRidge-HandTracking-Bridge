#pragma once
#include <stdint.h>
// ARM64 iOS and Windows are little-endian. No native padding on the wire.
typedef struct __attribute__((packed)) {
    char magic[4]; uint8_t version, count; uint16_t flags;
    uint32_t sequence; uint64_t session; double capture;
    uint16_t width, height; float fx, fy, cx, cy;
} VHHeader;
typedef struct __attribute__((packed)) {
    uint32_t identity; uint8_t side; int8_t palm; uint16_t reserved;
    float landmarks[21][3];
    float world[21][3]; float position[3],rotation[4],reprojection; uint32_t poseValid;
} VHHand;
static_assert(sizeof(VHHeader)==48,"wire header");
static_assert(sizeof(VHHand)==548,"wire hand");
