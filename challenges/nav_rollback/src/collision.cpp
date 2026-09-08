#include "longbench/collision.hpp"

#include <cstdint>

namespace longbench {
namespace {

struct Bounds {
  std::int64_t min_x = 0;
  std::int64_t min_y = 0;
  std::int64_t max_x = 0;
  std::int64_t max_y = 0;
};

Bounds bounds_for(const World& world, const Collider& collider) {
  const TransformNode& transform = world.transforms[collider.transform];
  return Bounds{
      transform.world_x - collider.half_x,
      transform.world_y - collider.half_y,
      transform.world_x + collider.half_x,
      transform.world_y + collider.half_y,
  };
}

bool layers_interact(const Collider& left, const Collider& right) {
  return (left.mask & right.layer) != 0U &&
         (right.mask & left.layer) != 0U;
}

bool overlaps(const Bounds& left, const Bounds& right) {
  return left.min_x <= right.max_x && right.min_x <= left.max_x &&
         left.min_y <= right.max_y && right.min_y <= left.max_y;
}

}  // namespace

std::uint64_t update_collisions(World& world, std::uint32_t tick) {
  std::uint64_t frame_digest = mix_digest(world.seed ^ 0xc0111deULL, tick);
  std::uint64_t pair_count = 0;
  for (std::uint32_t left = 0; left < world.colliders.size(); ++left) {
    const Collider& left_collider = world.colliders[left];
    const Bounds left_bounds = bounds_for(world, left_collider);
    for (std::uint32_t right = left + 1U; right < world.colliders.size();
         ++right) {
      const Collider& right_collider = world.colliders[right];
      if (!layers_interact(left_collider, right_collider) ||
          !overlaps(left_bounds, bounds_for(world, right_collider))) {
        continue;
      }
      const std::uint64_t pair =
          (static_cast<std::uint64_t>(left) << 32U) | right;
      frame_digest = mix_digest(frame_digest, pair);
      ++pair_count;
    }
  }
  frame_digest = mix_digest(frame_digest, pair_count);
  world.collision_digest = mix_digest(world.collision_digest, frame_digest);
  world.collision_pair_count = pair_count;
  return pair_count;
}

}  // namespace longbench
