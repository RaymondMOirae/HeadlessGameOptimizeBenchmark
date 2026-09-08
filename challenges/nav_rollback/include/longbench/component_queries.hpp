#pragma once

#include <cstdint>

#include "longbench/config.hpp"
#include "longbench/world.hpp"

namespace longbench {

void update_component_queries(World& world, const RunConfig& config,
                              std::uint32_t tick);

}  // namespace longbench
