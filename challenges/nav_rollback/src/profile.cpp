#include "longbench/profile.hpp"

#include <fstream>
#include <mutex>
#include <vector>

#if LONGBENCH_ENABLE_PERFETTO
#include <perfetto.h>

PERFETTO_TRACK_EVENT_STATIC_STORAGE();
#endif

namespace longbench::profile {

struct Session::Impl {
  bool active = false;
  std::string output_path;
#if LONGBENCH_ENABLE_PERFETTO
  std::unique_ptr<perfetto::TracingSession> tracing_session;
#endif
};

Session::Session(const std::string& output_path) : impl_(std::make_unique<Impl>()) {
  impl_->output_path = output_path;
  if (output_path.empty()) {
    return;
  }
#if LONGBENCH_ENABLE_PERFETTO
  static std::once_flag initialized;
  std::call_once(initialized, [] {
    perfetto::TracingInitArgs args;
    args.backends = perfetto::kInProcessBackend;
    perfetto::Tracing::Initialize(args);
    perfetto::TrackEvent::Register();
  });

  perfetto::TraceConfig config;
  config.add_buffers()->set_size_kb(32 * 1024);
  auto* data_source = config.add_data_sources()->mutable_config();
  data_source->set_name("track_event");
  perfetto::protos::gen::TrackEventConfig track_config;
  track_config.add_disabled_categories("*");
  track_config.add_enabled_categories("longbench.frame");
  track_config.add_enabled_categories("longbench.system");
  track_config.add_enabled_categories("longbench.counter");
  data_source->set_track_event_config_raw(track_config.SerializeAsString());

  impl_->tracing_session = perfetto::Tracing::NewTrace();
  impl_->tracing_session->Setup(config);
  impl_->tracing_session->StartBlocking();
  impl_->active = true;
#endif
}

Session::~Session() {
#if LONGBENCH_ENABLE_PERFETTO
  if (!impl_ || !impl_->active || !impl_->tracing_session) {
    return;
  }
  perfetto::TrackEvent::Flush();
  impl_->tracing_session->StopBlocking();
  std::vector<char> data(impl_->tracing_session->ReadTraceBlocking());
  std::ofstream output(impl_->output_path, std::ios::binary | std::ios::trunc);
  if (!data.empty()) {
    output.write(data.data(), static_cast<std::streamsize>(data.size()));
  }
#endif
}

}  // namespace longbench::profile
