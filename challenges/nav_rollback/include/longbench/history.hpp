#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "longbench/world.hpp"

namespace longbench {

class SnapshotHistory {
 public:
  explicit SnapshotHistory(std::uint32_t capacity);

  void record(const World& world, std::uint32_t source_tick);
  bool restore(World& world, std::uint32_t source_tick) const;
  std::size_t retained_bytes() const noexcept;

 private:
  struct Snapshot {
    std::vector<Unit> units;
    std::vector<TransformNode> transforms;
    std::vector<std::uint8_t> blocked;
    std::vector<std::vector<std::uint32_t>> previous_interest;
    std::uint64_t grid_revision = 0;
    std::uint64_t simulation_digest = 0;
    std::uint64_t route_digest = 0;
    std::uint64_t transform_digest = 0;
    std::uint64_t collision_digest = 0;
    std::uint64_t event_digest = 0;
    std::uint64_t query_digest = 0;
    std::uint64_t interest_digest = 0;
    std::uint64_t collision_pair_count = 0;
    std::uint64_t query_match_count = 0;
    std::uint64_t interest_visible_count = 0;
    std::uint32_t source_tick = 0;
    bool valid = false;
  };

  std::vector<Snapshot> slots_;
};

}  // namespace longbench
