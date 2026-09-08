#include "longbench/history.hpp"

#include <algorithm>

namespace longbench {

SnapshotHistory::SnapshotHistory(std::uint32_t capacity)
    : slots_(std::max<std::uint32_t>(1U, capacity)) {}

void SnapshotHistory::record(const World& world, std::uint32_t source_tick) {
  Snapshot& snapshot = slots_[source_tick % slots_.size()];
  snapshot.units = world.units;
  snapshot.transforms = world.transforms;
  snapshot.blocked = world.grid.blocked;
  snapshot.previous_interest = world.previous_interest;
  snapshot.grid_revision = world.grid.revision;
  snapshot.simulation_digest = world.simulation_digest;
  snapshot.route_digest = world.route_digest;
  snapshot.transform_digest = world.transform_digest;
  snapshot.collision_digest = world.collision_digest;
  snapshot.event_digest = world.event_digest;
  snapshot.query_digest = world.query_digest;
  snapshot.interest_digest = world.interest_digest;
  snapshot.collision_pair_count = world.collision_pair_count;
  snapshot.query_match_count = world.query_match_count;
  snapshot.interest_visible_count = world.interest_visible_count;
  snapshot.source_tick = source_tick;
  snapshot.valid = true;
}

bool SnapshotHistory::restore(World& world, std::uint32_t source_tick) const {
  const Snapshot& snapshot = slots_[source_tick % slots_.size()];
  if (!snapshot.valid || snapshot.source_tick != source_tick) {
    return false;
  }
  world.units = snapshot.units;
  world.transforms = snapshot.transforms;
  world.grid.blocked = snapshot.blocked;
  world.previous_interest = snapshot.previous_interest;
  world.grid.revision = snapshot.grid_revision;
  world.simulation_digest = snapshot.simulation_digest;
  world.route_digest = snapshot.route_digest;
  world.transform_digest = snapshot.transform_digest;
  world.collision_digest = snapshot.collision_digest;
  world.event_digest = snapshot.event_digest;
  world.query_digest = snapshot.query_digest;
  world.interest_digest = snapshot.interest_digest;
  world.collision_pair_count = snapshot.collision_pair_count;
  world.query_match_count = snapshot.query_match_count;
  world.interest_visible_count = snapshot.interest_visible_count;
  return true;
}

std::size_t SnapshotHistory::retained_bytes() const noexcept {
  std::size_t bytes = 0;
  for (const Snapshot& snapshot : slots_) {
    bytes += snapshot.units.capacity() * sizeof(Unit);
    bytes += snapshot.transforms.capacity() * sizeof(TransformNode);
    bytes += snapshot.blocked.capacity() * sizeof(std::uint8_t);
    bytes += snapshot.previous_interest.capacity() *
             sizeof(std::vector<std::uint32_t>);
    for (const auto& visible : snapshot.previous_interest) {
      bytes += visible.capacity() * sizeof(std::uint32_t);
    }
  }
  return bytes;
}

}  // namespace longbench
