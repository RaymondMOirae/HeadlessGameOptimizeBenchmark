#include <charconv>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>

#include "longbench/config.hpp"
#include "longbench/main_loop.hpp"

namespace {

template <typename T>
T parse_integer(std::string_view text, const char* option) {
  T value{};
  const auto [end, error] =
      std::from_chars(text.data(), text.data() + text.size(), value);
  if (error != std::errc{} || end != text.data() + text.size()) {
    throw std::runtime_error(std::string("invalid value for ") + option);
  }
  return value;
}

std::string next_value(int& index, int argc, char** argv, const char* option) {
  if (index + 1 >= argc) {
    throw std::runtime_error(std::string("missing value for ") + option);
  }
  return argv[++index];
}

void apply_scenario(longbench::RunConfig& config, const std::string& scenario) {
  config.scenario = scenario;
  if (scenario == "mixed") {
    return;
  }
  if (scenario == "raid") {
    config.units = 12000;
    config.navigators = 420;
    config.grid_width = config.grid_height = 46;
    config.goals = 5;
    config.warmup_frames = 3;
    config.measured_frames = 28;
    config.history_capacity = 16;
    config.rollback_period = 13;
    config.rollback_depth = 7;
    config.edit_period = 9;
    config.edits_per_period = 2;
    config.mutations_per_frame = 160;
    config.transforms = 3000;
    config.colliders = 500;
    config.events_per_frame = 1200;
    config.transform_mutations_per_frame = 8;
    config.reparent_period = 19;
    config.component_queries = 4;
    config.structural_changes_per_frame = 40;
    config.interest_observers = 8;
    config.interest_radius = 4;
    config.interest_movements_per_frame = 30;
    return;
  }
  if (scenario == "history") {
    config.units = 120000;
    config.navigators = 24;
    config.grid_width = config.grid_height = 34;
    config.goals = 4;
    config.warmup_frames = 3;
    config.measured_frames = 56;
    config.history_capacity = 32;
    config.rollback_period = 9;
    config.rollback_depth = 6;
    config.edit_period = 14;
    config.edits_per_period = 1;
    config.mutations_per_frame = 320;
    config.transforms = 40000;
    config.colliders = 300;
    config.events_per_frame = 1000;
    config.transform_mutations_per_frame = 64;
    config.reparent_period = 13;
    config.component_queries = 2;
    config.structural_changes_per_frame = 200;
    config.interest_observers = 4;
    config.interest_radius = 3;
    config.interest_movements_per_frame = 80;
    return;
  }
  if (scenario == "churn") {
    config.units = 30000;
    config.navigators = 240;
    config.grid_width = config.grid_height = 42;
    config.goals = 12;
    config.warmup_frames = 3;
    config.measured_frames = 36;
    config.history_capacity = 20;
    config.rollback_period = 10;
    config.rollback_depth = 5;
    config.edit_period = 2;
    config.edits_per_period = 4;
    config.mutations_per_frame = 500;
    config.transforms = 12000;
    config.colliders = 1400;
    config.events_per_frame = 5000;
    config.transform_mutations_per_frame = 80;
    config.reparent_period = 3;
    config.component_queries = 20;
    config.structural_changes_per_frame = 1200;
    config.interest_observers = 40;
    config.interest_radius = 6;
    config.interest_movements_per_frame = 900;
    return;
  }
  if (scenario == "scene") {
    config.units = 12000;
    config.navigators = 20;
    config.grid_width = config.grid_height = 32;
    config.goals = 4;
    config.warmup_frames = 3;
    config.measured_frames = 22;
    config.history_capacity = 16;
    config.rollback_period = 9;
    config.rollback_depth = 5;
    config.edit_period = 11;
    config.edits_per_period = 1;
    config.mutations_per_frame = 80;
    config.transforms = 60000;
    config.colliders = 5500;
    config.events_per_frame = 1500;
    config.transform_mutations_per_frame = 35;
    config.reparent_period = 7;
    config.component_queries = 3;
    config.structural_changes_per_frame = 60;
    config.interest_observers = 10;
    config.interest_radius = 4;
    config.interest_movements_per_frame = 40;
    return;
  }
  if (scenario == "events") {
    config.units = 30000;
    config.navigators = 8;
    config.grid_width = config.grid_height = 24;
    config.goals = 3;
    config.warmup_frames = 3;
    config.measured_frames = 28;
    config.history_capacity = 18;
    config.rollback_period = 10;
    config.rollback_depth = 6;
    config.edit_period = 15;
    config.edits_per_period = 1;
    config.mutations_per_frame = 120;
    config.transforms = 3000;
    config.colliders = 300;
    config.events_per_frame = 35000;
    config.transform_mutations_per_frame = 5;
    config.reparent_period = 23;
    config.component_queries = 2;
    config.structural_changes_per_frame = 80;
    config.interest_observers = 4;
    config.interest_radius = 3;
    config.interest_movements_per_frame = 50;
    return;
  }
  if (scenario == "ecs") {
    config.units = 140000;
    config.navigators = 0;
    config.grid_width = config.grid_height = 48;
    config.goals = 3;
    config.warmup_frames = 3;
    config.measured_frames = 28;
    config.history_capacity = 0;
    config.rollback_period = 0;
    config.rollback_depth = 0;
    config.edit_period = 0;
    config.edits_per_period = 0;
    config.mutations_per_frame = 120;
    config.transforms = 100;
    config.colliders = 0;
    config.events_per_frame = 0;
    config.transform_mutations_per_frame = 0;
    config.reparent_period = 0;
    config.component_queries = 44;
    config.structural_changes_per_frame = 1600;
    config.interest_observers = 0;
    config.interest_radius = 0;
    config.interest_movements_per_frame = 0;
    return;
  }
  if (scenario == "interest") {
    config.units = 90000;
    config.navigators = 40;
    config.grid_width = config.grid_height = 72;
    config.goals = 5;
    config.warmup_frames = 3;
    config.measured_frames = 22;
    config.history_capacity = 18;
    config.rollback_period = 9;
    config.rollback_depth = 5;
    config.edit_period = 13;
    config.edits_per_period = 1;
    config.mutations_per_frame = 120;
    config.transforms = 200;
    config.colliders = 0;
    config.events_per_frame = 200;
    config.transform_mutations_per_frame = 0;
    config.reparent_period = 0;
    config.component_queries = 2;
    config.structural_changes_per_frame = 600;
    config.interest_observers = 80;
    config.interest_radius = 7;
    config.interest_movements_per_frame = 2400;
    return;
  }
  throw std::runtime_error("unknown scenario: " + scenario);
}

void print_help() {
  std::cout
      << "longbench [options]\n"
      << "  --scenario mixed|raid|history|churn|scene|events|ecs|interest\n"
      << "  --seed N --units N --navigators N --grid-width N --grid-height N\n"
      << "  --goals N --warmup N --frames N --history-capacity N\n"
      << "  --rollback-period N --rollback-depth N --edit-period N\n"
      << "  --edits N --mutations N --transforms N --colliders N\n"
      << "  --events N --transform-mutations N --reparent-period N\n"
      << "  --component-queries N --structural-changes N\n"
      << "  --interest-observers N --interest-radius N --interest-movements N\n"
      << "  --trace FILE --output FILE --quiet\n";
}

std::string result_json(const longbench::RunConfig& config,
                        const longbench::RunResult& result) {
  return "{\n"
         "  \"schema\": \"longbench.run.v3\",\n"
         "  \"scenario\": \"" + config.scenario + "\",\n"
         "  \"seed\": " + std::to_string(config.seed) + ",\n"
         "  \"units\": " + std::to_string(result.units) + ",\n"
         "  \"navigators\": " + std::to_string(config.navigators) + ",\n"
         "  \"frames\": " + std::to_string(result.frames) + ",\n"
         "  \"checksum\": \"" + std::to_string(result.checksum) + "\",\n"
         "  \"route_digest\": \"" + std::to_string(result.route_digest) + "\",\n"
         "  \"rollback_digest\": \"" + std::to_string(result.rollback_digest) + "\",\n"
         "  \"transform_digest\": \"" + std::to_string(result.transform_digest) + "\",\n"
         "  \"collision_digest\": \"" + std::to_string(result.collision_digest) + "\",\n"
         "  \"event_digest\": \"" + std::to_string(result.event_digest) + "\",\n"
         "  \"query_digest\": \"" + std::to_string(result.query_digest) + "\",\n"
         "  \"interest_digest\": \"" + std::to_string(result.interest_digest) + "\",\n"
         "  \"collision_pair_count\": " +
             std::to_string(result.collision_pair_count) + ",\n"
         "  \"query_match_count\": " +
             std::to_string(result.query_match_count) + ",\n"
         "  \"interest_visible_count\": " +
             std::to_string(result.interest_visible_count) + ",\n"
         "  \"transforms\": " + std::to_string(result.transforms) + ",\n"
         "  \"colliders\": " + std::to_string(result.colliders) + ",\n"
         "  \"events_per_frame\": " +
             std::to_string(config.events_per_frame) + ",\n"
         "  \"component_queries\": " +
             std::to_string(config.component_queries) + ",\n"
         "  \"interest_observers\": " +
             std::to_string(config.interest_observers) + ",\n"
         "  \"measured_ns\": " + std::to_string(result.measured_ns) + ",\n"
         "  \"frame_p50_ns\": " + std::to_string(result.frame_p50_ns) + ",\n"
         "  \"frame_p95_ns\": " + std::to_string(result.frame_p95_ns) + ",\n"
         "  \"frame_p99_ns\": " + std::to_string(result.frame_p99_ns) + ",\n"
         "  \"retained_history_bytes\": " +
             std::to_string(result.retained_history_bytes) + "\n"
         "}";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    std::string scenario = "mixed";
    for (int i = 1; i < argc; ++i) {
      if (std::string_view(argv[i]) == "--scenario") {
        scenario = next_value(i, argc, argv, "--scenario");
      }
    }

    longbench::RunConfig config;
    apply_scenario(config, scenario);
    for (int i = 1; i < argc; ++i) {
      const std::string option = argv[i];
      if (option == "--help" || option == "-h") {
        print_help();
        return 0;
      }
      if (option == "--scenario") {
        ++i;
      } else if (option == "--seed") {
        config.seed = parse_integer<std::uint64_t>(next_value(i, argc, argv, "--seed"), "--seed");
      } else if (option == "--units") {
        config.units = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--units"), "--units");
      } else if (option == "--navigators") {
        config.navigators = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--navigators"), "--navigators");
      } else if (option == "--grid-width") {
        config.grid_width = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--grid-width"), "--grid-width");
      } else if (option == "--grid-height") {
        config.grid_height = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--grid-height"), "--grid-height");
      } else if (option == "--goals") {
        config.goals = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--goals"), "--goals");
      } else if (option == "--warmup") {
        config.warmup_frames = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--warmup"), "--warmup");
      } else if (option == "--frames") {
        config.measured_frames = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--frames"), "--frames");
      } else if (option == "--history-capacity") {
        config.history_capacity = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--history-capacity"), "--history-capacity");
      } else if (option == "--rollback-period") {
        config.rollback_period = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--rollback-period"), "--rollback-period");
      } else if (option == "--rollback-depth") {
        config.rollback_depth = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--rollback-depth"), "--rollback-depth");
      } else if (option == "--edit-period") {
        config.edit_period = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--edit-period"), "--edit-period");
      } else if (option == "--edits") {
        config.edits_per_period = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--edits"), "--edits");
      } else if (option == "--mutations") {
        config.mutations_per_frame = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--mutations"), "--mutations");
      } else if (option == "--transforms") {
        config.transforms = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--transforms"), "--transforms");
      } else if (option == "--colliders") {
        config.colliders = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--colliders"), "--colliders");
      } else if (option == "--events") {
        config.events_per_frame = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--events"), "--events");
      } else if (option == "--transform-mutations") {
        config.transform_mutations_per_frame = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--transform-mutations"), "--transform-mutations");
      } else if (option == "--reparent-period") {
        config.reparent_period = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--reparent-period"), "--reparent-period");
      } else if (option == "--component-queries") {
        config.component_queries = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--component-queries"), "--component-queries");
      } else if (option == "--structural-changes") {
        config.structural_changes_per_frame = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--structural-changes"), "--structural-changes");
      } else if (option == "--interest-observers") {
        config.interest_observers = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--interest-observers"), "--interest-observers");
      } else if (option == "--interest-radius") {
        config.interest_radius = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--interest-radius"), "--interest-radius");
      } else if (option == "--interest-movements") {
        config.interest_movements_per_frame = parse_integer<std::uint32_t>(next_value(i, argc, argv, "--interest-movements"), "--interest-movements");
      } else if (option == "--trace") {
        config.trace_path = next_value(i, argc, argv, "--trace");
      } else if (option == "--output") {
        config.result_path = next_value(i, argc, argv, "--output");
      } else if (option == "--quiet") {
        config.quiet = true;
      } else {
        throw std::runtime_error("unknown option: " + option);
      }
    }

    const std::uint64_t cells =
        static_cast<std::uint64_t>(config.grid_width) * config.grid_height;
    if (config.units == 0U || config.units > 500000U ||
        config.navigators > config.units || config.goals == 0U ||
        config.goals > cells || config.grid_width < 2U || config.grid_height < 2U ||
        config.grid_width > 512U || config.grid_height > 512U ||
        config.transforms == 0U || config.transforms > 500000U ||
        config.colliders > config.transforms || config.colliders > 30000U ||
        config.events_per_frame > 250000U ||
        config.component_queries > 128U ||
        config.structural_changes_per_frame > config.units ||
        config.interest_observers > config.units ||
        config.interest_radius > config.grid_width + config.grid_height ||
        config.interest_movements_per_frame > config.units ||
        config.transform_mutations_per_frame > config.transforms ||
        config.measured_frames == 0U ||
        (config.history_capacity == 0U &&
         (config.rollback_period != 0U || config.rollback_depth != 0U)) ||
        (config.history_capacity != 0U &&
         config.history_capacity <= config.rollback_depth)) {
      throw std::runtime_error("invalid or unsafe workload dimensions");
    }
    for (const std::string& path_text : {config.trace_path, config.result_path}) {
      if (!path_text.empty()) {
        const std::filesystem::path path(path_text);
        if (path.has_parent_path()) {
          std::filesystem::create_directories(path.parent_path());
        }
      }
    }

    const longbench::RunResult result = longbench::run_game(config);
    const std::string json = result_json(config, result);
    std::cout << json << '\n';
    if (!config.result_path.empty()) {
      std::ofstream output(config.result_path, std::ios::trunc);
      output << json << '\n';
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "longbench: " << error.what() << '\n';
    return 2;
  }
}
