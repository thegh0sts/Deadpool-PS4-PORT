// SPDX-License-Identifier: GPL-2.0-or-later
// deadpool-port: real occlusion queries for ZPASS_DONE (PixelPipeStatDump) events.
//
// The guest brackets draws with two ZPASS_DONE events: the first writes each render backend's
// depth-pass counter at results + 16 * rb, the second at results + 8 + 16 * rb, and the game
// sums (end - begin) over the backends (bit 63 of each word: valid). The port used to write a
// counter that grew by a fixed step per event, so every query reported millions of visible
// samples. Unreal Engine 3 (Deadpool) uses these queries for visibility culling and to fade
// light coronas and lens flares: the stand-in drew every corona at full strength, through
// walls.
//
// Here a Vulkan occlusion query covers the draws between the two events. A Vulkan query may
// not span command buffers or render pass instances, so the scheduler (CarriedScope) ends it
// before every such boundary and a new one begins after it; the result is their sum. The
// begin words are written when the first event is reached (0, valid), the end words once the
// GPU has finished the draws (Rasterizer::SignalAfterGpu): render backend 0 gets the count,
// the others 0, all valid.
#pragma once

#include <mutex>
#include <vector>

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"

namespace Vulkan {

class Instance;
class Rasterizer;

class OcclusionQueries final : public Scheduler::CarriedScope {
public:
    /// Writes one 64-bit word of guest memory the way the command processor does (labels).
    using GuestWrite = void (*)(VAddr address, u64 value);

    OcclusionQueries(const Instance& instance, Scheduler& scheduler, Rasterizer& rasterizer);
    ~OcclusionQueries();

    /// Whether real queries are used (the device resets queries from the host; BB_OCCLUSION=0
    /// keeps the stand-in counter).
    [[nodiscard]] bool Enabled() const {
        return pool != VK_NULL_HANDLE;
    }

    /// A ZPASS_DONE event writing the counters at `address`: the end of the active query when
    /// it is that query's address + 8, else the beginning of one. In order with the draws, on
    /// the thread that records them.
    void Event(VAddr address, u32 num_pairs, GuestWrite write) {
        if (active && address == begin_address + 8) {
            End(address, num_pairs, write);
        } else {
            Begin(address, num_pairs, write);
        }
    }

    /// The first ZPASS_DONE event of a pair (results: its address).
    void Begin(VAddr results, u32 num_pairs, GuestWrite write);
    /// The second one (results: its address, the first one's + 8).
    void End(VAddr results, u32 num_pairs, GuestWrite write);

    // Scheduler::CarriedScope
    void Suspend(bool inside_render_pass) override;
    void Resume(bool inside_render_pass) override;

private:
    static constexpr u32 NumSlots = 4096;

    /// A Vulkan query slot reset on the host, or ~0u when all are in use.
    u32 AcquireSlot();
    void ReleaseSlots(const std::vector<u32>& slots);
    void OpenSlot();
    void CloseSlot();

    const Instance& instance;
    Scheduler& scheduler;
    Rasterizer& rasterizer;
    vk::Device device;
    vk::QueryPool pool{};
    vk::QueryControlFlags control{};

    std::mutex free_mutex; ///< the free slots (released on the GPU signal thread)
    std::vector<u32> free_slots;

    // The query being recorded (recording side only).
    bool active = false;
    VAddr begin_address = 0;
    u32 open_slot = ~0u;          ///< the Vulkan query begun and not ended yet
    std::vector<u32> used_slots;  ///< every Vulkan query of the active guest query
    bool overflow = false;        ///< slots ran out: the result is unknown (reported visible)

    u64 queries = 0, unmatched = 0;
};

} // namespace Vulkan
