//! Bounded dashboard commands enter the real ECS command pipeline on the tick thread.
use axum::{extract::{Path, State}, http::StatusCode, routing::{get, post}, Json, Router};
use bevy_ecs::world::World;
use ferrumc_commands::{infrastructure, messages::{CommandDispatched, ResolvedCommandDispatched},
    CommandContext, CommandInput, Sender};
use ferrumc_state::GlobalState;
use serde::Deserialize;
use serde_json::{json, Value};
use std::{collections::VecDeque, sync::{LazyLock, Mutex, mpsc}, time::{Duration, Instant}};

static COMMANDS: LazyLock<(mpsc::SyncSender<String>, Mutex<mpsc::Receiver<String>>)> =
    LazyLock::new(|| { let (tx, rx) = mpsc::sync_channel(32); (tx, Mutex::new(rx)) });
static TICKS: LazyLock<Mutex<VecDeque<(Instant, f64)>>> = LazyLock::new(|| Mutex::new(VecDeque::new()));

pub fn record_tick(duration: Duration) {
    let now = Instant::now();
    let mut ticks = TICKS.lock().unwrap();
    ticks.push_back((now, duration.as_secs_f64() * 1000.0));
    while ticks.len() > 600 || ticks.front().is_some_and(|(time, _)| now.duration_since(*time).as_secs() > 5) {
        ticks.pop_front();
    }
}

pub fn tick_metrics() -> (f64, f64) {
    let ticks = TICKS.lock().unwrap();
    let recent: Vec<_> = ticks.iter().filter(|(time, _)| time.elapsed().as_secs_f64() <= 1.5).collect();
    if recent.len() < 2 { return (0.0, 0.0); }
    let span = recent.last().unwrap().0.duration_since(recent[0].0).as_secs_f64();
    let tps = ((recent.len() - 1) as f64 / span.max(0.001))
        .min(ferrumc_config::server_config::get_global_config().tps as f64);
    let mspt = recent.iter().map(|(_, ms)| ms).sum::<f64>() / recent.len() as f64;
    (tps, mspt)
}

pub fn dispatch_one(world: &mut World, state: GlobalState) {
    let Ok(input) = COMMANDS.1.lock().unwrap().try_recv() else { return; };
    tracing::info!("[Dashboard] > {input}");
    match input.as_str() {
        "help" => { tracing::info!("Commands: help, list, save, {}", infrastructure::command_names().join(", ")); return; }
        "list" => { tracing::info!("Players: {}", state.players.player_list.iter().map(|p| p.value().1.clone()).collect::<Vec<_>>().join(", ")); return; }
        "save" => { match state.world.sync() {
            Ok(_) => tracing::info!("World saved successfully"),
            Err(error) => tracing::error!("Could not save world: {error}")
        } return; }
        _ => {}
    }
    let Some(command) = infrastructure::find_command(&input) else {
        tracing::warn!("Unknown command: {input}"); return;
    };
    let sender = Sender::Server;
    let ctx = CommandContext {
        input: CommandInput::of(input.strip_prefix(command.name).unwrap_or(&input).trim_start().into()),
        command: command.clone(), sender, state,
    };
    world.write_message(CommandDispatched { command: input, sender });
    world.write_message(ResolvedCommandDispatched { command, ctx, sender });
}

#[derive(Deserialize)]
struct CommandRequest { command: String }

async fn command(Json(body): Json<CommandRequest>) -> Result<Json<Value>, (StatusCode, String)> {
    let input = body.command.trim().trim_start_matches('/');
    // The upstream parser indexes byte strings; reject non-ASCII rather than risk a panic.
    if input.is_empty() || input.len() > 1024 || !input.is_ascii() || input.chars().any(char::is_control) {
        return Err((StatusCode::BAD_REQUEST, "Use a single ASCII command, up to 1024 characters".into()));
    }
    if !["help", "list", "save"].contains(&input) && infrastructure::find_command(input).is_none() {
        return Err((StatusCode::BAD_REQUEST, "Unknown command. Use help to list available commands.".into()));
    }
    COMMANDS.0.try_send(input.into()).map_err(|_| (StatusCode::TOO_MANY_REQUESTS, "Command queue full".into()))?;
    Ok(Json(json!({"queued": true})))
}

async fn players(State(state): State<GlobalState>) -> Json<Value> {
    let players: Vec<_> = state.players.player_list.iter().map(|p| json!({
        "uuid": uuid::Uuid::from_u128(p.value().0).to_string(), "name": p.value().1
    })).collect();
    Json(json!(players))
}

#[derive(Deserialize)]
struct KickRequest { reason: String }

async fn kick(State(state): State<GlobalState>, Path(id): Path<String>, Json(body): Json<KickRequest>)
    -> Result<Json<Value>, (StatusCode, String)> {
    let id = uuid::Uuid::parse_str(&id).map_err(|_| (StatusCode::BAD_REQUEST, "Invalid UUID".into()))?;
    if body.reason.len() > 256 { return Err((StatusCode::BAD_REQUEST, "Reason too long".into())); }
    let entity = state.players.player_list.iter().find(|p| p.value().0 == id.as_u128()).map(|p| *p.key());
    let Some(entity) = entity else { return Err((StatusCode::NOT_FOUND, "Player is no longer online".into())); };
    state.players.disconnect(entity, Some(body.reason));
    Ok(Json(json!({"ok":true})))
}

async fn whitelist(Json(ids): Json<Vec<String>>) -> Result<Json<Value>, (StatusCode, String)> {
    let parsed = ids.iter().map(|id| uuid::Uuid::parse_str(id)).collect::<Result<Vec<_>, _>>()
        .map_err(|_| (StatusCode::BAD_REQUEST, "Invalid whitelist UUID".into()))?;
    let list = ferrumc_config::whitelist::get_whitelist();
    list.clear();
    for id in parsed { list.insert(id.as_u128()); }
    Ok(Json(json!({"ok":true})))
}

pub fn router(state: GlobalState) -> Router {
    Router::new().route("/command", post(command)).route("/players", get(players))
        .route("/players/{id}/kick", post(kick)).route("/whitelist", post(whitelist)).with_state(state)
}
