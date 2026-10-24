//! Small loopback-only issuer behind an independently configured TLS proxy.
//! It consumes expiring credentials minted by Spry's existing operator CLI;
//! the HTTP process has neither the TURN root secret nor container privileges.
use std::{
    collections::HashMap,
    fs,
    io::{Read, Write},
    net::{IpAddr, TcpListener, TcpStream},
    path::{Path, PathBuf},
    sync::{
        Arc, Mutex,
        atomic::{AtomicUsize, Ordering},
    },
    thread,
    time::{Duration, SystemTime, UNIX_EPOCH},
};

const ORIGIN: &str = "https://forgesworn.dev";
const MAX_POOL: usize = 128;
const MAX_CLIENTS: usize = 2048;
const WINDOW: u64 = 60;

#[derive(Clone)]
struct Credential {
    username: String,
    password: String,
    expires: u64,
}
struct Pool {
    generation: String,
    credentials: Vec<Credential>,
}
struct State {
    generation: String,
    cursor: usize,
    clients: HashMap<IpAddr, Vec<u64>>,
    issued: Vec<u64>,
    highest_wall: u64,
}
struct Config {
    pool: PathBuf,
    cursor: PathBuf,
    host: String,
}

fn seconds() -> Result<u64, ()> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|v| v.as_secs())
        .map_err(|_| ())
}
fn opaque(value: &str, max: usize) -> bool {
    !value.is_empty()
        && value.len() <= max
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}
fn pool(body: &str) -> Result<Pool, ()> {
    if body.len() > 32768 {
        return Err(());
    }
    let mut lines = body.lines();
    let generation = lines
        .next()
        .and_then(|line| line.strip_prefix("SPRYP1\t"))
        .ok_or(())?;
    if !opaque(generation, 64) {
        return Err(());
    }
    let mut credentials = Vec::new();
    for line in lines {
        let (username, password) = line.split_once('\t').ok_or(())?;
        let (expiry, label) = username.split_once(':').ok_or(())?;
        let expires = expiry.parse::<u64>().map_err(|_| ())?;
        if !opaque(label, 64)
            || expiry.len() > 12
            || password.len() != 28
            || !password
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b"+/=".contains(&b))
            || credentials.len() >= MAX_POOL
        {
            return Err(());
        }
        credentials.push(Credential {
            username: username.to_owned(),
            password: password.to_owned(),
            expires,
        });
    }
    if credentials.is_empty() {
        return Err(());
    }
    Ok(Pool {
        generation: generation.to_owned(),
        credentials,
    })
}

fn restore(path: &Path) -> Result<State, ()> {
    let (generation, cursor) = match fs::read_to_string(path) {
        Ok(value) => {
            let (generation, cursor) = value.trim_end().split_once('\t').ok_or(())?;
            if !opaque(generation, 64) {
                return Err(());
            }
            let cursor = cursor.parse::<usize>().map_err(|_| ())?;
            if cursor > MAX_POOL {
                return Err(());
            }
            (generation.to_owned(), cursor)
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => (String::new(), 0),
        Err(_) => return Err(()),
    };
    Ok(State {
        generation,
        cursor,
        clients: HashMap::new(),
        issued: Vec::new(),
        highest_wall: seconds()?,
    })
}
fn persist(config: &Config, state: &State) -> Result<(), ()> {
    let temporary = config.cursor.with_extension("next");
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(&temporary)
        .map_err(|_| ())?;
    file.write_all(format!("{}\t{}\n", state.generation, state.cursor).as_bytes())
        .map_err(|_| ())?;
    file.sync_all().map_err(|_| ())?;
    fs::rename(&temporary, &config.cursor).map_err(|_| ())?;
    Ok(())
}
fn take(config: &Config, state: &mut State, ip: IpAddr, now: u64) -> Result<Credential, u16> {
    if now < state.highest_wall {
        return Err(503);
    }
    state.highest_wall = now;
    state.clients.retain(|_, times| {
        times.retain(|t| now.saturating_sub(*t) < WINDOW);
        !times.is_empty()
    });
    state.issued.retain(|t| now.saturating_sub(*t) < WINDOW);
    if state.issued.len() >= 32
        || state
            .clients
            .get(&ip)
            .is_some_and(|times| times.len() >= 12)
        || state.clients.len() >= MAX_CLIENTS && !state.clients.contains_key(&ip)
    {
        return Err(429);
    }
    let pool = fs::read_to_string(&config.pool)
        .map_err(|_| 503u16)
        .and_then(|value| pool(&value).map_err(|_| 503u16))?;
    if pool.generation != state.generation {
        state.generation = pool.generation;
        state.cursor = 0;
    }
    let mut found = None;
    while state.cursor < pool.credentials.len() {
        let credential = &pool.credentials[state.cursor];
        state.cursor += 1;
        if credential.expires > now + 180 && credential.expires <= now + 1250 {
            found = Some(credential.clone());
            break;
        }
    }
    // Persist consumption before returning a password. A crash cannot hand the
    // same pool slot to a second visitor after an HTTP service restart.
    persist(config, state).map_err(|_| 503u16)?;
    let result = found.ok_or(503u16)?;
    state.issued.push(now);
    state.clients.entry(ip).or_default().push(now);
    Ok(result)
}

struct Request {
    origin: String,
    ip: IpAddr,
    method: String,
}
fn request(stream: &mut TcpStream) -> Result<Request, u16> {
    let mut buffer = [0; 2048];
    let mut used = 0;
    let header_end = loop {
        if used == buffer.len() {
            return Err(413);
        }
        let count = stream.read(&mut buffer[used..]).map_err(|_| 400u16)?;
        if count == 0 {
            return Err(400);
        }
        used += count;
        if let Some(end) = buffer[..used]
            .windows(4)
            .position(|bytes| bytes == b"\r\n\r\n")
        {
            break end + 4;
        }
    };
    let headers = std::str::from_utf8(&buffer[..header_end]).map_err(|_| 400u16)?;
    let mut lines = headers.split("\r\n");
    let first: Vec<_> = lines.next().unwrap_or_default().split(' ').collect();
    if first.len() != 3
        || first[1] != "/turn-credentials"
        || !matches!(first[2], "HTTP/1.0" | "HTTP/1.1")
    {
        return Err(404);
    }
    let method = first[0].to_owned();
    let mut origin = None;
    let mut ip = None;
    let mut length = None;
    let mut content_type = None;
    for line in lines.filter(|line| !line.is_empty()) {
        let (name, value) = line.split_once(':').ok_or(400u16)?;
        let value = value.trim();
        if name.eq_ignore_ascii_case("transfer-encoding") {
            return Err(400);
        }
        let target = if name.eq_ignore_ascii_case("origin") {
            &mut origin
        } else if name.eq_ignore_ascii_case("x-real-ip") {
            &mut ip
        } else if name.eq_ignore_ascii_case("content-length") {
            &mut length
        } else if name.eq_ignore_ascii_case("content-type") {
            &mut content_type
        } else {
            continue;
        };
        if target.replace(value.to_owned()).is_some() {
            return Err(400);
        }
    }
    let origin = origin.ok_or(403u16)?;
    if origin != ORIGIN {
        return Err(403);
    }
    let ip = ip.and_then(|v| v.parse().ok()).ok_or(400u16)?;
    if method == "OPTIONS" {
        return Ok(Request { origin, ip, method });
    }
    if method != "POST" {
        return Err(405);
    }
    if content_type.as_deref().and_then(|v| v.split(';').next()) != Some("application/json") {
        return Err(415);
    }
    let length = length.and_then(|v| v.parse::<usize>().ok()).ok_or(400u16)?;
    if length > 128 {
        return Err(413);
    }
    if header_end + length > buffer.len() {
        return Err(413);
    }
    while used < header_end + length {
        let count = stream
            .read(&mut buffer[used..header_end + length])
            .map_err(|_| 400u16)?;
        if count == 0 {
            return Err(400);
        }
        used += count;
    }
    let body: Vec<_> = buffer[header_end..header_end + length]
        .iter()
        .copied()
        .filter(|b| !b.is_ascii_whitespace())
        .collect();
    if body != b"{\"v\":1}" {
        return Err(400);
    }
    Ok(Request { origin, ip, method })
}
fn respond(stream: &mut TcpStream, status: u16, body: &str, cors: bool) {
    let reason = match status {
        200 => "OK",
        204 => "No Content",
        400 => "Bad Request",
        403 => "Forbidden",
        404 => "Not Found",
        405 => "Method Not Allowed",
        413 => "Payload Too Large",
        415 => "Unsupported Media Type",
        429 => "Too Many Requests",
        _ => "Service Unavailable",
    };
    let cors_headers = if cors {
        format!(
            "Access-Control-Allow-Origin: {ORIGIN}\r\nAccess-Control-Allow-Methods: POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\nAccess-Control-Max-Age: 600\r\n"
        )
    } else {
        String::new()
    };
    let _ = write!(
        stream,
        "HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nCache-Control: no-store\r\nPragma: no-cache\r\nVary: Origin\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\nAllow: POST, OPTIONS\r\nRetry-After: 15\r\n{cors_headers}\r\n{body}",
        body.len()
    );
}
fn handle(mut stream: TcpStream, config: &Config, state: &Mutex<State>) {
    let timeout = Some(Duration::from_secs(2));
    let _ = stream.set_read_timeout(timeout);
    let _ = stream.set_write_timeout(timeout);
    let request = match request(&mut stream) {
        Ok(value) => value,
        Err(status) => {
            respond(
                &mut stream,
                status,
                "{\"error\":\"turn-unavailable\"}",
                false,
            );
            return;
        }
    };
    if request.method == "OPTIONS" {
        respond(&mut stream, 204, "", request.origin == ORIGIN);
        return;
    }
    let result = seconds().map_err(|_| 503u16).and_then(|now| {
        let mut state = state.lock().map_err(|_| 503u16)?;
        take(config, &mut state, request.ip, now).map(|credential| (now, credential))
    });
    match result {
        Ok((now, credential)) => {
            let ttl = credential.expires - now;
            let body = format!(
                "{{\"v\":1,\"iceServers\":[{{\"urls\":[\"turns:{}:5349?transport=tcp\"],\"username\":\"{}\",\"credential\":\"{}\"}}],\"ttlSeconds\":{},\"issuedAt\":{},\"expiresAt\":{},\"refreshAt\":{},\"serverTime\":{}}}",
                config.host,
                credential.username,
                credential.password,
                ttl,
                now * 1000,
                credential.expires * 1000,
                now * 1000 + ttl * 1000 * 2 / 3,
                now * 1000
            );
            respond(&mut stream, 200, &body, true);
        }
        Err(status) => respond(
            &mut stream,
            status,
            "{\"error\":\"turn-unavailable\"}",
            true,
        ),
    }
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    if args.len() != 3
        || !args[2]
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b".-".contains(&b))
        || !args[2].contains('.')
    {
        return Err("usage: spry-public-issuer POOL CURSOR HOSTNAME".into());
    }
    let config = Arc::new(Config {
        pool: PathBuf::from(&args[0]),
        cursor: PathBuf::from(&args[1]),
        host: args[2].clone(),
    });
    let state = Arc::new(Mutex::new(
        restore(&config.cursor).map_err(|_| "invalid issuer state")?,
    ));
    let active = Arc::new(AtomicUsize::new(0));
    let listener = TcpListener::bind("127.0.0.1:7349")?;
    for stream in listener.incoming().flatten() {
        if active.fetch_add(1, Ordering::AcqRel) >= 4 {
            active.fetch_sub(1, Ordering::AcqRel);
            let _ = stream.shutdown(std::net::Shutdown::Both);
            continue;
        }
        let (config, state, active) = (config.clone(), state.clone(), active.clone());
        thread::spawn(move || {
            handle(stream, &config, &state);
            active.fetch_sub(1, Ordering::AcqRel);
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pool_refuses_malformed_or_unbounded_input() {
        let line = "2000000000:opaque\taaaaaaaaaaaaaaaaaaaaaaaaaaa=";
        assert_eq!(
            pool(&format!("SPRYP1\tabc\n{line}\n"))
                .unwrap()
                .credentials
                .len(),
            1
        );
        for value in [
            String::new(),
            format!("SPRYP1\tabc\n{line}\n{}", "x".repeat(32768)),
            "SPRYP1\tabc\n2000000000:bad label\taaaaaaaaaaaaaaaaaaaaaaaaaaa=\n".to_owned(),
            "SPRYP1\tabc\n2000000000:label\tbad\n".to_owned(),
            format!("SPRYP1\tabc\n{}", format!("{line}\n").repeat(129)),
        ] {
            assert!(pool(&value).is_err());
        }
    }
    #[test]
    fn exact_http_body_and_origin_are_required() {
        fn parse(raw: &str) -> Result<Request, u16> {
            let listener = TcpListener::bind("127.0.0.1:0").unwrap();
            let mut client = TcpStream::connect(listener.local_addr().unwrap()).unwrap();
            client.write_all(raw.as_bytes()).unwrap();
            client.shutdown(std::net::Shutdown::Write).unwrap();
            let (mut server, _) = listener.accept().unwrap();
            request(&mut server)
        }
        let header = "POST /turn-credentials HTTP/1.1\r\nOrigin: https://forgesworn.dev\r\nX-Real-IP: 192.0.2.1\r\nContent-Type: application/json\r\nContent-Length: 7\r\n\r\n{\"v\":1}";
        assert!(parse(header).is_ok());
        assert_eq!(
            parse(&header.replace("Origin: https://forgesworn.dev\r\n", "")).err(),
            Some(403)
        );
        assert_eq!(
            parse(&header.replace(ORIGIN, "https://evil.test")).err(),
            Some(403)
        );
        assert_eq!(
            parse(&header.replace(
                "Content-Length: 7",
                "Content-Length: 7\r\nContent-Length: 7"
            ))
            .err(),
            Some(400)
        );
        assert_eq!(
            parse(&header.replace(
                "Content-Length: 7",
                "Transfer-Encoding: chunked\r\nContent-Length: 7"
            ))
            .err(),
            Some(400)
        );
        assert_eq!(
            parse(&header.replace("{\"v\":1}", "{\"v\":2}")).err(),
            Some(400)
        );
        assert_eq!(parse(&header.replace("POST", "GET")).err(), Some(405));
        assert!(parse(&header.replace("POST", "OPTIONS")).is_ok());
    }

    #[test]
    fn consumption_survives_restart_and_limits_and_expiry_fail_closed() {
        let directory =
            std::env::temp_dir().join(format!("spry-issuer-test-{}", std::process::id()));
        fs::create_dir(&directory).unwrap();
        let config = Config {
            pool: directory.join("pool"),
            cursor: directory.join("cursor"),
            host: "relay.test".into(),
        };
        let fixture = |generation: &str| {
            format!(
                "SPRYP1\t{generation}\n{}",
                (0..128)
                    .map(|i| format!("2000000000:label{i}\taaaaaaaaaaaaaaaaaaaaaaaaaaa=\n"))
                    .collect::<String>()
            )
        };
        fs::write(&config.pool, fixture("first")).unwrap();
        let now = 1999998800;
        let ip: IpAddr = "192.0.2.1".parse().unwrap();
        let mut state = State {
            generation: String::new(),
            cursor: 0,
            clients: HashMap::new(),
            issued: Vec::new(),
            highest_wall: now,
        };
        for i in 0..12 {
            assert_eq!(
                take(&config, &mut state, ip, now).unwrap().username,
                format!("2000000000:label{i}")
            );
        }
        assert_eq!(take(&config, &mut state, ip, now).err(), Some(429));
        let mut restarted = restore(&config.cursor).unwrap();
        restarted.highest_wall = now;
        assert_eq!(
            take(&config, &mut restarted, ip, now).unwrap().username,
            "2000000000:label12"
        );
        for i in 2..33 {
            take(
                &config,
                &mut restarted,
                format!("192.0.2.{i}").parse().unwrap(),
                now,
            )
            .unwrap();
        }
        assert_eq!(
            take(&config, &mut restarted, "192.0.2.99".parse().unwrap(), now).err(),
            Some(429)
        );
        assert_eq!(take(&config, &mut restarted, ip, now - 1).err(), Some(503));
        assert!(take(&config, &mut restarted, ip, now + 61).is_ok());
        assert_eq!(
            take(&config, &mut restarted, ip, 2000000000).err(),
            Some(503)
        );
        fs::write(&config.pool, fixture("second")).unwrap();
        let mut fresh = restore(&config.cursor).unwrap();
        fresh.highest_wall = now;
        assert_eq!(
            take(&config, &mut fresh, ip, now).unwrap().username,
            "2000000000:label0"
        );
        fs::remove_dir_all(directory).unwrap();
    }
}
