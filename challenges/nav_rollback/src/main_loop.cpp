#include "longbench/main_loop.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <vector>

#include "longbench/history.hpp"
#include "longbench/collision.hpp"
#include "longbench/component_queries.hpp"
#include "longbench/events.hpp"
#include "longbench/interest.hpp"
#include "longbench/navigation.hpp"
#include "longbench/profile.hpp"
#include "longbench/systems.hpp"
#include "longbench/transforms.hpp"
#include "longbench/world.hpp"

namespace longbench {
namespace {

using Clock = std::chrono::steady_clock;

std::uint64_t percentile(std::vector<std::uint64_t> values, double quantile) {
  if (values.empty()) {
    return 0;
  }
  std::sort(values.begin(), values.end());
  const double position = quantile * static_cast<double>(values.size() - 1U);
  const auto index = static_cast<std::size_t>(position + 0.5);
  return values[std::min(index, values.size() - 1U)];
}

void run_frame(World& world, SnapshotHistory& history, const RunConfig& config,
               std::uint32_t tick) {
  LB_FRAME("Frame");
  {
    LB_ZONE("Input");
    apply_frame_input(world, config, tick);
  }
  {
    LB_ZONE("Update");
    update_navigation(world);
    update_population(world, config, tick);
    update_component_queries(world, config, tick);
    update_transforms(world, tick);
    update_collisions(world, tick);
    update_interest_management(world, config, tick);
    produce_and_dispatch_events(world, config, tick);
    finalize_frame(world, tick);
  }
  {
    LB_ZONE("Checkpoint");
    if (config.history_capacity != 0U) {
      history.record(world, tick);
      const bool should_rollback =
          config.rollback_period != 0U && tick >= config.rollback_depth &&
          tick % config.rollback_period == config.rollback_period - 1U;
      if (should_rollback) {
        const std::uint32_t target_tick = tick - config.rollback_depth;
        if (!history.restore(world, target_tick)) {
          throw std::runtime_error("rollback target is no longer in the history ring");
        }
        const std::uint64_t restored_hash = hash_dynamic_state(world);
        world.rollback_digest = mix_digest(
            world.rollback_digest,
            restored_hash ^ (static_cast<std::uint64_t>(target_tick) << 32U) ^ tick);
      }
    }
  }
  world.tick = tick + 1U;
  LB_COUNTER("Units", static_cast<std::int64_t>(world.units.size()));
  LB_COUNTER("GridRevision", static_cast<std::int64_t>(world.grid.revision));
  LB_COUNTER("HistoryBytes", static_cast<std::int64_t>(history.retained_bytes()));
  LB_COUNTER("Transforms", static_cast<std::int64_t>(world.transforms.size()));
  LB_COUNTER("CollisionPairs",
             static_cast<std::int64_t>(world.collision_pair_count));
  LB_COUNTER("Events", static_cast<std::int64_t>(config.events_per_frame));
  LB_COUNTER("QueryMatches", static_cast<std::int64_t>(world.query_match_count));
  LB_COUNTER("InterestVisible",
             static_cast<std::int64_t>(world.interest_visible_count));
}

}  // namespace

RunResult run_game(const RunConfig& config) {
  profile::Session trace_session(config.trace_path);
  LB_RUN_METADATA(LONGBENCH_SOURCE_HASH);
  World world = make_world(config);
  SnapshotHistory history(std::max<std::uint32_t>(1U, config.history_capacity));

  std::uint32_t tick = 0;
  for (; tick < config.warmup_frames; ++tick) {
    run_frame(world, history, config, tick);
  }

  std::vector<std::uint64_t> frame_ns;
  frame_ns.reserve(config.measured_frames);
  const auto measurement_start = Clock::now();
  for (std::uint32_t frame = 0; frame < config.measured_frames; ++frame, ++tick) {
    const auto frame_start = Clock::now();
    run_frame(world, history, config, tick);
    const auto frame_end = Clock::now();
    frame_ns.push_back(static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(frame_end - frame_start)
            .count()));
  }
  const auto measurement_end = Clock::now();

  RunResult result;
  result.checksum = hash_world(world);
  result.route_digest = world.route_digest;
  result.rollback_digest = world.rollback_digest;
  result.transform_digest = world.transform_digest;
  result.collision_digest = world.collision_digest;
  result.event_digest = world.event_digest;
  result.query_digest = world.query_digest;
  result.interest_digest = world.interest_digest;
  result.collision_pair_count = world.collision_pair_count;
  result.query_match_count = world.query_match_count;
  result.interest_visible_count = world.interest_visible_count;
  result.measured_ns = static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(measurement_end - measurement_start)
          .count());
  result.frame_p50_ns = percentile(frame_ns, 0.50);
  result.frame_p95_ns = percentile(frame_ns, 0.95);
  result.frame_p99_ns = percentile(frame_ns, 0.99);
  result.retained_history_bytes = history.retained_bytes();
  result.frames = config.measured_frames;
  result.units = static_cast<std::uint32_t>(world.units.size());
  result.transforms = static_cast<std::uint32_t>(world.transforms.size());
  result.colliders = static_cast<std::uint32_t>(world.colliders.size());
  return result;
}

}  // namespace longbench
