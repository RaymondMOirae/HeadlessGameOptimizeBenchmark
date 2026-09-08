#pragma once

#include <cstdint>

#include "longbench/config.hpp"
#include "longbench/world.hpp"

namespace longbench {

void produce_and_dispatch_events(World& world, const RunConfig& config,
                                 std::uint32_t tick);

}  // namespace longbench
