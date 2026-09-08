#pragma once

#include <cstdint>

#include "longbench/config.hpp"
#include "longbench/world.hpp"

namespace longbench {

void apply_frame_input(World& world, const RunConfig& config,
                       std::uint32_t tick);
void update_population(World& world, const RunConfig& config,
                       std::uint32_t tick);
void finalize_frame(World& world, std::uint32_t tick);

}  // namespace longbench
