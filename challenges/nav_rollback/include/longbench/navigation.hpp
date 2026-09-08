#pragma once

#include <cstdint>

#include "longbench/world.hpp"

namespace longbench {

std::uint32_t compute_next_cell(const Grid& grid, std::uint32_t start,
                                std::uint32_t goal);
void update_navigation(World& world);

}  // namespace longbench
