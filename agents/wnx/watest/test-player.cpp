// test-player.cpp

//
#include "pch.h"

#include <chrono>
#include <filesystem>

#include "carrier.h"
#include "cfg.h"
#include "cfg_details.h"
#include "cma_core.h"
#include "common/cfg_info.h"
#include "common/mailslot_transport.h"
#include "common/wtools.h"
#include "player.h"
#include "read_file.h"
#include "test_tools.h"
#include "tools/_misc.h"
#include "tools/_process.h"

namespace cma::player {  // to become friendly for wtools classes
TEST(PlayerTest, Pipe) {
    auto p = new wtools::SimplePipe();
    EXPECT_TRUE(p->getRead() == 0);
    EXPECT_TRUE(p->getWrite() == 0);
    p->create();
    EXPECT_TRUE(p->getRead() != 0);
    EXPECT_TRUE(p->getWrite() != 0);

    auto p2 = new wtools::SimplePipe();
    EXPECT_TRUE(p2->getRead() == 0);
    EXPECT_TRUE(p2->getWrite() == 0);
    p2->create();
    EXPECT_TRUE(p2->getRead() != 0);
    EXPECT_TRUE(p2->getWrite() != 0);
    delete p;
    delete p2;
}

TEST(PlayerTest, ConfigFolders) {
    using namespace cma::cfg;
    using namespace wtools;
    cma::OnStart(cma::AppType::test);
    {
        std::string s = "$BUILTIN_AGENT_PATH$\\";
        auto result = cma::cfg::ReplacePredefinedMarkers(s);
        EXPECT_EQ(result, ToUtf8(GetSystemPluginsDir()) + "\\");
    }

    {
        std::string s = "$BUILTIN_PLUGINS_PATH$\\";
        auto result = cma::cfg::ReplacePredefinedMarkers(s);
        EXPECT_EQ(result, ToUtf8(GetSystemPluginsDir()) + "\\");
    }

    {
        std::string s = "$CUSTOM_PLUGINS_PATH$\\";
        auto result = cma::cfg::ReplacePredefinedMarkers(s);
        EXPECT_EQ(result, ToUtf8(GetUserPluginsDir()) + "\\");
    }

    {
        std::string s = "user\\";
        auto result = cma::cfg::ReplacePredefinedMarkers(s);
        EXPECT_EQ(result, s);
    }
}

static void CreateFileInTemp(const std::filesystem::path &filename) {
    std::ofstream ofs(wtools::ToStr(filename));

    if (!ofs) {
        XLOG::l("Can't open file {} error {}", filename, GetLastError());
        return;
    }

    ofs << wtools::ToStr(filename) << std::endl;
}

constexpr const char *SecondLine = "0, 1, 2, 3, 4, 5, 6, 7, 8";

static void CreatePluginInTemp(const std::filesystem::path &filename,
                               int timeout, std::string &plugin_name) {
    std::ofstream ofs(wtools::ToStr(filename));

    if (!ofs) {
        XLOG::l("Can't open file {} error {}", filename, GetLastError());
        return;
    }

    ofs << "@echo off\n"
        //<< "timeout /T " << timeout << " /NOBREAK > nul\n"
        << "powershell Start-Sleep " << timeout << " \n"
        << "@echo ^<^<^<" << plugin_name << "^>^>^>\n"
        << "@echo " << SecondLine << "\n";
}

static void RemoveFolder(const std::filesystem::path &Path) {
    namespace fs = std::filesystem;
    fs::path top = Path;
    fs::path dir_path;

    cma::PathVector directories;
    std::error_code ec;
    for (auto &p : fs::recursive_directory_iterator(top, ec)) {
        dir_path = p.path();
        if (fs::is_directory(dir_path)) {
            directories.push_back(fs::canonical(dir_path));
        }
    }

    for (auto rit = directories.rbegin(); rit != directories.rend(); ++rit) {
        if (fs::is_empty(*rit)) {
            fs::remove(*rit);
        }
    }

    fs::remove_all(Path);
}

// returns folder where
static cma::PathVector GetFolderStructure() {
    using namespace cma::cfg;
    namespace fs = std::filesystem;
    fs::path tmp = cma::cfg::GetTempDir();
    if (!fs::exists(tmp) || !fs::is_directory(tmp) ||
        wtools::ToStr(tmp).find("\\tmp") == 0 ||
        wtools::ToStr(tmp).find("\\tmp") == std::string::npos) {
        XLOG::l(XLOG::kStdio)("Cant create folder structure {} {} {}",
                              fs::exists(tmp), fs::is_directory(tmp),
                              wtools::ToStr(tmp).find("\\tmp"));
        return {};
    }
    PathVector pv;
    for (auto &folder : {"a", "b", "c"}) {
        auto dir = tmp / folder;
        pv.emplace_back(dir);
    }
    return pv;
}

TEST(PlayerTest, All) {
    using namespace std::chrono;

    std::vector<std::wstring> exe;
    auto unit_test_path = tst::GetUnitTestFilesRoot();
    exe.push_back(unit_test_path / L"a.exe");
    exe.push_back(unit_test_path / L"b.cmd");
    exe.push_back(unit_test_path / L"B.cmd");
    int expected = 0;
    exe.push_back(unit_test_path / L"test_plugin.cmd");
    expected++;
    exe.push_back(unit_test_path / L"tESt_plugin.cmd");
    exe.push_back(unit_test_path / L"TEst_plugin2.bat");
    expected++;
    exe.push_back(unit_test_path / L"debug_print.exe");
    exe.push_back(unit_test_path);
    expected = 3;

    auto test_plugin_output = cma::tools::ReadFileInVector(
        (unit_test_path / L"test_plugin.output").wstring().c_str());
    EXPECT_TRUE(test_plugin_output);
    if (test_plugin_output) EXPECT_EQ(test_plugin_output->size(), 36);

    auto test_plugin2_output = cma::tools::ReadFileInVector(
        (unit_test_path / L"test_plugin2.output").wstring().c_str());
    EXPECT_TRUE(test_plugin2_output);
    if (test_plugin2_output) EXPECT_EQ(test_plugin2_output->size(), 56);

    auto summary_output = cma::tools::ReadFileInVector(
        (unit_test_path / L"summary.output").wstring().c_str());
    EXPECT_TRUE(summary_output);
    if (summary_output) EXPECT_EQ(summary_output->size(), 92);

    cma::player::TheBox box;
    auto x = box.start(L"id", exe);
    box.waitForAllProcesses(10000ms, true);

    std::vector<char> accu;
    int count = 0;

    bool test_size_ok = false;
    bool test_content_ok = false;
    bool test2_size_ok = false;
    bool test2_content_ok = false;
    box.processResults([&](const std::wstring &CmdLine, uint32_t Pid,
                           uint32_t Code, const std::vector<char> &Data) {
        auto data = Data;
        if (data.size() == test_plugin_output->size()) {
            test_size_ok = true;
            test_content_ok =
                0 ==
                memcmp(data.data(), test_plugin_output->data(), data.size());
        } else if (data.size() == test_plugin2_output->size()) {
            test2_size_ok = true;
            test2_content_ok =
                0 ==
                memcmp(data.data(), test_plugin2_output->data(), data.size());
        }

        cma::tools::AddVector(accu, data);
        count++;
    });

    EXPECT_EQ(3, count);
    EXPECT_TRUE(test_size_ok);
    EXPECT_TRUE(test_content_ok);
    EXPECT_TRUE(test2_size_ok);
    EXPECT_TRUE(test2_content_ok);

    EXPECT_TRUE(x == expected);
    EXPECT_TRUE(box.id_ == L"id");
    EXPECT_TRUE(box.processes_.size() == 3);
}

TEST(PlayerTest, RealLifeInventory_Long) {
    using namespace std::chrono;
    using namespace std;
    using namespace cma::cfg;
    namespace fs = std::filesystem;

    const wstring plugin = L"mk_inventory.vbs";
    const wstring plugin_state_file = L"mk_inventory.local";

    error_code ec;
    vector<wstring> exe;
    auto plugin_path = GetCfg().getSystemPluginsDir();
    ASSERT_TRUE(fs::exists(plugin_path, ec));

    auto data_path = GetCfg().getDataDir();
    ASSERT_TRUE(fs::exists(data_path, ec));

    exe.push_back((plugin_path.lexically_normal() / plugin).wstring());
    {
        cma::player::TheBox box;
        EXPECT_TRUE(box.exec_array_.empty());
        box.tryAddToExecArray(exe[0]);
        EXPECT_TRUE(box.exec_array_.size() == 1);
        EXPECT_TRUE(box.exec_array_[0].find(plugin) != wstring::npos);
    }

    // folder prepare
    auto fs_state_path = GetCfg().getStateDir();
    auto state_path = wtools::ToStr(fs_state_path);
    ASSERT_TRUE(!state_path.empty());

    // delete all file in folder
    std::filesystem::remove_all(state_path, ec);  // no exception here
    std::filesystem::create_directory(state_path, ec);

    auto result =
        tools::win::SetEnv(std::string{envs::kMkStateDirName}, state_path);
    player::TheBox box;
    auto x = box.start(L"id", exe);
    box.waitForAllProcesses(20000ms, true);

    vector<char> accu;
    int count = 0;

    box.processResults([&](const std::wstring cmd_line, uint32_t pid,
                           uint32_t code, const std::vector<char> &result) {
        // we check for the UNICODE output(see msdn 0xFFFE, -xFEFF etc.)
        bool convert_required = result[0] == '\xFF' && result[1] == '\xFE';

        std::string data;
        if (convert_required) {
            auto raw_data =
                reinterpret_cast<const wchar_t *>(result.data() + 2);
            wstring wdata(raw_data, raw_data + (result.size() - 2) / 2);
            if (wdata.back() != 0) wdata += L'\0';
            data = wtools::ToUtf8(wdata);
        } else {
            data.assign(result.begin(), result.end());
        }

        if (data.back() != 0) data += '\0';
        XLOG::d("Process [{}]\t pid [{}]\t code [{}]\n---\n{}\n---\n",
                wtools::ToUtf8(cmd_line), pid, code, data.data());

        cma::tools::AddVector(accu, data);
        count++;
    });

    EXPECT_EQ(1, count);
    EXPECT_GE(accu.size(), static_cast<size_t>(3000));
    EXPECT_TRUE(accu[0] == '<' && accu[1] == '<');
    EXPECT_TRUE(fs::exists(fs_state_path / plugin_state_file))
        << fs_state_path / plugin_state_file
        << " was not found on disk after processing finished. Check plugin itself";
}

}  // namespace cma::player
