//! Dashboard bans are checked for every login, including after server restarts.
pub fn is_banned(player: u128) -> bool {
    let path = ferrumc_general_purpose::paths::get_root_path().join("banned-players.json");
    match std::fs::read_to_string(path) {
        Ok(text) => match serde_json::from_str::<Vec<String>>(&text) {
            Ok(bans) => bans.iter().any(|id| uuid::Uuid::parse_str(id)
                .map(|id| id.as_u128() == player).unwrap_or(false)),
            Err(error) => { tracing::error!("Invalid ban list: {error}"); true }
        },
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => false,
        Err(error) => { tracing::error!("Cannot read ban list: {error}"); true }
    }
}
