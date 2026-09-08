#include "longbench/systems.hpp"

#include <algorithm>

namespace longbench {
namespace {

std::uint64_t deterministic_value(std::uint64_t seed, std::uint32_t tick,
                                  std::uint64_t salt) {
  std::uint64_t value = seed ^
      (static_cast<std::uint64_t>(tick) * 0x9e3779b97f4a7c15ULL) ^ salt;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return value ^ (value >> 31U);
}

bool is_goal(const World& world, std::uint32_t cell) {
  return std::find(world.goals.begin(), world.goals.end(), cell) !=
         world.goals.end();
}

}  // namespace

void apply_frame_input(World& world, const RunConfig& config,
                       std::uint32_t tick) {
  if (config.edit_period != 0U && tick % config.edit_period == 0U) {
    const std::uint32_t cells =
        static_cast<std::uint32_t>(world.grid.blocked.size());
    for (std::uint32_t edit = 0; edit < config.edits_per_period; ++edit) {
      std::uint32_t cell = static_cast<std::uint32_t>(
          deterministic_value(world.seed, tick, 0x1000ULL + edit) % cells);
      for (std::uint32_t attempt = 0; attempt < cells && is_goal(world, cell);
           ++attempt) {
        cell = (cell + 1U) % cells;
      }
      if (!is_goal(world, cell)) {
        world.grid.blocked[cell] ^= 1U;
        ++world.grid.revision;
      }
    }
  }

  if (!world.goals.empty() && world.navigator_count != 0U && tick % 13U == 5U) {
    const std::uint32_t changes = std::min<std::uint32_t>(7U, world.navigator_count);
    for (std::uint32_t change = 0; change < changes; ++change) {
      const std::uint32_t index = static_cast<std::uint32_t>(
          deterministic_value(world.seed, tick, 0x2000ULL + change) %
          world.navigator_count);
      world.units[index].goal_slot = static_cast<std::uint16_t>(
          (world.units[index].goal_slot + 1U + change) % world.goals.size());
    }
  }

  if (!world.transforms.empty()) {
    const std::uint32_t transform_count =
        static_cast<std::uint32_t>(world.transforms.size());
    const std::uint32_t first_mutable = transform_count / 2U;
    const std::uint32_t mutable_count = transform_count - first_mutable;
    const std::uint32_t changes = std::min<std::uint32_t>(
        config.transform_mutations_per_frame, transform_count);
    for (std::uint32_t change = 0; change < changes; ++change) {
      const std::uint64_t value = deterministic_value(
          world.seed, tick, 0x5000ULL + static_cast<std::uint64_t>(change) * 31U);
      const std::uint32_t index = first_mutable +
          static_cast<std::uint32_t>(value % mutable_count);
      TransformNode& node = world.transforms[index];
      node.local_x += static_cast<std::int32_t>((value >> 9U) % 9U) - 4;
      node.local_y += static_cast<std::int32_t>((value >> 17U) % 9U) - 4;
      if (change % 11U == 0U) {
        node.local_a += static_cast<std::int32_t>((value >> 25U) % 3U) - 1;
        node.local_d += static_cast<std::int32_t>((value >> 33U) % 3U) - 1;
      }
    }

    if (config.reparent_period != 0U && transform_count > 1U &&
        tick % config.reparent_period == config.reparent_period - 1U) {
      const std::uint64_t value =
          deterministic_value(world.seed, tick, 0x5f00ULL);
      const std::uint32_t index = 1U +
          static_cast<std::uint32_t>(value % (transform_count - 1U));
      world.transforms[index].parent =
          static_cast<std::uint32_t>((value >> 32U) % index);
    }
  }

  if (!world.units.empty()) {
    const std::uint32_t structural_changes = std::min<std::uint32_t>(
        config.structural_changes_per_frame,
        static_cast<std::uint32_t>(world.units.size()));
    for (std::uint32_t change = 0; change < structural_changes; ++change) {
      const std::uint64_t value = deterministic_value(
          world.seed, tick, 0x8100ULL + static_cast<std::uint64_t>(change) * 47U);
      Unit& unit = world.units[static_cast<std::size_t>(value % world.units.size())];
      const std::uint16_t bit =
          static_cast<std::uint16_t>(1U << ((value >> 21U) & 7U));
      unit.component_mask ^= bit;
      if (unit.component_mask == 0U) {
        unit.component_mask = 1U;
      }
    }

    const std::uint32_t movements = std::min<std::uint32_t>(
        config.interest_movements_per_frame,
        static_cast<std::uint32_t>(world.units.size()));
    const std::uint32_t cells =
        static_cast<std::uint32_t>(world.grid.blocked.size());
    for (std::uint32_t movement = 0; movement < movements; ++movement) {
      const std::uint64_t value = deterministic_value(
          world.seed, tick,
          0x8900ULL + static_cast<std::uint64_t>(movement) * 53U);
      const std::uint32_t first_non_navigator = std::min<std::uint32_t>(
          world.navigator_count, static_cast<std::uint32_t>(world.units.size()));
      const std::uint32_t movable =
          static_cast<std::uint32_t>(world.units.size()) - first_non_navigator;
      if (movable == 0U) {
        break;
      }
      Unit& unit = world.units[first_non_navigator +
                               static_cast<std::uint32_t>(value % movable)];
      const std::int32_t delta = static_cast<std::int32_t>((value >> 29U) % 9U) - 4;
      unit.cell = static_cast<std::uint32_t>(
          (static_cast<std::int64_t>(unit.cell) + delta + cells) % cells);
    }
  }
}

void update_population(World& world, const RunConfig& config,
                       std::uint32_t tick) {
  if (world.units.empty()) {
    return;
  }
  const std::uint32_t count = std::min<std::uint32_t>(
      config.mutations_per_frame, static_cast<std::uint32_t>(world.units.size()));
  for (std::uint32_t mutation = 0; mutation < count; ++mutation) {
    const std::uint32_t index = static_cast<std::uint32_t>(
        deterministic_value(world.seed, tick, 0x3000ULL + mutation * 17ULL) %
        world.units.size());
    Unit& unit = world.units[index];
    const std::uint64_t value =
        deterministic_value(world.seed ^ unit.id, tick, mutation + 0x4000ULL);
    unit.health += static_cast<std::int32_t>(value % 7U) - 3;
    if (unit.health < -50 || unit.health > 180) {
      unit.health = 100;
    }
    unit.cooldown = (unit.cooldown + 1U + static_cast<std::uint32_t>(value & 3U)) % 31U;
    unit.inventory_digest = mix_digest(unit.inventory_digest, value);
    unit.behavior_state ^= value + static_cast<std::uint64_t>(tick);
  }
}

void finalize_frame(World& world, std::uint32_t tick) {
  std::uint64_t value = static_cast<std::uint64_t>(tick) << 32U;
  value ^= world.grid.revision;
  value ^= world.route_digest;
  value ^= world.transform_digest;
  value ^= world.collision_digest;
  value ^= world.event_digest;
  value ^= world.query_digest;
  value ^= world.interest_digest;
  value ^= world.collision_pair_count * 0x9e3779b97f4a7c15ULL;
  value ^= world.query_match_count * 0xbf58476d1ce4e5b9ULL;
  value ^= world.interest_visible_count * 0x94d049bb133111ebULL;
  if (!world.units.empty()) {
    const Unit& sample = world.units[(tick * 977U) % world.units.size()];
    value ^= sample.inventory_digest;
    value ^= static_cast<std::uint64_t>(sample.cell) << 11U;
  }
  world.simulation_digest = mix_digest(world.simulation_digest, value);
}

}  // namespace longbench
