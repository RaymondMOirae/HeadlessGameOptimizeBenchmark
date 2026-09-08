#include "longbench/component_queries.hpp"

#include <algorithm>
#include <cstdint>
#include <vector>

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

struct QuerySpec {
  std::uint16_t required = 0;
  std::uint16_t excluded = 0;
  std::uint32_t operation = 0;
};

QuerySpec make_query(std::uint64_t seed, std::uint32_t tick,
                     std::uint32_t sequence) {
  const std::uint64_t value = deterministic_value(
      seed ^ 0xc0a9e17ULL, tick / 3U,
      0x7100ULL + static_cast<std::uint64_t>(sequence) * 43U);
  const std::uint32_t first = static_cast<std::uint32_t>(value & 7U);
  std::uint32_t second = static_cast<std::uint32_t>((value >> 11U) & 7U);
  if (second == first) {
    second = (second + 3U) & 7U;
  }
  std::uint32_t third = static_cast<std::uint32_t>((value >> 21U) & 7U);
  while (third == first || third == second) {
    third = (third + 1U) & 7U;
  }
  std::uint32_t excluded = static_cast<std::uint32_t>((value >> 31U) & 7U);
  while (excluded == first || excluded == second || excluded == third) {
    excluded = (excluded + 1U) & 7U;
  }
  QuerySpec spec;
  spec.required = static_cast<std::uint16_t>(
      (1U << first) | (1U << second) | (1U << third));
  spec.excluded = static_cast<std::uint16_t>(1U << excluded);
  spec.operation = static_cast<std::uint32_t>((value >> 43U) % 3U);
  return spec;
}

}  // namespace

void update_component_queries(World& world, const RunConfig& config,
                              std::uint32_t tick) {
  if (config.component_queries == 0U || world.units.empty()) {
    world.query_match_count = 0;
    return;
  }

  std::uint64_t frame_digest = mix_digest(world.seed ^ 0xc0a9e17ULL, tick);
  std::uint64_t total_matches = 0;
  for (std::uint32_t sequence = 0; sequence < config.component_queries;
       ++sequence) {
    const QuerySpec query = make_query(world.seed, tick, sequence);
    std::vector<std::uint32_t> matches;
    for (std::uint32_t index = 0; index < world.units.size(); ++index) {
      const std::uint16_t mask = world.units[index].component_mask;
      if ((mask & query.required) == query.required &&
          (mask & query.excluded) == 0U) {
        matches.push_back(index);
      }
    }

    std::uint64_t query_digest = mix_digest(
        query.required, static_cast<std::uint64_t>(query.excluded) << 16U);
    for (std::uint32_t index : matches) {
      Unit& unit = world.units[index];
      const std::uint64_t value =
          deterministic_value(world.seed ^ unit.id, tick,
                              0x7900ULL + sequence * 131ULL);
      if (query.operation == 0U) {
        unit.energy -= static_cast<std::int32_t>(value & 3U);
        if (unit.energy < -2000) {
          unit.energy = 1200;
        }
      } else if (query.operation == 1U) {
        unit.cooldown =
            (unit.cooldown + 1U + static_cast<std::uint32_t>(value & 1U)) % 31U;
      } else {
        unit.behavior_state = mix_digest(unit.behavior_state,
                                         value ^ sequence);
      }
      query_digest = mix_digest(
          query_digest,
          (static_cast<std::uint64_t>(index) << 32U) ^ unit.cooldown ^
              static_cast<std::uint32_t>(unit.energy));
    }
    total_matches += matches.size();
    frame_digest = mix_digest(
        frame_digest, mix_digest(query_digest, matches.size()));
  }
  world.query_match_count = total_matches;
  world.query_digest = mix_digest(world.query_digest, frame_digest);
}

}  // namespace longbench
