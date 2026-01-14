# Bloomberg Telegram - Signal Intelligence Engine

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Next.js-14+-black.svg" alt="Next.js">
  <img src="https://img.shields.io/badge/PostgreSQL-TimescaleDB-blue.svg" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</div>

<p align="center">
  <strong>A real-time intelligence layer for crypto Telegram channels</strong>
</p>

<p align="center">
  Bloomberg Terminal-grade signal intelligence for the memecoin era.
  <br />
  Ingest thousands of noisy Telegram messages → Output compressed, actionable insights.
</p>

---

## 🚀 Features

### Core Intelligence
- **Real-time Telegram Ingestion** - Connect your Telegram account and monitor unlimited channels
- **Entity Extraction** - Automatically detect tokens, wallets, prices, and sentiment
- **Signal Clustering** - Group related messages about the same token/event
- **Caller Reputation** - Track and rank signal sources by hit rate and returns
- **"Why Is This Moving?"** - Explain price movements with correlated signals

### Signal Feed
- **Priority Scoring** - Rank signals by source diversity, velocity, whale activity
- **Sentiment Analysis** - Bullish/bearish classification with confidence scores
- **Deduplication** - Eliminate noise and duplicate signals across channels
- **Real-time Updates** - WebSocket-powered live feed

### Supported Chains
- 🟣 **Solana** (Priority)
- 🔵 **Base**
- 🟡 **BNB Chain**

### External Integrations (Free APIs)
- DEX Screener - Price data and charts
- Jupiter - Solana token data
- CoinGecko - General token info

---

## 📋 Architecture

```
Telegram Sources → Ingestion Layer → Processing Pipeline → Intelligence Engine → User Interface
      ↓                  ↓                   ↓                    ↓                  ↓
  - Groups           - Rate limiting     - Entity extraction   - Clustering       - Feed view
  - Bots             - Deduplication     - Sentiment           - Ranking          - Token pages
  - Channels         - Normalization     - Classification      - Correlation      - Alerts
  - DMs                                                        - Memory           - Leaderboard
```

---

## 🛠️ Tech Stack

### Backend
- **Python 3.11+** with FastAPI
- **Telethon** for Telegram API
- **PostgreSQL + TimescaleDB** for time-series data
- **Redis** for queues and caching
- **Qdrant** for vector similarity search
- **Celery** for background tasks
- **sentence-transformers** for embeddings

### Frontend
- **Next.js 14** with App Router
- **React Query** for data fetching
- **Zustand** for state management
- **Tailwind CSS** for styling
- **Framer Motion** for animations
- **Socket.io** for real-time updates

### Infrastructure
- **Docker Compose** for local development
- Self-hosted friendly design

---

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ (for frontend development)
- Python 3.11+ (for backend development)
- Telegram API credentials from [my.telegram.org](https://my.telegram.org/apps)

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/bloomberg-telegram.git
cd bloomberg-telegram

# Copy environment file
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Start with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Services will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### 3. Connect Your Telegram

1. Go to http://localhost:3000/settings
2. Click "Add Account"
3. Enter your Telegram API credentials
4. Verify with the code sent to your Telegram
5. Add channels/groups to monitor

---

## 📖 API Reference

### Signals
```bash
# Get signal feed
GET /api/v1/signals/feed?chain=solana&min_score=50

# Get cluster details
GET /api/v1/signals/clusters/{cluster_id}

# Why is this moving?
GET /api/v1/signals/why-moving/{chain}/{token_address}
```

### Tokens
```bash
# Get token info
GET /api/v1/tokens/info/{chain}/{token_address}

# Search tokens
GET /api/v1/tokens/search?query=COWSAY

# Get callers for a token
GET /api/v1/tokens/callers/{chain}/{token_address}
```

### Sources
```bash
# Get leaderboard
GET /api/v1/sources/leaderboard

# Get source reputation
GET /api/v1/sources/reputation/{telegram_id}
```

### WebSocket
```javascript
const socket = io('ws://localhost:8000/feed/ws');

// Subscribe to signals
socket.emit('subscribe', { channels: ['signals'] });

// Receive updates
socket.on('signal_update', (data) => {
  console.log('New signal:', data);
});
```

---

## 🏗️ Development

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run Celery worker
celery -A app.workers.celery_app worker --loglevel=info

# Run Celery beat (scheduler)
celery -A app.workers.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

---

## 📊 Scoring Algorithm

Signals are scored 0-100 based on:

| Component | Weight | Description |
|-----------|--------|-------------|
| Source Diversity | 25% | More unique sources = higher |
| Recency | 20% | Newer signals = higher (decays over 1h) |
| Velocity | 20% | Faster mention rate = higher |
| Wallet Activity | 15% | Whale wallets = higher |
| Source Quality | 20% | Higher trust scores = higher |
| Spam Penalty | -30% | Spam patterns reduce score |

---

## 🔐 Security

- **Telegram credentials** are encrypted at rest using Fernet
- **Session tokens** use JWT with configurable expiration
- **No server-side storage** of raw API credentials
- **CORS** configured for specific origins
- **Rate limiting** on all API endpoints

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This software is for educational and informational purposes only. It is not financial advice. Cryptocurrency trading carries significant risk. Always do your own research (DYOR) before making investment decisions.

---

<div align="center">
  <strong>Built for degens, by degens. 🚀</strong>
</div>
