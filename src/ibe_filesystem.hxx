#pragma once

#if defined(__cplusplus) && __cplusplus >= 201703

#include <filesystem>

namespace ibe {
namespace fs {
using namespace std::filesystem;

constexpr file_type directory_file = file_type::directory;
constexpr file_type regular_file = file_type::regular;
}  // namespace fs
}  // namespace ibe

#elif defined(IBE_USE_BOOST)

#include <boost/filesystem>

namespace ibe {
namespace fs = boost::filesystem;
}  // namespace ibe

#else
#error "Could not find a filesystem library"
#endif
