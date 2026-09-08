#include "longbench/interest.hpp"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <vector>

namespace longbench {

void update_interest_management(World& world, const RunConfig& config,
                                std::uint32_t tick) {
  const std::uint32_t observer_count = std::min<std::uint32_t>(
      config.interest_observers, static_cast<std::uint32_t>(world.units.size()));
  if (observer_count == 0U) {
    world.interest_visible_count = 0;
    return;
  }
  if (world.previous_interest.size() != observer_count) {
    world.previous_interest.resize(observer_count);
  }

  std::uint64_t frame_digest = mix_digest(world.seed ^ 0x1a7e2e57ULL, tick);
  std::uint64_t total_visible = 0;
  for (std::uint32_t slot = 0; slot < observer_count; ++slot) {
    const std::uint32_t observer_index = static_cast<std::uint32_t>(
        (static_cast<std::uint64_t>(slot) * 2654435761ULL +
         static_cast<std::uint64_t>(tick) * 17ULL) % world.units.size());
    Unit& observer = world.units[observer_index];
    const std::uint32_t observer_x = observer.cell % world.grid.width;
    const std::uint32_t observer_y = observer.cell / world.grid.width;
    const std::uint16_t observer_team = observer.component_mask & 3U;

    std::vector<std::uint32_t> visible;
    for (std::uint32_t index = 0; index < world.units.size(); ++index) {
      if (index == observer_index) {
        continue;
      }
      const Unit& candidate = world.units[index];
      if ((candidate.component_mask & 3U) != observer_team) {
        continue;
      }
      const std::uint32_t candidate_x = candidate.cell % world.grid.width;
      const std::uint32_t candidate_y = candidate.cell / world.grid.width;
      const std::uint32_t distance =
          static_cast<std::uint32_t>(std::abs(
              static_cast<std::int32_t>(observer_x) -
              static_cast<std::int32_t>(candidate_x))) +
          static_cast<std::uint32_t>(std::abs(
              static_cast<std::int32_t>(observer_y) -
              static_cast<std::int32_t>(candidate_y)));
      if (distance <= config.interest_radius) {
        visible.push_back(index);
      }
    }

    const std::vector<std::uint32_t>& previous = world.previous_interest[slot];
    std::size_t old_index = 0;
    std::size_t new_index = 0;
    std::uint64_t delta_digest = mix_digest(observer.id, slot);
    std::uint32_t enters = 0;
    std::uint32_t leaves = 0;
    while (old_index < previous.size() || new_index < visible.size()) {
      if (new_index == visible.size() ||
          (old_index < previous.size() &&
           previous[old_index] < visible[new_index])) {
        delta_digest = mix_digest(
            delta_digest, 0x8000000000000000ULL | previous[old_index++]);
        ++leaves;
      } else if (old_index == previous.size() ||
                 visible[new_index] < previous[old_index]) {
        delta_digest = mix_digest(delta_digest, visible[new_index++]);
        ++enters;
      } else {
        delta_digest = mix_digest(
            delta_digest, 0x4000000000000000ULL | visible[new_index]);
        ++old_index;
        ++new_index;
      }
    }
    delta_digest = mix_digest(
        delta_digest, (static_cast<std::uint64_t>(enters) << 32U) | leaves);
    observer.behavior_state = mix_digest(observer.behavior_state, delta_digest);
    total_visible += visible.size();
    frame_digest = mix_digest(
        frame_digest, mix_digest(delta_digest, visible.size()));
    world.previous_interest[slot] = std::move(visible);
  }
  world.interest_visible_count = total_visible;
  world.interest_digest = mix_digest(world.interest_digest, frame_digest);
}

}  // namespace longbench
