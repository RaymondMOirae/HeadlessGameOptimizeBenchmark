#include "longbench/world.hpp"

#include <algorithm>
#include <limits>

namespace longbench {
namespace {

std::uint64_t next_random(std::uint64_t& state) {
  state += 0x9e3779b97f4a7c15ULL;
  std::uint64_t value = state;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  return value ^ (value >> 31U);
}

void hash_value(std::uint64_t& hash, std::uint64_t value) {
  constexpr std::uint64_t kPrime = 1099511628211ULL;
  for (int byte = 0; byte < 8; ++byte) {
    hash ^= (value >> (byte * 8)) & 0xffULL;
    hash *= kPrime;
  }
}

}  // namespace

std::uint64_t mix_digest(std::uint64_t state, std::uint64_t value) {
  value += 0x9e3779b97f4a7c15ULL;
  value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
  value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
  value ^= value >> 31U;
  state ^= value + 0x9e3779b97f4a7c15ULL + (state << 6U) + (state >> 2U);
  return state;
}

World make_world(const RunConfig& config) {
  World world;
  world.seed = config.seed;
  world.navigator_count = config.navigators;
  world.grid.width = config.grid_width;
  world.grid.height = config.grid_height;
  const std::size_t cells =
      static_cast<std::size_t>(config.grid_width) * config.grid_height;
  world.grid.terrain.resize(cells);
  world.grid.blocked.resize(cells);

  std::uint64_t random_state = config.seed ^ 0x4f1bbcdc6765d2a9ULL;
  for (std::size_t cell = 0; cell < cells; ++cell) {
    world.grid.terrain[cell] =
        static_cast<std::uint8_t>(1U + next_random(random_state) % 4U);
    world.grid.blocked[cell] =
        static_cast<std::uint8_t>(next_random(random_state) % 100U < 9U);
  }

  world.goals.reserve(config.goals);
  for (std::uint32_t slot = 0; slot < config.goals; ++slot) {
    std::uint32_t candidate =
        static_cast<std::uint32_t>(next_random(random_state) % cells);
    while (std::find(world.goals.begin(), world.goals.end(), candidate) !=
           world.goals.end()) {
      candidate = (candidate + 1U) % static_cast<std::uint32_t>(cells);
    }
    world.grid.blocked[candidate] = 0;
    world.goals.push_back(candidate);
  }

  world.units.reserve(config.units);
  for (std::uint32_t id = 0; id < config.units; ++id) {
    Unit unit;
    unit.id = id;
    unit.cell = static_cast<std::uint32_t>(next_random(random_state) % cells);
    if (id < config.navigators) {
      while (world.grid.blocked[unit.cell] != 0) {
        unit.cell = (unit.cell + 1U) % static_cast<std::uint32_t>(cells);
      }
    }
    unit.goal_slot = static_cast<std::uint16_t>(
        next_random(random_state) % std::max<std::uint32_t>(1U, config.goals));
    unit.flags = static_cast<std::uint16_t>(next_random(random_state) & 0xffU);
    unit.component_mask = static_cast<std::uint16_t>(
        1U | (next_random(random_state) & 0xffU));
    unit.health = 80 + static_cast<std::int32_t>(next_random(random_state) % 41U);
    unit.energy = 900 + static_cast<std::int32_t>(next_random(random_state) % 301U);
    unit.cooldown = static_cast<std::uint32_t>(next_random(random_state) % 17U);
    unit.inventory_digest = next_random(random_state);
    unit.behavior_state = next_random(random_state);
    world.units.push_back(unit);
  }

  world.transforms.reserve(config.transforms);
  for (std::uint32_t id = 0; id < config.transforms; ++id) {
    TransformNode node;
    node.id = id;
    if (id != 0U && id % 4096U != 0U) {
      node.parent = static_cast<std::uint32_t>(next_random(random_state) % id);
    }
    node.local_a = 1024 +
        static_cast<std::int32_t>(next_random(random_state) % 9U) - 4;
    node.local_b =
        static_cast<std::int32_t>(next_random(random_state) % 7U) - 3;
    node.local_c =
        static_cast<std::int32_t>(next_random(random_state) % 7U) - 3;
    node.local_d = 1024 +
        static_cast<std::int32_t>(next_random(random_state) % 9U) - 4;
    node.local_x =
        static_cast<std::int32_t>(next_random(random_state) % 2001U) - 1000;
    node.local_y =
        static_cast<std::int32_t>(next_random(random_state) % 2001U) - 1000;
    world.transforms.push_back(node);
  }

  world.colliders.reserve(config.colliders);
  for (std::uint32_t id = 0; id < config.colliders; ++id) {
    Collider collider;
    collider.transform = static_cast<std::uint32_t>(
        (static_cast<std::uint64_t>(id) * 2654435761ULL) % config.transforms);
    collider.half_x =
        6 + static_cast<std::int32_t>(next_random(random_state) % 35U);
    collider.half_y =
        6 + static_cast<std::int32_t>(next_random(random_state) % 35U);
    collider.layer = static_cast<std::uint8_t>(
        1U << static_cast<std::uint32_t>(next_random(random_state) % 4U));
    collider.mask =
        static_cast<std::uint8_t>(1U + next_random(random_state) % 15U);
    world.colliders.push_back(collider);
  }
  world.simulation_digest = mix_digest(config.seed, cells);
  world.route_digest = mix_digest(config.seed, config.navigators);
  world.transform_digest = mix_digest(config.seed, config.transforms);
  world.collision_digest = mix_digest(config.seed, config.colliders);
  world.event_digest = mix_digest(config.seed, config.events_per_frame);
  world.query_digest = mix_digest(config.seed, config.component_queries);
  world.interest_digest = mix_digest(config.seed, config.interest_observers);
  world.previous_interest.resize(
      std::min<std::uint32_t>(config.interest_observers, config.units));
  return world;
}

std::uint64_t hash_dynamic_state(const World& world) {
  std::uint64_t hash = 1469598103934665603ULL;
  hash_value(hash, world.grid.revision);
  hash_value(hash, world.simulation_digest);
  hash_value(hash, world.route_digest);
  hash_value(hash, world.transform_digest);
  hash_value(hash, world.collision_digest);
  hash_value(hash, world.event_digest);
  hash_value(hash, world.query_digest);
  hash_value(hash, world.interest_digest);
  hash_value(hash, world.collision_pair_count);
  hash_value(hash, world.query_match_count);
  hash_value(hash, world.interest_visible_count);
  hash_value(hash, world.units.size());
  for (const Unit& unit : world.units) {
    hash_value(hash, unit.id);
    hash_value(hash, unit.cell);
    hash_value(hash, unit.goal_slot);
    hash_value(hash, unit.flags);
    hash_value(hash, unit.component_mask);
    hash_value(hash, static_cast<std::uint32_t>(unit.health));
    hash_value(hash, static_cast<std::uint32_t>(unit.energy));
    hash_value(hash, unit.cooldown);
    hash_value(hash, unit.inventory_digest);
    hash_value(hash, unit.behavior_state);
  }
  for (std::uint8_t blocked : world.grid.blocked) {
    hash_value(hash, blocked);
  }
  hash_value(hash, world.previous_interest.size());
  for (const auto& visible : world.previous_interest) {
    hash_value(hash, visible.size());
    for (std::uint32_t index : visible) {
      hash_value(hash, index);
    }
  }
  hash_value(hash, world.transforms.size());
  for (const TransformNode& node : world.transforms) {
    hash_value(hash, node.id);
    hash_value(hash, node.parent);
    hash_value(hash, static_cast<std::uint64_t>(node.local_a));
    hash_value(hash, static_cast<std::uint64_t>(node.local_b));
    hash_value(hash, static_cast<std::uint64_t>(node.local_c));
    hash_value(hash, static_cast<std::uint64_t>(node.local_d));
    hash_value(hash, static_cast<std::uint64_t>(node.local_x));
    hash_value(hash, static_cast<std::uint64_t>(node.local_y));
    hash_value(hash, static_cast<std::uint64_t>(node.world_a));
    hash_value(hash, static_cast<std::uint64_t>(node.world_b));
    hash_value(hash, static_cast<std::uint64_t>(node.world_c));
    hash_value(hash, static_cast<std::uint64_t>(node.world_d));
    hash_value(hash, static_cast<std::uint64_t>(node.world_x));
    hash_value(hash, static_cast<std::uint64_t>(node.world_y));
  }
  return hash;
}

std::uint64_t hash_world(const World& world) {
  std::uint64_t hash = hash_dynamic_state(world);
  hash_value(hash, world.tick);
  hash_value(hash, world.rollback_digest);
  for (std::uint8_t terrain : world.grid.terrain) {
    hash_value(hash, terrain);
  }
  for (std::uint32_t goal : world.goals) {
    hash_value(hash, goal);
  }
  for (const Collider& collider : world.colliders) {
    hash_value(hash, collider.transform);
    hash_value(hash, static_cast<std::uint32_t>(collider.half_x));
    hash_value(hash, static_cast<std::uint32_t>(collider.half_y));
    hash_value(hash, collider.layer);
    hash_value(hash, collider.mask);
  }
  return hash;
}

}  // namespace longbench
