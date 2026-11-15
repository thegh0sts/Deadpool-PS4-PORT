// SPDX-License-Identifier: GPL-2.0-or-later
#include "video_core/renderer_vulkan/vk_occlusion.h"

#include <cstdio>
#include <cstdlib>

#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_rasterizer.h"

namespace Vulkan {

namespace {
constexpr u64 ValidBit = 0x8000000000000000ULL;
/// A query whose result is unknown (no slot, or an end without a begin): reported as plenty
/// visible, so nothing is culled by mistake (the old stand-in's answer).
constexpr u64 UnknownCount = 0x2FFFFFFULL;
} // namespace

OcclusionQueries::OcclusionQueries(const Instance& instance_, Scheduler& scheduler_,
                                   Rasterizer& rasterizer_)
    : instance{instance_}, scheduler{scheduler_}, rasterizer{rasterizer_},
      device{instance_.GetDevice()} {
    const char* env = std::getenv("BB_OCCLUSION");
    if (env && env[0] == '0') {
        std::printf("Occlusion queries: stand-in counter (BB_OCCLUSION=0)\n");
        return;
    }
    if (!instance.IsHostQueryResetSupported()) {
        std::printf("Occlusion queries: stand-in counter (the device cannot reset queries from "
                    "the host)\n");
        return;
    }
    const vk::QueryPoolCreateInfo info{
        .queryType = vk::QueryType::eOcclusion,
        .queryCount = NumSlots,
    };
    auto [result, created] = device.createQueryPool(info);
    if (result != vk::Result::eSuccess) {
        std::printf("Occlusion queries: stand-in counter (no query pool: %s)\n",
                    vk::to_string(result).c_str());
        return;
    }
    pool = created;
    device.resetQueryPool(pool, 0, NumSlots);
    if (instance.IsOcclusionQueryPrecise()) {
        control = vk::QueryControlFlagBits::ePrecise;
    }
    free_slots.reserve(NumSlots);
    for (u32 i = NumSlots; i-- > 0;) {
        free_slots.push_back(i);
    }
    std::printf("Occlusion queries: Vulkan queries (%s counts)\n",
                control ? "precise" : "approximate");
}

OcclusionQueries::~OcclusionQueries() {
    if (pool) {
        device.destroyQueryPool(pool);
    }
}

u32 OcclusionQueries::AcquireSlot() {
    std::scoped_lock lk{free_mutex};
    if (free_slots.empty()) {
        return ~0u;
    }
    const u32 slot = free_slots.back();
    free_slots.pop_back();
    return slot;
}

void OcclusionQueries::ReleaseSlots(const std::vector<u32>& slots) {
    std::scoped_lock lk{free_mutex};
    for (const u32 slot : slots) {
        // Reset here, on the host, after its result was read: the slot is not in use.
        device.resetQueryPool(pool, slot, 1);
        free_slots.push_back(slot);
    }
}

void OcclusionQueries::OpenSlot() {
    const u32 slot = AcquireSlot();
    if (slot == ~0u) {
        overflow = true;
        return;
    }
    open_slot = slot;
    used_slots.push_back(slot);
    scheduler.Record([pool = pool, slot, control = control](vk::CommandBuffer cmdbuf) {
        cmdbuf.beginQuery(pool, slot, control);
    });
}

void OcclusionQueries::CloseSlot() {
    if (open_slot == ~0u) {
        return;
    }
    scheduler.Record([pool = pool, slot = open_slot](vk::CommandBuffer cmdbuf) {
        cmdbuf.endQuery(pool, slot);
    });
    open_slot = ~0u;
}

void OcclusionQueries::Suspend(bool) {
    if (active) {
        CloseSlot();
    }
}

void OcclusionQueries::Resume(bool) {
    if (active && !overflow) {
        OpenSlot();
    }
}

void OcclusionQueries::Begin(VAddr results, u32 num_pairs, GuestWrite write) {
    if (active) {
        // A begin without an end: the earlier one is dropped (its words stay as they are).
        ++unmatched;
        CloseSlot();
        scheduler.SetCarriedScope(nullptr);
        active = false;
        if (!used_slots.empty()) {
            rasterizer.SignalAfterGpu([this, slots = std::move(used_slots)] { ReleaseSlots(slots); });
        }
        used_slots.clear();
    }
    for (u32 i = 0; i < num_pairs; ++i) {
        write(results + 16 * i, ValidBit);
    }
    active = true;
    begin_address = results;
    overflow = false;
    used_slots.clear();
    scheduler.SetCarriedScope(this);
    OpenSlot();
    if (++queries == 1) {
        std::printf("Occlusion queries: first query at %#llx\n", (unsigned long long)results);
    }
}

void OcclusionQueries::End(VAddr results, u32 num_pairs, GuestWrite write) {
    if (!active || results != begin_address + 8) {
        // No matching begin: the old answer (visible), written now.
        if (++unmatched <= 4) {
            std::printf("Occlusion queries: end at %#llx without its begin (begin %#llx)\n",
                        (unsigned long long)results, (unsigned long long)begin_address);
        }
        for (u32 i = 0; i < num_pairs; ++i) {
            write(results + 16 * i, ValidBit | (i == 0 ? UnknownCount : 0));
        }
        if (!active) {
            return;
        }
    }
    CloseSlot();
    scheduler.SetCarriedScope(nullptr);
    active = false;
    if (results != begin_address + 8) {
        if (!used_slots.empty()) {
            rasterizer.SignalAfterGpu([this, slots = std::move(used_slots)] { ReleaseSlots(slots); });
        }
        used_slots.clear();
        return;
    }
    // After the GPU has run the draws: the sum of the Vulkan queries, into render backend 0.
    rasterizer.SignalAfterGpu([this, slots = std::move(used_slots), overflow = overflow, results,
                               num_pairs, write] {
        u64 count = 0;
        for (const u32 slot : slots) {
            u64 value = 0;
            const auto result = device.getQueryPoolResults(
                pool, slot, 1, sizeof(value), &value, sizeof(value),
                vk::QueryResultFlagBits::e64 | vk::QueryResultFlagBits::eWait);
            if (result == vk::Result::eSuccess) {
                count += value;
            }
        }
        if (overflow) {
            count = UnknownCount;
        }
        for (u32 i = 0; i < num_pairs; ++i) {
            write(results + 16 * i, ValidBit | (i == 0 ? count : 0));
        }
        ReleaseSlots(slots);
    });
    used_slots.clear();
}

} // namespace Vulkan
