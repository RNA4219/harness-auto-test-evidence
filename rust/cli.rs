use anyhow::{Result, anyhow};
use bigdecimal::num_bigint::BigInt;
use clap::{Arg, ArgAction, ArgMatches, Command};
use serde::Deserialize;
use serde_json::{Map, Value, json};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};

#[derive(Deserialize)]
pub struct Node {
    pub name: String,
    help: String,
    #[serde(default)]
    children: Vec<Node>,
    #[serde(default)]
    args: Vec<OptionSpec>,
    pub route: Option<Route>,
}

#[derive(Deserialize)]
struct OptionSpec {
    name: String,
    help: String,
    #[serde(default)]
    flags: Vec<String>,
    #[serde(default)]
    kind: String,
    #[serde(default)]
    choices: Vec<String>,
    #[serde(default)]
    required: bool,
    #[serde(default)]
    default: Value,
}

#[derive(Deserialize)]
pub struct Route {
    pub owner: String,
    pub contract: String,
    pub directory_output: bool,
    pub paths: BTreeMap<String, String>,
}

pub struct Invocation<'a> {
    pub command: String,
    pub values: Map<String, Value>,
    pub route: Option<&'a Route>,
}

impl Invocation<'_> {
    pub fn integer(&self, name: &str) -> Result<BigInt> {
        Ok(self.values[name].to_string().parse()?)
    }
    pub fn path(&self, name: &str) -> &Path {
        Path::new(
            self.values[name]
                .as_str()
                .expect("required path in CLI contract"),
        )
    }
    pub fn optional_path(&self, name: &str) -> Option<PathBuf> {
        self.values.get(name)?.as_str().map(PathBuf::from)
    }
}

impl Node {
    pub fn load() -> Self {
        serde_json::from_str(include_str!("commands.json")).expect("valid CLI contract")
    }

    pub fn parser(&self) -> Command {
        let mut cmd = Command::new(&self.name)
            .about(&self.help)
            .disable_help_subcommand(true)
            .args_override_self(true);
        if !self.children.is_empty() {
            cmd = cmd.subcommand_required(true);
            for child in &self.children {
                cmd = cmd.subcommand(child.parser());
            }
        }
        for spec in &self.args {
            let mut arg = Arg::new(&spec.name)
                .long(&spec.flags[0])
                .help(&spec.help)
                .required(spec.required);
            for alias in &spec.flags[1..] {
                arg = arg.visible_alias(alias);
            }
            if !spec.choices.is_empty() {
                arg = arg.value_parser(clap::builder::PossibleValuesParser::new(
                    spec.choices.clone(),
                ));
            }
            arg = match spec.kind.as_str() {
                "flag" => arg.action(ArgAction::SetTrue),
                "array" => arg.action(ArgAction::Append),
                "int" => arg
                    .allow_negative_numbers(true)
                    .value_parser(|s: &str| s.trim().parse::<BigInt>()),
                _ => arg,
            };
            cmd = cmd.arg(arg);
        }
        cmd
    }

    pub fn parse<'a>(&'a self, matches: &ArgMatches) -> Result<Invocation<'a>> {
        let (mut node, mut args) = (self, matches);
        let mut names = Vec::new();
        while let Some((name, child)) = args.subcommand() {
            node = node
                .children
                .iter()
                .find(|n| n.name == name)
                .ok_or_else(|| anyhow!("unknown command: {name}"))?;
            names.push(name);
            args = child;
        }
        let mut values = Map::new();
        for spec in &node.args {
            let name = &spec.name;
            let value = match spec.kind.as_str() {
                "flag" => Some(json!(args.get_flag(name))),
                "array" => args
                    .get_many::<String>(name)
                    .map(|v| json!(v.collect::<Vec<_>>())),
                "int" => args
                    .get_one::<BigInt>(name)
                    .map(|v| v.to_string().parse::<Value>())
                    .transpose()?,
                _ => args.get_one::<String>(name).map(|v| json!(v)),
            }
            .unwrap_or_else(|| spec.default.clone());
            let value = if spec.kind == "path"
                && let Some(raw) = value.as_str()
            {
                let mut normalized = PathBuf::new();
                for part in Path::new(raw).components() {
                    if part != std::path::Component::CurDir {
                        normalized.push(part.as_os_str());
                    }
                }
                if normalized.as_os_str().is_empty() {
                    normalized.push(".");
                }
                json!(normalized)
            } else {
                value
            };
            values.insert(name.clone(), value);
        }
        Ok(Invocation {
            command: names.join(" "),
            values,
            route: node.route.as_ref(),
        })
    }
}
