<div align="center">

<img width="100%" src="banner-0.jpg" alt="Black Hole"/>

---

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-8B5CF6?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)]()
[![Anti-Censorship](https://img.shields.io/badge/Purpose-Anti--Censorship-FF6B6B?style=for-the-badge)]()

</div>

---

## what is this?

a proxy engine that uses **chaos theory** to make your traffic unpredictable. instead of regular patterns that DPI can detect, it generates fragmentation timing based on the Lorenz Attractor - making each connection mathematically unique

built for bypassing censorship. tested against advanced DPI systems on Android (Termux) and Linux

---

## how it works

```mermaid
flowchart TD
    A["Your Application Or Any"]

    A -->|127.0.0.1:10809| B["Protocol Detector"]

    B --> C[HTTP]
    B --> D[HTTPS]
    B --> E[SOCKS5]
    B --> F[WebSocket]

    C & D & E & F --> G["Bypass Check"]

    G -->|Iranian domains .ir| H["Direct"]
    G -->|Download files .zip .mp4| I["Direct"]
    G -->|Everything else| J["Chaos Engine
    Lorenz + Logistic Map"]

    J --> K["DNS
    DoH / DoT
    Cloudflare · Google · Quad9"]

    J --> L["TLS Fragmentation
    2-7 pieces · 0.5-3ms jitter"]

    K & L --> M["Domain Fronting
    Cloudflare · Akamai · Google CDN"]

    M --> N["Internet"]

    style A fill:#1a0933,stroke:#8B5CF6,color:#fff
    style B fill:#1a0933,stroke:#8B5CF6,color:#fff
    style G fill:#1a0933,stroke:#8B5CF6,color:#fff
    style J fill:#2d1b69,stroke:#8B5CF6,color:#fff
    style K fill:#1a0933,stroke:#06B6D4,color:#fff
    style L fill:#1a0933,stroke:#06B6D4,color:#fff
    style M fill:#1a0933,stroke:#06B6D4,color:#fff
    style H fill:#064e3b,stroke:#059669,color:#fff
    style I fill:#064e3b,stroke:#059669,color:#fff
    style N fill:#1e1b4b,stroke:#8B5CF6,color:#fff
    style C fill:#374151,stroke:#6B7280,color:#fff
    style D fill:#374151,stroke:#6B7280,color:#fff
    style E fill:#374151,stroke:#6B7280,color:#fff
    style F fill:#374151,stroke:#6B7280,color:#fff
```

---

## features

| Feature | Description | Status |
|---------|-------------|--------|
| Protocol Multiplexing | Auto-detect HTTP/HTTPS, SOCKS5, WebSocket | Active |
| Chaos Fragmentation | Lorenz-Logistic hybrid TLS fragmentation | Active |
| Encrypted DNS | DoH and DoT support | Active |
| Domain Fronting | Hide destination via CDN | Active |
| Smart Bypass | Direct routing for Iranian domains | Active |
| Real-time Stats | Monitor connections and traffic | Active |
| Connection Limiting | Max 100 concurrent connections | Active |
| Web Dashboard | Visual monitoring interface | Active |
| Executable (exe) | Single-file build for Windows/Linux | Planned |

---

## install

```bash
# requirements
pip install pyyaml aiohttp numpy

# or
pip install -r requirements.txt

# termux (android)
pkg install python-numpy
pip install pyyaml aiohttp

# run
python3 main.py
```

that's it

---

## configuration

edit `config.yaml`:

```yaml
server:
  host: "0.0.0.0"        # آدرس listen - 0.0.0.0 یعنی همه interface ها
  port: 10809             # پورت پروکسی
  protocol_timeout: 30   # ثانیه - timeout برای detect کردن protocol اول

web:
  enabled: true          # داشبورد وب روشن/خاموش
  port: 8080             # پورت داشبورد

buffers:
  small: 8192            # 8KB - برای خوندن اول connection
  medium: 65536          # 64KB - buffer معمولی relay
  large: 262144          # 256KB
  xlarge: 1048576        # 1MB - برای فایل‌های بزرگ

dns:
  mode: "doh"            # doh = DNS-over-HTTPS / dot = DNS-over-TLS
  cache_ttl: 300         # ثانیه - چقدر DNS cache نگه داشته بشه
  cache_max_size: 1000   # حداکثر تعداد entry در cache

limits:
  max_connections: 100   # حداکثر connection همزمان
  connection_timeout: 30 # ثانیه - timeout کل connection
  idle_timeout: 60       # ثانیه - قطع connection بی‌تحرک

bypass:
  iranian_domains: true          # دامنه‌های .ir مستقیم وصل بشن
  download_direct: true          # فایل‌های دانلودی (.zip .mp4 ...) مستقیم

chaos:
  aggressive: true        # true = fragmentation بیشتر، سخت‌تر برای DPI
  base_jitter_ms: 1.0    # میلی‌ثانیه - تاخیر پایه بین fragment ها
  variance_ms: 2.0       # میلی‌ثانیه - میزان تصادفی بودن تاخیر

evasion:
  domain_fronting: true   # مخفی کردن مقصد از طریق CDN
  tls_fragmentation: true # شکستن TLS ClientHello به چند تکه
  traffic_padding: true   # اضافه کردن padding به packet ها (planned)
  dummy_traffic: true     # ترافیک فیک برای گمراه کردن DPI (planned)
  protocol_mimicry: true  # شبیه‌سازی protocol های دیگه (planned)

performance:
  connection_pooling: true  # reuse کردن connection ها (planned)
  pool_max_size: 50         # حداکثر connection در pool
  smart_caching: true       # cache هوشمند response ها (planned)

logging:
  level: "INFO"  # DEBUG / INFO / WARNING / ERROR
  file: "cte.log"  # فایل لاگ - حذف کن اگه نمیخوای
  console: true    # نمایش لاگ در terminal
```

---

## usage

**start the server:**
```bash
python3 main.py
```

**configure your client :**

```
# HTTP
Proxy: 127.0.0.1:10809  |  Type: HTTP

# SOCKS5
Host: 127.0.0.1  |  Port: 10809  |  Type: SOCKS5
```

---

## web dashboard

open `http://127.0.0.1:8080` in your browser while the proxy is running.

shows live stats — connections, traffic, routing, protocols, chaos metrics, DNS cache.  
auto-refreshes every 2 seconds.

---

## chaos engine

```mermaid
flowchart TD
    S["SHA-256 Seed
    nanosecond time + connection_id"]

    S --> LI["Lorenz Initial State
    x ∈ [-10,10]
    y ∈ [-10,10]
    z ∈ [0,40]"]

    S --> GI["Logistic Initial State
    x ∈ [0,1]
    r = 3.99"]

    LI --> LS["Lorenz Step
    dx = σ(y-x)·dt
    dy = (x(ρ-z)-y)·dt
    dz = (xy-βz)·dt
    σ=10, ρ=28, β=8/3"]

    GI --> GS["Logistic Step
    xₙ₊₁ = 3.99·xₙ·(1-xₙ)"]

    LS & GS --> MIX["Mix Entropy
    lorenz = (x+10)/20
    mixed = (lorenz + logistic) % 1
    final = (mixed + iteration×φ) % 1"]

    MIX --> FC["fragment_count
    2-8 pieces"]
    MIX --> FP["fragment_positions
    per-segment chaos split"]
    MIX --> FT["fragment_timing
    0.5-3ms jitter"]

    FC & FP & FT --> OUT["TLS ClientHello
    fragmented + delayed"]

    MIX --> HIST["History Buffer
    deque maxlen=1000"]

    HIST --> LY["Lyapunov Exponent"]
    HIST --> SE["Shannon Entropy"]
    HIST --> CD["Correlation Dimension"]

    LY & SE & CD --> DASH["Web Dashboard
    real-time metrics"]

    style S fill:#1a0933,stroke:#8B5CF6,color:#fff
    style LI fill:#1a0933,stroke:#8B5CF6,color:#fff
    style GI fill:#1a0933,stroke:#8B5CF6,color:#fff
    style LS fill:#2d1b69,stroke:#8B5CF6,color:#fff
    style GS fill:#2d1b69,stroke:#8B5CF6,color:#fff
    style MIX fill:#2d1b69,stroke:#8B5CF6,color:#fff
    style FC fill:#1a0933,stroke:#06B6D4,color:#fff
    style FP fill:#1a0933,stroke:#06B6D4,color:#fff
    style FT fill:#1a0933,stroke:#06B6D4,color:#fff
    style OUT fill:#064e3b,stroke:#059669,color:#fff
    style HIST fill:#1a0933,stroke:#8B5CF6,color:#fff
    style LY fill:#1e1b4b,stroke:#8B5CF6,color:#fff
    style SE fill:#1e1b4b,stroke:#8B5CF6,color:#fff
    style CD fill:#1e1b4b,stroke:#8B5CF6,color:#fff
    style DASH fill:#064e3b,stroke:#059669,color:#fff
```

---

## dns privacy

```
DoH (DNS-over-HTTPS)  →  Cloudflare / Google / Quad9 / AdGuard
DoT (DNS-over-TLS)    →  same providers
```

prevents DNS poisoning. hides queries from ISP

---

## performance

```
Max Connections  →  100 concurrent
Throughput       →  ~50-100 Mbps
Added Latency    →  +2-5ms (fragmentation overhead)
Memory Usage     →  ~50-100 MB
```

> numbers based on `aggressive: true` — latency drops to ~1ms with `aggressive: false`

---

## project structure

```
chaos_traffic_engine/
│
├── main.py
├── config.yaml
├── requirements.txt
│
├── core/
│   ├── engine.py
│   ├── dns.py
│   └── tls.py
│
├── server/
│   ├── proxy.py
│   ├── protocols.py
│   └── relay.py
│
├── evasion/
│   └── fronting.py
│
├── monitoring/
│   ├── stats.py
│   └── limiter.py
│
├── utils/
│   ├── bypass.py
│   └── logger.py
│
├── web/
│   ├── dashboard.py
│   ├── api.py
│   └── static/
│       ├── index.html
│       ├── script.js
│       └── style.css
│
└── config/
    ├── dns_servers.json
    ├── cdn_domains.json
    └── iranian_domains.json
```

---

## troubleshooting

**port already in use:**
```bash
sudo lsof -i :10809
# change port in config.yaml if needed
```

**DNS failing:**
```yaml
dns:
  mode: "dot"  # switch between doh/dot
```

**slow speed:**
```yaml
chaos:
  aggressive: false  # reduce fragmentation overhead
```

**YouTube buffering:**
```yaml
evasion:
  domain_fronting: false  # disable if streams keep dropping
```

---

## security notes

- ✅ encrypted DNS — queries hidden from ISP
- ✅ unpredictable TLS fingerprint — chaos-generated, unique per connection
- ✅ domain fronting — real destination hidden behind CDN
- ✅ Iranian domain bypass — local traffic never goes through proxy
- ⚠️ no authentication — bind to `127.0.0.1` if on a shared network

---

<div align="center">

**MIT License** — use freely, ethically, responsibly.

*✧ 𝙎𝙩𝙖𝙮 𝙐𝙣𝙠𝙣𝙤𝙬𝙣, 𝙨𝙩𝙖𝙮 𝙛𝙧𝙚𝙚 ✧* 

</div>