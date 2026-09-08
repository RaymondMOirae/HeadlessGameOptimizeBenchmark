#pragma once

#include <memory>
#include <string>

#include "longbench/trace_categories.hpp"

namespace longbench::profile {

class Session {
 public:
  explicit Session(const std::string& output_path);
  ~Session();
  Session(const Session&) = delete;
  Session& operator=(const Session&) = delete;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace longbench::profile

#if LONGBENCH_ENABLE_PERFETTO
#define LB_ZONE(name) TRACE_EVENT("longbench.system", name)
#define LB_FRAME(name) TRACE_EVENT("longbench.frame", name)
#define LB_COUNTER(name, value) TRACE_COUNTER("longbench.counter", name, value)
#define LB_RUN_METADATA(value) \
  TRACE_EVENT_INSTANT("longbench.counter", "RunMetadata", "source_hash", value)
#else
#define LB_ZONE(name) do { (void)sizeof(name); } while (false)
#define LB_FRAME(name) do { (void)sizeof(name); } while (false)
#define LB_COUNTER(name, value) do { (void)sizeof(name); (void)(value); } while (false)
#define LB_RUN_METADATA(value) do { (void)sizeof(value); } while (false)
#endif
