#include "longbench/navigation.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <limits>
#include <queue>
#include <utility>
#include <vector>

namespace longbench {
namespace {

constexpr std::uint32_t kUnreachable =
    std::numeric_limits<std::uint32_t>::max() / 4U;

template <typename Function>
void for_each_neighbor(const Grid& grid, std::uint32_t cell, Function&& function) {
  const std::uint32_t x = cell % grid.width;
  const std::uint32_t y = cell / grid.width;
  // This order is part of the simulation contract for equal-cost first steps.
  if (y > 0U) function(cell - grid.width);       // up
  if (x > 0U) function(cell - 1U);              // left
  if (x + 1U < grid.width) function(cell + 1U); // right
  if (y + 1U < grid.height) function(cell + grid.width);  // down
}

}  // namespace

std::uint32_t compute_next_cell(const Grid& grid, std::uint32_t start,
                                std::uint32_t goal) {
  if (start == goal) {
    return start;
  }
  const std::size_t cell_count = grid.terrain.size();
  std::vector<std::uint32_t> distance(cell_count, kUnreachable);
  using QueueItem = std::pair<std::uint32_t, std::uint32_t>;
  std::priority_queue<QueueItem, std::vector<QueueItem>, std::greater<QueueItem>>
      frontier;
  distance[goal] = 0;
  frontier.emplace(0U, goal);

  while (!frontier.empty()) {
    const auto [known_distance, cell] = frontier.top();
    frontier.pop();
    if (known_distance != distance[cell]) {
      continue;
    }
    for_each_neighbor(grid, cell, [&](std::uint32_t predecessor) {
      if (grid.blocked[predecessor] != 0) {
        return;
      }
      const std::uint32_t candidate =
          known_distance + static_cast<std::uint32_t>(grid.terrain[cell]);
      if (candidate < distance[predecessor]) {
        distance[predecessor] = candidate;
        frontier.emplace(candidate, predecessor);
      }
    });
  }

  std::uint32_t best_cell = start;
  std::uint32_t best_cost = kUnreachable;
  for_each_neighbor(grid, start, [&](std::uint32_t neighbor) {
    if (grid.blocked[neighbor] != 0 || distance[neighbor] == kUnreachable) {
      return;
    }
    const std::uint32_t candidate =
        static_cast<std::uint32_t>(grid.terrain[neighbor]) + distance[neighbor];
    if (candidate < best_cost) {
      best_cost = candidate;
      best_cell = neighbor;
    }
  });
  return best_cell;
}

void update_navigation(World& world) {
  const std::uint32_t count =
      std::min<std::uint32_t>(world.navigator_count,
                              static_cast<std::uint32_t>(world.units.size()));
  for (std::uint32_t index = 0; index < count; ++index) {
    Unit& unit = world.units[index];
    const std::uint32_t goal =
        world.goals[unit.goal_slot % world.goals.size()];
    const std::uint32_t next = compute_next_cell(world.grid, unit.cell, goal);
    if (next != unit.cell) {
      unit.cell = next;
      unit.energy -= static_cast<std::int32_t>(world.grid.terrain[next]);
      if (unit.energy < -2000) {
        unit.energy = 1200;
      }
    }
    const std::uint64_t packed =
        (static_cast<std::uint64_t>(unit.id) << 32U) ^ unit.cell;
    world.route_digest = mix_digest(world.route_digest, packed);
  }
}

}  // namespace longbench
