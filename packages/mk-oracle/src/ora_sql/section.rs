// Copyright (C) 2023 Checkmk GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
// conditions defined in the file COPYING, which is part of this source code package.

use super::sqls::{self, find_known_query};
use crate::config::{self, section, section::names};
use crate::emit::header;
use crate::types::SectionName;
use crate::{constants, utils};
use anyhow::Result;
use std::collections::HashMap;
use std::fs::read_to_string;
use std::path::{Path, PathBuf};

#[derive(Debug, PartialEq)]
pub enum SectionKind {
    Sync,
    Async,
}

#[derive(Debug, Clone)]
pub struct Section {
    name: SectionName,
    sep: char,
    cache_age: Option<u32>,
    header_name: String,
}

impl Section {
    pub fn make_instance_section() -> Self {
        let config_section = config::section::SectionBuilder::new(section::names::INSTANCE).build();
        Self::new(&config_section, 0)
    }

    pub fn new(section: &config::section::Section, global_cache_age: u32) -> Self {
        let cache_age = if section.kind() == config::section::SectionKind::Async {
            Some(global_cache_age)
        } else {
            None
        };
        Self {
            name: section.name().clone(),
            sep: section.sep(),
            cache_age,
            header_name: section.name().clone().into(),
        }
    }

    pub fn to_plain_header(&self) -> String {
        header(&self.header_name, self.sep)
    }

    pub fn to_work_header(&self) -> String {
        header(
            &(self.header_name.clone() + &self.cached_header()),
            self.sep,
        )
    }

    fn cached_header(&self) -> String {
        self.cache_age
            .map(|age| {
                format!(
                    ":cached({},{})",
                    utils::get_utc_now().unwrap_or_default(),
                    age
                )
            })
            .unwrap_or_default()
    }

    pub fn name(&self) -> &SectionName {
        &self.name
    }

    pub fn header_name(&self) -> &str {
        &self.header_name
    }

    pub fn sep(&self) -> char {
        self.sep
    }

    pub fn kind(&self) -> &SectionKind {
        if self.cache_age.is_some() {
            &SectionKind::Async
        } else {
            &SectionKind::Sync
        }
    }

    pub fn cache_age(&self) -> u32 {
        self.cache_age.unwrap_or_default()
    }

    /// try to find the section's query in the sql directory for instance with the given version
    /// or in the known queries if custom sql query is not provided
    pub fn select_query(&self, sql_dir: Option<PathBuf>, instance_version: u32) -> Option<String> {
        match self.header_name.as_str() {
            names::IO_STATS => find_known_query(sqls::Id::IoStats).map(str::to_string).ok(),
            _ => self.find_query(sql_dir, instance_version),
        }
    }

    fn find_query(&self, sql_dir: Option<PathBuf>, instance_version: u32) -> Option<String> {
        self.find_provided_query(sql_dir, instance_version)
            .or_else(|| {
                get_sql_id(&self.header_name)
                    .and_then(Self::find_known_query)
                    .map(|s| s.to_owned())
            })
    }

    pub fn find_provided_query(
        &self,
        sql_dir: Option<PathBuf>,
        instance_version: u32,
    ) -> Option<String> {
        if let Some(dir) = sql_dir {
            if let Ok(versioned_files) = find_sql_files(&dir, &self.header_name) {
                for (min_version, sql_file) in versioned_files {
                    if instance_version >= min_version {
                        #[allow(clippy::all)]
                        return read_to_string(&sql_file)
                            .map_err(|e| {
                                log::error!("Can't read file {:?} {}", &sql_file, &e);
                                e
                            })
                            .ok();
                    }
                }
            };
        }
        None
    }
    fn find_known_query(id: sqls::Id) -> Option<&'static str> {
        sqls::find_known_query(id)
            .map_err(|e| {
                log::error!("{e}");
                e
            })
            .ok()
    }
}

fn find_sql_files(dir: &Path, section_name: &str) -> Result<Vec<(u32, PathBuf)>> {
    let mut paths: Vec<(u32, PathBuf)> = std::fs::read_dir(dir)?
        .filter_map(|res| res.ok())
        .map(|dir_entry| dir_entry.path())
        .filter_map(|path| {
            if path
                .extension()
                .is_some_and(|ext| ext == constants::SQL_QUERY_EXTENSION)
            {
                Some(path)
            } else {
                None
            }
        })
        .filter_map(|path| get_file_version(&path, section_name).map(|version| (version, path)))
        .collect::<Vec<_>>();
    paths.sort_by_key(|p| p.0);
    paths.reverse();
    Ok(paths)
}

fn get_file_version(path: &Path, section_name: &str) -> Option<u32> {
    if let Some(stem) = path.file_stem().map(|n| n.to_string_lossy().to_string()) {
        match stem.rsplitn(2, '@').collect::<Vec<&str>>().as_slice() {
            [min_version, name] => {
                if name.to_lowercase() == section_name.to_lowercase() {
                    return Some(min_version.parse::<u32>().unwrap_or(0));
                }
            }
            [stem] => {
                if stem.to_lowercase() == section_name.to_lowercase() {
                    return Some(0);
                }
            }
            _ => {}
        }
    }
    None
}

lazy_static::lazy_static! {
    static ref SECTION_MAP: HashMap<&'static str, sqls::Id> = HashMap::from([
        (names::IO_STATS, sqls::Id::IoStats),
    ]);
}

pub fn get_sql_id<T: AsRef<str>>(section_name: T) -> Option<sqls::Id> {
    SECTION_MAP.get(section_name.as_ref()).copied()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::section;

    #[test]
    fn test_section_header() {
        let section = Section::make_instance_section();
        assert_eq!(
            section.to_plain_header(),
            "<<<oracle_instance:sep(124)>>>\n"
        );
        assert_eq!(section.to_work_header(), "<<<oracle_instance:sep(124)>>>\n");

        let section = Section::new(
            &section::SectionBuilder::new("backup")
                .set_async(true)
                .build(),
            100,
        );
        assert_eq!(section.to_plain_header(), "<<<oracle_backup:sep(124)>>>\n");
        assert!(section
            .to_work_header()
            .starts_with("<<<oracle_backup:cached("));
        assert!(section.to_work_header().ends_with("100):sep(124)>>>\n"));

        let section = Section::new(&section::SectionBuilder::new("jobs").build(), 100);
        assert!(section
            .to_work_header()
            .starts_with("<<<oracle_jobs:cached("));
        let section = Section::new(
            &section::SectionBuilder::new("jobs")
                .set_async(false)
                .build(),
            100,
        );
        assert_eq!(section.to_work_header(), "<<<oracle_jobs:sep(124)>>>\n");
    }

    /// We test only few parameters
    #[test]
    fn test_get_ids() {
        assert_eq!(get_sql_id(names::IO_STATS).unwrap(), sqls::Id::IoStats);
        // TODO: add all..
        assert!(get_sql_id("").is_none());
    }
}
