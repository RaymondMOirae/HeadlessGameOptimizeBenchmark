#include "longbench/events.hpp"

#include <algorithm>
#include <cstdint>
#include <memory>
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

class QueuedEvent {
 public:
  QueuedEvent(std::uint32_t kind, std::uint32_t target, std::uint64_t value)
      : kind_(kind), target_(target), value_(value),
        payload_(16U + static_cast<std::size_t>(value % 48U)) {
    for (std::size_t index = 0; index < payload_.size(); ++index) {
      payload_[index] = static_cast<std::uint8_t>(
          (value >> ((index % 8U) * 8U)) ^ (index * 37U + kind));
    }
  }

  virtual ~QueuedEvent() = default;

  virtual void dispatch(World& world, std::uint64_t& frame_digest) const {
    Unit& unit = world.units[target_];
    std::uint64_t payload_digest = value_;
    for (std::uint8_t byte : payload_) {
      payload_digest = mix_digest(payload_digest, byte);
    }
    if (kind_ == 0U) {
      unit.health += static_cast<std::int32_t>(value_ % 5U) - 2;
      if (unit.health < -50 || unit.health > 180) {
        unit.health = 100;
      }
    } else if (kind_ == 1U) {
      unit.cooldown =
          (unit.cooldown + 1U + static_cast<std::uint32_t>(value_ & 7U)) % 31U;
      unit.energy -= static_cast<std::int32_t>((value_ >> 8U) & 3U);
    } else {
      unit.flags ^= static_cast<std::uint16_t>(value_ & 0x1fU);
      unit.inventory_digest = mix_digest(unit.inventory_digest, payload_digest);
    }
    frame_digest = mix_digest(
        frame_digest,
        payload_digest ^ (static_cast<std::uint64_t>(kind_) << 60U) ^ target_);
  }

 private:
  std::uint32_t kind_ = 0;
  std::uint32_t target_ = 0;
  std::uint64_t value_ = 0;
  std::vector<std::uint8_t> payload_;
};

}  // namespace

void produce_and_dispatch_events(World& world, const RunConfig& config,
                                 std::uint32_t tick) {
  const std::uint32_t count = std::min<std::uint32_t>(
      config.events_per_frame, static_cast<std::uint32_t>(world.units.size()) * 8U);
  std::vector<std::unique_ptr<QueuedEvent>> queue;
  for (std::uint32_t sequence = 0; sequence < count; ++sequence) {
    const std::uint64_t value = deterministic_value(
        world.seed ^ world.collision_pair_count ^ world.query_match_count ^
            (world.interest_visible_count << 1U), tick,
        0xe000ULL + static_cast<std::uint64_t>(sequence) * 29U);
    const std::uint32_t target =
        static_cast<std::uint32_t>(value % world.units.size());
    queue.push_back(std::make_unique<QueuedEvent>(
        static_cast<std::uint32_t>((value >> 17U) % 3U), target, value));
  }

  std::uint64_t frame_digest =
      mix_digest(world.seed ^ 0xe7e17ULL, static_cast<std::uint64_t>(tick) << 32U);
  for (const auto& event : queue) {
    event->dispatch(world, frame_digest);
  }
  world.event_digest = mix_digest(world.event_digest,
                                  mix_digest(frame_digest, queue.size()));
}

}  // namespace longbench
