#include "context/uia_helper.hpp"

#include <algorithm>
#include <cctype>
#include <mutex>
#include <string>
#include <utility>

#ifdef _WIN32
#include <OleAuto.h>
#include <UIAutomation.h>
#endif

namespace spider::context::uia {

#ifdef _WIN32
namespace {

struct AutomationCache {
    HWND cached_hwnd_ = nullptr;
    IUIAutomationValuePattern* cached_pattern_ = nullptr;
    IUIAutomation* automation_ = nullptr;

    ~AutomationCache() {
        if (cached_pattern_ != nullptr) {
            cached_pattern_->Release();
            cached_pattern_ = nullptr;
        }
        if (automation_ != nullptr) {
            automation_->Release();
            automation_ = nullptr;
        }
    }
};

std::mutex& cache_mutex() {
    static std::mutex mutex;
    return mutex;
}

AutomationCache& cache() {
    static AutomationCache instance;
    return instance;
}

void clear_cached_pattern(AutomationCache& state) {
    if (state.cached_pattern_ != nullptr) {
        state.cached_pattern_->Release();
        state.cached_pattern_ = nullptr;
    }
    state.cached_hwnd_ = nullptr;
}

std::string normalize_lower(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
    return value;
}

std::string trim_copy(std::string value) {
    const auto not_space = [](unsigned char ch) {
        return !std::isspace(ch);
    };
    value.erase(value.begin(), std::find_if(value.begin(), value.end(), not_space));
    value.erase(std::find_if(value.rbegin(), value.rend(), not_space).base(), value.end());
    return value;
}

std::string bstr_to_utf8(BSTR value) {
    if (value == nullptr) {
        return {};
    }
    const int required = WideCharToMultiByte(
        CP_UTF8,
        0,
        value,
        -1,
        nullptr,
        0,
        nullptr,
        nullptr);
    if (required <= 1) {
        return {};
    }
    std::string result(static_cast<std::size_t>(required), '\0');
    WideCharToMultiByte(
        CP_UTF8,
        0,
        value,
        -1,
        result.data(),
        required,
        nullptr,
        nullptr);
    if (!result.empty() && result.back() == '\0') {
        result.pop_back();
    }
    return result;
}

std::string extract_domain(std::string url) {
    url = normalize_lower(trim_copy(std::move(url)));
    if (url.empty()) {
        return {};
    }

    const auto protocol = url.find("://");
    if (protocol != std::string::npos) {
        url.erase(0, protocol + 3);
    }

    const auto at = url.rfind('@');
    if (at != std::string::npos) {
        url.erase(0, at + 1);
    }

    const auto slash = url.find_first_of("/?#");
    if (slash != std::string::npos) {
        url.erase(slash);
    }

    const auto port = url.find(':');
    if (port != std::string::npos) {
        url.erase(port);
    }

    if (url.rfind("www.", 0) == 0) {
        url.erase(0, 4);
    }

    return url;
}

IUIAutomation* get_automation() {
    AutomationCache& state = cache();
    if (state.automation_ != nullptr) {
        return state.automation_;
    }

    IUIAutomation* automation = nullptr;
    const HRESULT hr = CoCreateInstance(
        __uuidof(CUIAutomation),
        nullptr,
        CLSCTX_INPROC_SERVER,
        IID_PPV_ARGS(&automation));
    if (FAILED(hr) || automation == nullptr) {
        return nullptr;
    }

    state.automation_ = automation;
    return state.automation_;
}

IUIAutomationCondition* create_edit_and_automation_id_condition(
    IUIAutomation* automation,
    const wchar_t* automation_id) {
    if (automation == nullptr || automation_id == nullptr) {
        return nullptr;
    }

    VARIANT edit_variant{};
    edit_variant.vt = VT_I4;
    edit_variant.lVal = UIA_EditControlTypeId;

    IUIAutomationCondition* edit_condition = nullptr;
    if (FAILED(automation->CreatePropertyCondition(UIA_ControlTypePropertyId, edit_variant, &edit_condition))) {
        return nullptr;
    }

    VARIANT id_variant{};
    id_variant.vt = VT_BSTR;
    id_variant.bstrVal = SysAllocString(automation_id);

    IUIAutomationCondition* id_condition = nullptr;
    const HRESULT id_hr =
        automation->CreatePropertyCondition(UIA_AutomationIdPropertyId, id_variant, &id_condition);
    SysFreeString(id_variant.bstrVal);
    if (FAILED(id_hr) || id_condition == nullptr) {
        edit_condition->Release();
        return nullptr;
    }

    IUIAutomationCondition* combined = nullptr;
    const HRESULT and_hr = automation->CreateAndCondition(edit_condition, id_condition, &combined);
    edit_condition->Release();
    id_condition->Release();
    if (FAILED(and_hr)) {
        return nullptr;
    }
    return combined;
}

IUIAutomationCondition* create_edit_and_name_condition(
    IUIAutomation* automation,
    const wchar_t* name_value) {
    if (automation == nullptr || name_value == nullptr) {
        return nullptr;
    }

    VARIANT edit_variant{};
    edit_variant.vt = VT_I4;
    edit_variant.lVal = UIA_EditControlTypeId;

    IUIAutomationCondition* edit_condition = nullptr;
    if (FAILED(automation->CreatePropertyCondition(UIA_ControlTypePropertyId, edit_variant, &edit_condition))) {
        return nullptr;
    }

    VARIANT name_variant{};
    name_variant.vt = VT_BSTR;
    name_variant.bstrVal = SysAllocString(name_value);

    IUIAutomationCondition* name_condition = nullptr;
    const HRESULT name_hr =
        automation->CreatePropertyCondition(UIA_NamePropertyId, name_variant, &name_condition);
    SysFreeString(name_variant.bstrVal);
    if (FAILED(name_hr) || name_condition == nullptr) {
        edit_condition->Release();
        return nullptr;
    }

    IUIAutomationCondition* combined = nullptr;
    const HRESULT and_hr = automation->CreateAndCondition(edit_condition, name_condition, &combined);
    edit_condition->Release();
    name_condition->Release();
    if (FAILED(and_hr)) {
        return nullptr;
    }
    return combined;
}

IUIAutomationValuePattern* find_value_pattern(
    IUIAutomation* automation,
    IUIAutomationElement* root,
    IUIAutomationCondition* condition) {
    if (automation == nullptr || root == nullptr || condition == nullptr) {
        return nullptr;
    }

    IUIAutomationElement* element = nullptr;
    const HRESULT find_hr = root->FindFirst(TreeScope_Descendants, condition, &element);
    if (FAILED(find_hr) || element == nullptr) {
        return nullptr;
    }

    IUIAutomationValuePattern* pattern = nullptr;
    const HRESULT pattern_hr =
        element->GetCurrentPatternAs(UIA_ValuePatternId, IID_PPV_ARGS(&pattern));
    element->Release();
    if (FAILED(pattern_hr)) {
        return nullptr;
    }
    return pattern;
}

std::string read_domain_from_pattern(IUIAutomationValuePattern* pattern) {
    if (pattern == nullptr) {
        return {};
    }

    BSTR value = nullptr;
    const HRESULT hr = pattern->get_CurrentValue(&value);
    if (FAILED(hr) || value == nullptr) {
        if (value != nullptr) {
            SysFreeString(value);
        }
        return {};
    }

    std::string domain = extract_domain(bstr_to_utf8(value));
    SysFreeString(value);
    return domain;
}

}  // namespace

std::string get_browser_domain(HWND hwnd) {
    if (hwnd == nullptr) {
        return {};
    }

    std::lock_guard<std::mutex> lock(cache_mutex());
    AutomationCache& state = cache();

    if (state.cached_hwnd_ == hwnd && state.cached_pattern_ != nullptr) {
        std::string cached_domain = read_domain_from_pattern(state.cached_pattern_);
        if (!cached_domain.empty()) {
            return cached_domain;
        }
        clear_cached_pattern(state);
    }

    IUIAutomation* automation = get_automation();
    if (automation == nullptr) {
        return {};
    }

    IUIAutomationElement* root = nullptr;
    const HRESULT root_hr = automation->ElementFromHandle(hwnd, &root);
    if (FAILED(root_hr) || root == nullptr) {
        return {};
    }

    IUIAutomationValuePattern* pattern = nullptr;

    IUIAutomationCondition* condition = create_edit_and_automation_id_condition(automation, L"urlBar");
    if (condition != nullptr) {
        pattern = find_value_pattern(automation, root, condition);
        condition->Release();
    }

    if (pattern == nullptr) {
        condition = create_edit_and_name_condition(automation, L"Address and search bar");
        if (condition != nullptr) {
            pattern = find_value_pattern(automation, root, condition);
            condition->Release();
        }
    }

    if (pattern == nullptr) {
        condition = create_edit_and_name_condition(automation, L"Address");
        if (condition != nullptr) {
            pattern = find_value_pattern(automation, root, condition);
            condition->Release();
        }
    }

    if (pattern == nullptr) {
        condition = create_edit_and_automation_id_condition(automation, L"urlbar-input");
        if (condition != nullptr) {
            pattern = find_value_pattern(automation, root, condition);
            condition->Release();
        }
    }

    root->Release();
    if (pattern == nullptr) {
        return {};
    }

    std::string domain = read_domain_from_pattern(pattern);
    if (domain.empty()) {
        pattern->Release();
        return {};
    }

    clear_cached_pattern(state);
    state.cached_hwnd_ = hwnd;
    state.cached_pattern_ = pattern;
    return domain;
}

#else

std::string get_browser_domain(void*) {
    return {};
}

#endif

}  // namespace spider::context::uia
