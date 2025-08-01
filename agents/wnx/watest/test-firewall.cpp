// watest.cpp : This file contains the 'main' function. Program execution begins
// and ends there.
//
#include "pch.h"

#include "tools/_misc.h"
#include "wnx/firewall.h"
#include "wnx/logger.h"
#include "wnx/on_start.h"

namespace cma::fw {

namespace {
constexpr std::wstring_view g_rule_name{L"test_CMK_rule"};
constexpr std::wstring_view g_rule_name_bad{L"test_CMK_rule_"};
const std::wstring g_app_name_base =
    std::wstring(L"%ProgramFiles%") + L"\\checkmk\\service\\check_mk_agent.exe";
const std::wstring g_app_name_canonical =
    tools::win::GetEnv(L"ProgramFiles") +
    L"\\checkmk\\service\\check_mk_agent.exe";
const std::wstring g_app_name_canonical_bad =
    tools::win::GetEnv(L"ProgramFiles") +
    L"\\checkmk\\service\\check_mk_agent.exe_";
}  // namespace

TEST(FirewallApi, PolicyCtor) {
    Policy policy;
    ASSERT_TRUE(policy.getRules() != nullptr);
    ASSERT_GE(policy.getRulesCount(), 10);
    ASSERT_NE(policy.getCurrentProfileTypes(), -1);
}

class FirewallApiFixture : public ::testing::Test {
    void SetUp() override { reset(); }

    void TearDown() override { reset(); }

    void reset() const {
        RemoveRule(g_rule_name);  // to be sure that no rules are
        RemoveRule(
            g_rule_name);  // Windows can create many rules with same name
    }
};

TEST_F(FirewallApiFixture, BaseComponent) {
    ASSERT_FALSE(FindRule(g_rule_name));
    EXPECT_EQ(CountRules(g_rule_name, L""), 0);
    ASSERT_TRUE(CreateInboundRule(g_rule_name, g_app_name_base, 9999));
    EXPECT_EQ(CountRules(g_rule_name, L""), 1);
    EXPECT_EQ(CountRules(g_rule_name, g_app_name_canonical), 1)
        << "Rule " << g_rule_name.data() << " for "
        << g_app_name_canonical.data() << "not found/1";
    EXPECT_EQ(CountRules(g_rule_name, g_app_name_canonical_bad), 0);
    ASSERT_NE(FindRule(g_rule_name), nullptr);
    EXPECT_FALSE(FindRule(g_rule_name_bad));

    auto rule = FindRule(g_rule_name, g_app_name_canonical);
    ASSERT_NE(rule, nullptr) << "Rule " << g_rule_name.data() << " for "
                             << g_app_name_canonical.data() << "not found/2";

    long types = 0;
    rule->get_Profiles(&types);
    EXPECT_EQ(types, NET_FW_PROFILE2_DOMAIN | NET_FW_PROFILE2_PRIVATE |
                         NET_FW_PROFILE2_PUBLIC);

    EXPECT_FALSE(FindRule(g_rule_name, g_app_name_canonical_bad));

    ASSERT_FALSE(RemoveRule(g_rule_name, g_app_name_canonical_bad));
    ASSERT_TRUE(RemoveRule(g_rule_name, g_app_name_canonical));
    EXPECT_EQ(CountRules(g_rule_name, g_app_name_canonical), 0);
    EXPECT_FALSE(FindRule(g_rule_name));
}

}  // namespace cma::fw
