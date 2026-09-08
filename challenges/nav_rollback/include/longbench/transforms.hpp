#pragma once

#include <cstdint>

#include "longbench/world.hpp"

namespace longbench {

void update_transforms(World& world, std::uint32_t tick);

}  // namespace longbench
