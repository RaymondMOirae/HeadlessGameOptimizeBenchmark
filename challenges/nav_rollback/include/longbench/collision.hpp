#pragma once

#include <cstdint>

#include "longbench/world.hpp"

namespace longbench {

std::uint64_t update_collisions(World& world, std::uint32_t tick);

}  // namespace longbench
