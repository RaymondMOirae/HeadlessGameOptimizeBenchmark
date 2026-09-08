#pragma once

#include <cstddef>
#include <cstdint>

#include "longbench/config.hpp"

namespace longbench {

struct RunResult {
  std::uint64_t checksum = 0;
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
  std::uint64_t measured_ns = 0;
  std::uint64_t frame_p50_ns = 0;
  std::uint64_t frame_p95_ns = 0;
  std::uint64_t frame_p99_ns = 0;
  std::size_t retained_history_bytes = 0;
  std::uint32_t frames = 0;
  std::uint32_t units = 0;
  std::uint32_t transforms = 0;
  std::uint32_t colliders = 0;
};

RunResult run_game(const RunConfig& config);

}  // namespace longbench
