#pragma once

// Local headers
#include "Access.hxx"
#include "ibe_filesystem.hxx"

// Standard library
#include <string>
#include <vector>

namespace ibe {
void check_access(const fs::path& path, Access const& access);

// Return a directory listing obtained from the file system metadata database.
std::vector<std::string> const get_dir_entries(const fs::path& diskpath,
                                               const fs::path& path,
                                               Access const& access);
}  // namespace ibe
