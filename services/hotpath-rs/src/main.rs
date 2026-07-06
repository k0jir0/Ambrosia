use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tracing::{error, info};

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "camelCase")]
enum Command {
    NewOrder {
        order_id: String,
        symbol: String,
        side: String,
        quantity: u64,
        price: f64,
        max_notional_usd: f64,
        reference_price: Option<f64>,
        max_slippage_bps: Option<f64>,
        strategy_origin: Option<String>,
    },
    KillSwitch { enabled: bool },
    Health,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct Response {
    status: String,
    accepted: bool,
    reason: String,
    order_id: Option<String>,
}

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("HOTPATH_LOG")
                .unwrap_or_else(|_| "ambrosia_hotpath=info,tokio=warn".to_string()),
        )
        .with_target(false)
        .compact()
        .init();

    let bind_addr = std::env::var("HOTPATH_BIND").unwrap_or_else(|_| "127.0.0.1:9100".to_string());
    let listener = TcpListener::bind(&bind_addr).await?;
    let kill_switch = Arc::new(AtomicBool::new(false));

    info!("hot path listening on {}", bind_addr);

    loop {
        let (socket, peer) = listener.accept().await?;
        let kill_switch = Arc::clone(&kill_switch);
        tokio::spawn(async move {
            if let Err(err) = handle_connection(socket, kill_switch).await {
                error!("connection {} failed: {}", peer, err);
            }
        });
    }
}

async fn handle_connection(socket: TcpStream, kill_switch: Arc<AtomicBool>) -> Result<()> {
    let (reader, mut writer) = socket.into_split();
    let mut lines = BufReader::new(reader).lines();

    while let Some(line) = lines.next_line().await? {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }

        let response = match serde_json::from_str::<Command>(line) {
            Ok(command) => handle_command(command, &kill_switch),
            Err(err) => Response {
                status: "error".to_string(),
                accepted: false,
                reason: format!("invalid_command: {}", err),
                order_id: None,
            },
        };

        let encoded = serde_json::to_string(&response)?;
        writer.write_all(encoded.as_bytes()).await?;
        writer.write_all(b"\n").await?;
        writer.flush().await?;
    }

    Ok(())
}

fn handle_command(command: Command, kill_switch: &Arc<AtomicBool>) -> Response {
    match command {
        Command::KillSwitch { enabled } => {
            kill_switch.store(enabled, Ordering::Relaxed);
            Response {
                status: "ok".to_string(),
                accepted: true,
                reason: if enabled {
                    "kill_switch_enabled".to_string()
                } else {
                    "kill_switch_disabled".to_string()
                },
                order_id: None,
            }
        }
        Command::Health => Response {
            status: "ok".to_string(),
            accepted: true,
            reason: if kill_switch.load(Ordering::Relaxed) {
                "degraded_kill_switch_active".to_string()
            } else {
                "healthy".to_string()
            },
            order_id: None,
        },
        Command::NewOrder {
            order_id,
            symbol,
            side,
            quantity,
            price,
            max_notional_usd,
            reference_price,
            max_slippage_bps,
            strategy_origin,
        } => {
            if kill_switch.load(Ordering::Relaxed) {
                return Response {
                    status: "rejected".to_string(),
                    accepted: false,
                    reason: "kill_switch_active".to_string(),
                    order_id: Some(order_id),
                };
            }

            if quantity == 0 || !price.is_finite() || price <= 0.0 {
                return Response {
                    status: "rejected".to_string(),
                    accepted: false,
                    reason: "invalid_order_fields".to_string(),
                    order_id: Some(order_id),
                };
            }

            if let Some(origin) = strategy_origin {
                let lowered = origin.to_ascii_lowercase();
                if lowered.contains("llm") || lowered.contains("gpt") || lowered.contains("model") {
                    return Response {
                        status: "rejected".to_string(),
                        accepted: false,
                        reason: "llm_origin_rejected".to_string(),
                        order_id: Some(order_id),
                    };
                }
            }

            let side_ok = side == "buy" || side == "sell";
            let symbol_ok = !symbol.trim().is_empty() && symbol.len() <= 24;
            let notional = price * quantity as f64;
            let within_limit = notional <= max_notional_usd;

            if !side_ok || !symbol_ok || !within_limit {
                return Response {
                    status: "rejected".to_string(),
                    accepted: false,
                    reason: if !within_limit {
                        "notional_limit_exceeded".to_string()
                    } else {
                        "risk_policy_rejected".to_string()
                    },
                    order_id: Some(order_id),
                };
            }

            if let (Some(ref_px), Some(max_bps)) = (reference_price, max_slippage_bps) {
                if !ref_px.is_finite() || ref_px <= 0.0 || !max_bps.is_finite() || max_bps < 0.0 {
                    return Response {
                        status: "rejected".to_string(),
                        accepted: false,
                        reason: "invalid_price_collar".to_string(),
                        order_id: Some(order_id),
                    };
                }
                let slip_bps = (((price - ref_px).abs()) / ref_px) * 10_000.0;
                if slip_bps > max_bps {
                    return Response {
                        status: "rejected".to_string(),
                        accepted: false,
                        reason: "price_collar_exceeded".to_string(),
                        order_id: Some(order_id),
                    };
                }
            }

            Response {
                status: "accepted".to_string(),
                accepted: true,
                reason: "risk_checks_passed".to_string(),
                order_id: Some(order_id),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{handle_command, Command};
    use std::sync::atomic::AtomicBool;
    use std::sync::Arc;

    #[test]
    fn rejects_llm_origin() {
        let kill_switch = Arc::new(AtomicBool::new(false));
        let response = handle_command(
            Command::NewOrder {
                order_id: "o-1".to_string(),
                symbol: "AAPL".to_string(),
                side: "buy".to_string(),
                quantity: 10,
                price: 100.0,
                max_notional_usd: 2000.0,
                reference_price: None,
                max_slippage_bps: None,
                strategy_origin: Some("llm_router".to_string()),
            },
            &kill_switch,
        );
        assert!(!response.accepted);
        assert_eq!(response.reason, "llm_origin_rejected");
    }

    #[test]
    fn rejects_when_price_collar_exceeded() {
        let kill_switch = Arc::new(AtomicBool::new(false));
        let response = handle_command(
            Command::NewOrder {
                order_id: "o-2".to_string(),
                symbol: "MSFT".to_string(),
                side: "buy".to_string(),
                quantity: 5,
                price: 110.0,
                max_notional_usd: 10000.0,
                reference_price: Some(100.0),
                max_slippage_bps: Some(500.0),
                strategy_origin: Some("rule_engine".to_string()),
            },
            &kill_switch,
        );
        assert!(!response.accepted);
        assert_eq!(response.reason, "price_collar_exceeded");
    }

    #[test]
    fn accepts_when_deterministic_checks_pass() {
        let kill_switch = Arc::new(AtomicBool::new(false));
        let response = handle_command(
            Command::NewOrder {
                order_id: "o-3".to_string(),
                symbol: "NVDA".to_string(),
                side: "sell".to_string(),
                quantity: 2,
                price: 99.8,
                max_notional_usd: 1000.0,
                reference_price: Some(100.0),
                max_slippage_bps: Some(50.0),
                strategy_origin: Some("deterministic_rulebook".to_string()),
            },
            &kill_switch,
        );
        assert!(response.accepted);
        assert_eq!(response.reason, "risk_checks_passed");
    }
}
