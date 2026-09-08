#pragma once

#include <array>
#include <cstdint>
#include <vector>

#include "longbench/config.hpp"

namespace longbench {

struct Unit {
  std::uint32_t id = 0;
  std::uint32_t cell = 0;
  std::uint16_t goal_slot = 0;
  std::uint16_t flags = 0;
  std::uint16_t component_mask = 0;
  std::int32_t health = 100;
  std::int32_t energy = 1000;
  std::uint32_t cooldown = 0;
  std::uint64_t inventory_digest = 0;
  std::uint64_t behavior_state = 0;
};

struct Grid {
  std::uint32_t width = 0;
  std::uint32_t height = 0;
  std::uint64_t revision = 0;
  std::vector<std::uint8_t> terrain;
  std::vector<std::uint8_t> blocked;
};

constexpr std::uint32_t kNoParent = 0xffffffffU;

struct TransformNode {
  std::uint32_t id = 0;
  std::uint32_t parent = kNoParent;
  std::int32_t local_a = 1024;
  std::int32_t local_b = 0;
  std::int32_t local_c = 0;
  std::int32_t local_d = 1024;
  std::int32_t local_x = 0;
  std::int32_t local_y = 0;
  std::int64_t world_a = 1024;
  std::int64_t world_b = 0;
  std::int64_t world_c = 0;
  std::int64_t world_d = 1024;
  std::int64_t world_x = 0;
  std::int64_t world_y = 0;
};

struct Collider {
  std::uint32_t transform = 0;
  std::int32_t half_x = 1;
  std::int32_t half_y = 1;
  std::uint8_t layer = 1;
  std::uint8_t mask = 0xff;
};

struct World {
  Grid grid;
  std::vector<Unit> units;
  std::vector<std::uint32_t> goals;
  std::vector<TransformNode> transforms;
  std::vector<Collider> colliders;
  std::vector<std::vector<std::uint32_t>> previous_interest;
  std::uint64_t seed = 0;
  std::uint64_t simulation_digest = 0;
  std::uint64_t route_digest = 0;
  std::uint64_t rollback_digest = 0;
  std::uint64_t transform_digest = 0;
  std::uint64_t collision_digest = 0;
  std::uint64_t event_digest = 0;
  std::uint64_t query_digest = 0;
  std::uint64_t interest_digest = 0;
  std::uint64_t collision_pair_count = 0;
  std::uint64_t query_match_count = 0;
  std::uint64_t interest_visible_count = 0;
  std::uint32_t navigator_count = 0;
  std::uint32_t tick = 0;
};

World make_world(const RunConfig& config);
std::uint64_t hash_world(const World& world);
std::uint64_t hash_dynamic_state(const World& world);
std::uint64_t mix_digest(std::uint64_t state, std::uint64_t value);

}  // namespace longbench
