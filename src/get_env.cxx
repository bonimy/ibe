#include "get_env.hxx"

namespace ibe {
namespace {
std::string const get_env(char const* name) {
    char const* value = std::getenv(name);
    return value ? std::string(value) : std::string();
}
}  // namespace
}  // namespace ibe
