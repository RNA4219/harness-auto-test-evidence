use std::fmt;

#[derive(Debug)]
pub struct CommandFailure {
    pub code: u8,
    pub diagnostic: String,
}

impl fmt::Display for CommandFailure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.diagnostic)
    }
}
impl std::error::Error for CommandFailure {}
