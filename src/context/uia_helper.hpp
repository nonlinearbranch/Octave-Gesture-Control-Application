#pragma once

#include <string>

#ifdef _WIN32
#include <windows.h>
#endif

namespace spider::context::uia {

#ifdef _WIN32
std::string get_browser_domain(HWND hwnd);
#else
std::string get_browser_domain(void* hwnd = nullptr);
#endif

}  // namespace spider::context::uia
