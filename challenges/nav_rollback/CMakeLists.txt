cmake_minimum_required(VERSION 3.20)

project(nav_rollback_longbench VERSION 0.1.0 LANGUAGES CXX)

option(LONGBENCH_ENABLE_PERFETTO "Build with the Perfetto tracing SDK" OFF)
option(LONGBENCH_WARNINGS_AS_ERRORS "Treat project warnings as errors" OFF)
set(LONGBENCH_SOURCE_HASH "untracked" CACHE STRING
    "Logic source hash embedded into profile metadata")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_library(longbench_core
    src/collision.cpp
    src/component_queries.cpp
    src/events.cpp
    src/history.cpp
    src/interest.cpp
    src/main_loop.cpp
    src/navigation.cpp
    src/profile.cpp
    src/systems.cpp
    src/transforms.cpp
    src/world.cpp)

target_include_directories(longbench_core PUBLIC include)
target_link_libraries(longbench_core PUBLIC Threads::Threads)
target_compile_definitions(longbench_core PUBLIC
    LONGBENCH_SOURCE_HASH="${LONGBENCH_SOURCE_HASH}")

if(MSVC)
  target_compile_options(longbench_core PRIVATE /W4 /permissive-)
  if(LONGBENCH_WARNINGS_AS_ERRORS)
    target_compile_options(longbench_core PRIVATE /WX)
  endif()
else()
  target_compile_options(longbench_core PRIVATE -Wall -Wextra -Wpedantic)
  if(LONGBENCH_WARNINGS_AS_ERRORS)
    target_compile_options(longbench_core PRIVATE -Werror)
  endif()
endif()

if(LONGBENCH_ENABLE_PERFETTO)
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/third_party/perfetto/perfetto.cc")
    set(PERFETTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/perfetto")
  elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/perfetto/perfetto.cc")
    set(PERFETTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/perfetto")
  else()
    message(FATAL_ERROR "Perfetto SDK missing from challenge workspace")
  endif()

  add_library(perfetto_sdk STATIC "${PERFETTO_DIR}/perfetto.cc")
  target_include_directories(perfetto_sdk PUBLIC "${PERFETTO_DIR}")
  target_link_libraries(perfetto_sdk PUBLIC Threads::Threads)
  target_compile_definitions(perfetto_sdk PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
  if(MSVC)
    target_compile_options(perfetto_sdk PRIVATE /bigobj /permissive-)
  elseif(WIN32)
    target_compile_options(perfetto_sdk PRIVATE -Wa,-mbig-obj)
  endif()
  if(WIN32)
    target_link_libraries(perfetto_sdk PUBLIC ws2_32)
  endif()
  target_compile_definitions(longbench_core PUBLIC LONGBENCH_ENABLE_PERFETTO=1)
  target_link_libraries(longbench_core PUBLIC perfetto_sdk)
else()
  target_compile_definitions(longbench_core PUBLIC LONGBENCH_ENABLE_PERFETTO=0)
endif()

add_executable(longbench src/main.cpp)
target_link_libraries(longbench PRIVATE longbench_core)

install(TARGETS longbench RUNTIME DESTINATION bin)
