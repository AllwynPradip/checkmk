// Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
// conditions defined in the file COPYING, which is part of this source code package.

use crate::config::defines::defaults::DEFAULT_SEP;
use derive_more::{Display, From, Into};

#[derive(PartialEq, PartialOrd, Debug, Clone, From, Into)]
pub struct Port(pub u16);

impl Port {
    pub fn value(&self) -> u16 {
        self.0
    }
}

impl std::fmt::Display for Port {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.value())
    }
}

#[derive(PartialEq, From, Into, Debug, Clone)]
pub struct MaxConnections(pub u32);

#[derive(PartialEq, From, Debug, Clone)]
pub struct MaxQueries(pub u32);

#[derive(PartialEq, Debug, Display, Clone, Default, Into, Hash, Eq)]
pub struct InstanceName(String);

impl From<&str> for InstanceName {
    fn from(s: &str) -> Self {
        Self(s.to_string().to_uppercase())
    }
}

impl From<&String> for InstanceName {
    fn from(s: &String) -> Self {
        Self(s.clone().to_uppercase())
    }
}

#[derive(PartialEq, From, Debug, Display, Clone, Default, Into, Hash, Eq)]
pub struct ServiceName(String);

impl From<&str> for ServiceName {
    fn from(s: &str) -> Self {
        Self(s.to_string())
    }
}

#[derive(PartialEq, From, Clone, Debug, Display)]
pub struct ServiceType(String);
impl From<&str> for ServiceType {
    fn from(s: &str) -> Self {
        Self(s.to_string())
    }
}

#[derive(PartialEq, From, Clone, Debug, Display, Default)]
pub struct InstanceId(String);

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct InstanceEdition(String);

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct InstanceVersion(String);

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct InstanceCluster(String);

// used once, may be removed in the future
impl<'a> From<&'a InstanceCluster> for &'a str {
    fn from(instance_cluster: &'a InstanceCluster) -> &'a str {
        instance_cluster.0.as_str()
    }
}

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct ComputerName(String);

// used once, may be removed in the future
impl<'a> From<&'a ComputerName> for &'a str {
    fn from(computer_name: &'a ComputerName) -> &'a str {
        computer_name.0.as_str()
    }
}

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct ConfigHash(String);

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into, Hash, Eq)]
pub struct PiggybackHostName(String);

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct InstanceAlias(String);

#[derive(PartialEq, From, Clone, Debug, Display, Default, Into)]
pub struct HostName(String);

#[derive(PartialEq, From, Clone, Debug, Display, Hash, Eq, Into)]
pub struct SectionName(String);

impl SectionName {
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Debug)]
pub struct Credentials {
    pub user: String,
    pub password: String,
}

#[derive(Debug, Clone, PartialEq, Eq, From)]
pub enum Separator {
    No,
    Comma,
    Decorated(char),
}

impl Default for Separator {
    fn default() -> Self {
        Separator::Decorated(DEFAULT_SEP)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, From)]
pub struct SqlQuery {
    text: String,
    separator: Separator,
}
impl SqlQuery {
    pub fn new<T: AsRef<str> + Sized>(s: T, separator: Separator) -> Self {
        match separator {
            Separator::No => Self {
                text: s.as_ref().to_owned(),
                separator: crate::types::Separator::No,
            },
            Separator::Comma => Self {
                text: use_sep(s.as_ref(), ","),
                separator: Separator::Comma,
            },
            Separator::Decorated(c) => Self {
                text: use_sep(s, format!("|| '{}' ||", c).as_str()),
                separator: Separator::Decorated(c),
            },
        }
    }

    pub fn as_str(&self) -> &str {
        &self.text
    }

    pub fn sep(&self) -> Option<char> {
        match &self.separator {
            Separator::No => None,
            Separator::Comma => None,
            Separator::Decorated(c) => Some(*c),
        }
    }
}
fn use_sep<T: AsRef<str>>(s: T, sep: &str) -> String {
    s.as_ref().replace("{sep}", sep)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_instance_name() {
        assert_eq!(&InstanceName::from("teST").to_string(), "TEST");
    }

    #[test]
    fn test_sql_query() {
        assert_eq!(
            SqlQuery::new("a {sep} b", Separator::No).as_str(),
            "a {sep} b"
        );
        assert_eq!(
            SqlQuery::new("a {sep} b", Separator::Comma).as_str(),
            "a , b"
        );
        assert_eq!(
            SqlQuery::new("a {sep} b", Separator::default()).as_str(),
            "a || '|' || b"
        );
        assert_eq!(
            SqlQuery::new("a {sep} b", Separator::Decorated('x')).as_str(),
            "a || 'x' || b"
        );
    }

    #[test]
    fn test_make_query() {
        const QUERY: &str = "a{sep}b{sep}c";
        assert_eq!(use_sep(QUERY, ","), "a,b,c");
    }
}
