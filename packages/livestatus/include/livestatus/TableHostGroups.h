// Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the
// terms and conditions defined in the file COPYING, which is part of this
// source code package.

#ifndef TableHostGroups_h
#define TableHostGroups_h

#include <string>

#include "livestatus/Row.h"
#include "livestatus/Table.h"
class ColumnOffsets;
class ICore;
class Query;
class User;

class TableHostGroups : public Table {
public:
    explicit TableHostGroups(ICore *mc);

    [[nodiscard]] std::string name() const override;
    [[nodiscard]] std::string namePrefix() const override;
    void answerQuery(Query &query, const User &user) override;
    [[nodiscard]] Row get(const std::string &primary_key) const override;

    static void addColumns(Table *table, const std::string &prefix,
                           const ColumnOffsets &offsets);
};

#endif  // TableHostGroups_h
