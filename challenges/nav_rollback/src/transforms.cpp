#include "longbench/transforms.hpp"

#include <algorithm>
#include <cstdint>

namespace longbench {
namespace {

constexpr std::int64_t kFixedScale = 1024;

void compose(TransformNode& node, const TransformNode& parent) {
  const std::int64_t local_a = node.local_a;
  const std::int64_t local_b = node.local_b;
  const std::int64_t local_c = node.local_c;
  const std::int64_t local_d = node.local_d;
  node.world_a =
      (parent.world_a * local_a + parent.world_c * local_b) / kFixedScale;
  node.world_b =
      (parent.world_b * local_a + parent.world_d * local_b) / kFixedScale;
  node.world_c =
      (parent.world_a * local_c + parent.world_c * local_d) / kFixedScale;
  node.world_d =
      (parent.world_b * local_c + parent.world_d * local_d) / kFixedScale;
  node.world_x = parent.world_x +
      (parent.world_a * node.local_x + parent.world_c * node.local_y) /
          kFixedScale;
  node.world_y = parent.world_y +
      (parent.world_b * node.local_x + parent.world_d * node.local_y) /
          kFixedScale;
}

void copy_local_to_world(TransformNode& node) {
  node.world_a = node.local_a;
  node.world_b = node.local_b;
  node.world_c = node.local_c;
  node.world_d = node.local_d;
  node.world_x = node.local_x;
  node.world_y = node.local_y;
}

}  // namespace

void update_transforms(World& world, std::uint32_t tick) {
  for (TransformNode& node : world.transforms) {
    if (node.parent == kNoParent) {
      copy_local_to_world(node);
    } else {
      compose(node, world.transforms[node.parent]);
    }
  }

  const std::uint32_t samples = std::min<std::uint32_t>(
      32U, static_cast<std::uint32_t>(world.transforms.size()));
  std::uint64_t frame_digest = mix_digest(world.seed, tick);
  for (std::uint32_t sample = 0; sample < samples; ++sample) {
    const TransformNode& node = world.transforms[
        (static_cast<std::uint64_t>(tick) * 131U + sample * 997U) %
        world.transforms.size()];
    frame_digest = mix_digest(frame_digest, node.id);
    frame_digest = mix_digest(frame_digest, node.parent);
    frame_digest = mix_digest(frame_digest,
                              static_cast<std::uint64_t>(node.world_a));
    frame_digest = mix_digest(frame_digest,
                              static_cast<std::uint64_t>(node.world_d));
    frame_digest = mix_digest(frame_digest,
                              static_cast<std::uint64_t>(node.world_x));
    frame_digest = mix_digest(frame_digest,
                              static_cast<std::uint64_t>(node.world_y));
  }
  world.transform_digest = mix_digest(world.transform_digest, frame_digest);
}

}  // namespace longbench
