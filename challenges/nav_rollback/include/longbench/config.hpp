#pragma once

#include <cstdint>
#include <string>

namespace longbench {

struct RunConfig {
  std::string scenario = "mixed";
  std::string trace_path;
  std::string result_path;
  std::uint64_t seed = 2027;
  std::uint32_t units = 60000;
  std::uint32_t navigators = 250;
  std::uint32_t grid_width = 44;
  std::uint32_t grid_height = 44;
  std::uint32_t goals = 6;
  std::uint32_t warmup_frames = 4;
  std::uint32_t measured_frames = 42;
  std::uint32_t history_capacity = 28;
  std::uint32_t rollback_period = 11;
  std::uint32_t rollback_depth = 7;
  std::uint32_t edit_period = 9;
  std::uint32_t edits_per_period = 3;
  std::uint32_t mutations_per_frame = 420;
  std::uint32_t transforms = 16000;
  std::uint32_t colliders = 2400;
  std::uint32_t events_per_frame = 10000;
  std::uint32_t transform_mutations_per_frame = 40;
  std::uint32_t reparent_period = 17;
  std::uint32_t component_queries = 12;
  std::uint32_t structural_changes_per_frame = 120;
  std::uint32_t interest_observers = 24;
  std::uint32_t interest_radius = 4;
  std::uint32_t interest_movements_per_frame = 90;
  bool quiet = false;
};

}  // namespace longbench
