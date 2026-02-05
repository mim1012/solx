# Product Requirements Document (PRD)
## Phoenix Trading System v4.1

**Date**: 2026-01-24
**Product Owner**: User
**Document Type**: Technical PRD for Existing System

---

## 1. Product Overview

### 1.1 Purpose
Phoenix Trading System is an automated grid trading bot for SOXL ETF (3x leveraged semiconductor index) that exploits mean-reversion patterns in volatile markets through a 240-tier price ladder strategy.

### 1.2 Core Value Proposition
- **Automated profit extraction** from sideways/corrective markets
- **Risk-managed** position sizing across 240 price tiers
- **Slippage prevention** through limit orders only
- **Gap protection** with Tier 1 custom trading mode
- **24/7 unattended operation** with Excel-based configuration

### 1.3 Target Users
- Individual traders with $10,000+ capital
- Investors seeking automated mean-reversion strategies
- Traders comfortable with potential drawdowns in strong downtrends

---

## 2. Functional Requirements (FRs)

### FR1: System Initialization and Authentication
**Description**: The system shall initialize on startup and authenticate with KIS (Korea Investment & Securities) REST API.

**Requirements**:
- FR1.1: Read configuration from Excel file `phoenix_grid_template_v3.xlsx`
- FR1.2: Authenticate using OAuth2 with APP KEY and APP SECRET
- FR1.3: Cache access token (24-hour expiry) to `kis_token_cache.json`
- FR1.4: Validate all required Excel fields (19 fields in B12-B22)
- FR1.5: Initialize Telegram notifications if enabled

### FR2: Tier 1 (High Water Mark) Management
**Description**: The system shall track and update the highest price (Tier 1) observed during operation.

**Requirements**:
- FR2.1: Initialize Tier 1 price to current market price on first run
- FR2.2: Update Tier 1 to new highs when current price exceeds Tier 1
- FR2.3: Persist Tier 1 price to Excel B18
- FR2.4: Update Tier 1 automatically after full position clearance

### FR3: Price Tier Calculation
**Description**: The system shall calculate buy and sell prices for all 240 tiers based on Tier 1.

**Requirements**:
- FR3.1: Calculate tier N buy price: `Tier1_price × (1 - (N-1) × 0.005)` (0.5% intervals)
- FR3.2: Calculate tier N sell price: `Tier_buy_price × 1.03` (+3% profit target)
- FR3.3: Store tier table (240 rows) to Excel C25:G264

### FR4: Market Data Acquisition
**Description**: The system shall query real-time market data for SOXL from KIS REST API.

**Requirements**:
- FR4.1: Query current price every polling interval (default 40 seconds)
- FR4.2: Auto-detect exchange (NAS/AMS/NYS) for ticker
- FR4.3: Handle API rate limiting (5 requests/second max, 200ms interval)
- FR4.4: Cache price data with timestamp

### FR5: Batch Buy Signal Generation
**Description**: The system shall generate buy signals for multiple eligible tiers simultaneously.

**Requirements**:
- FR5.1: Identify all tiers where `current_price ≤ tier_buy_price` AND position not held
- FR5.2: Group eligible tiers into single batch signal
- FR5.3: Skip buy signal if 240th tier already filled
- FR5.4: Respect max tiers limit (240 tiers)

### FR6: Batch Sell Signal Generation
**Description**: The system shall generate sell signals for held positions when profit target reached.

**Requirements**:
- FR6.1: Identify all tiers where `current_price ≥ tier_sell_price` AND position held
- FR6.2: Group eligible sell tiers into single batch signal
- FR6.3: Support full clearance when all positions sold

### FR7: Order Execution (Buy)
**Description**: The system shall execute buy orders as limit orders to prevent slippage.

**Requirements**:
- FR7.1: Place limit buy order at `current_price` (or lower)
- FR7.2: Calculate quantity: `Tier_investment_amount / current_price`
- FR7.3: Submit order via KIS REST API `/uapi/overseas-stock/v1/trading/order`
- FR7.4: Wait up to 20 seconds for fill confirmation (10 retries × 2 seconds)
- FR7.5: Handle partial fills by distributing quantity across tiers

### FR8: Order Execution (Sell)
**Description**: The system shall execute sell orders as limit orders for profit realization.

**Requirements**:
- FR8.1: Place limit sell order at `current_price` (or higher)
- FR8.2: Calculate quantity from held position
- FR8.3: Submit order via KIS REST API
- FR8.4: Wait up to 20 seconds for fill confirmation
- FR8.5: Update Tier 1 if all positions cleared

### FR9: Tier 1 Custom Trading Mode
**Description**: The system shall optionally trade Tier 1 when current price > Tier 1 price.

**Requirements**:
- FR9.1: Enable/disable via Excel B20 (`TRUE`/`FALSE`)
- FR9.2: When enabled and `current_price > Tier1_price × (1 + buy_percent)`:
  - Buy at Tier 1 designated price (not current price)
  - Invest fixed percentage (Excel B21, e.g., 10% = $1000 of $10,000)
- FR9.3: Sell when `current_price ≥ Tier1_buy_price × 1.03`
- FR9.4: Purpose: Capture gap-up profits

### FR10: Position Management
**Description**: The system shall track positions using immutable dataclass objects.

**Requirements**:
- FR10.1: Store position data: tier, quantity, avg_price, invested_amount, opened_at
- FR10.2: Update positions on every fill confirmation
- FR10.3: Persist positions to Excel (tier table C25:G264)
- FR10.4: Support partial fill handling

### FR11: Excel State Persistence
**Description**: The system shall persist all state to Excel for human readability and recovery.

**Requirements**:
- FR11.1: Save 4 Excel areas on every state change:
  - Area A: Settings (B12-B22)
  - Area B: Program info (H12-H22)
  - Area C: Tier table (C25:G264)
  - Area D: Simulation (I25:M264)
- FR11.2: Append operation logs to Sheet 2 "02_운용로그_히스토리"
- FR11.3: Retry save up to 3 times with 1-second delay on PermissionError
- FR11.4: Warn user if Excel locked

### FR12: Trading Hours Management
**Description**: The system shall respect US market hours (NYSE/AMEX/NASDAQ).

**Requirements**:
- FR12.1: Convert Korea time (UTC+9) to US Eastern time
- FR12.2: Detect market open: 23:30 KST (09:30 EST)
- FR12.3: Detect market close: 06:00 KST next day (16:00 EST)
- FR12.4: Pause trading outside market hours
- FR12.5: Auto-resume on next market open

### FR13: Error Handling and Recovery
**Description**: The system shall handle common failures gracefully.

**Requirements**:
- FR13.1: Retry failed API calls (3 attempts with exponential backoff)
- FR13.2: Handle token expiry by re-authentication
- FR13.3: Handle rate limiting with 200ms delays
- FR13.4: Handle partial order fills
- FR13.5: Log all errors to console and `phoenix_trading.log`

### FR14: Telegram Notifications
**Description**: The system shall optionally send trade notifications via Telegram.

**Requirements**:
- FR14.1: Enable/disable via Excel B16
- FR14.2: Send notifications for:
  - System start/stop
  - Buy/sell order executions
  - Tier 1 updates
  - Errors
- FR14.3: Use Telegram Bot API with token from Excel B17

### FR15: Graceful Shutdown
**Description**: The system shall handle shutdown signals (Ctrl+C, SIGTERM) cleanly.

**Requirements**:
- FR15.1: Catch SIGINT/SIGTERM signals
- FR15.2: Save final state to Excel
- FR15.3: Close KIS API connection
- FR15.4: Exit with status code

---

## 3. Non-Functional Requirements (NFRs)

### NFR1: Performance
- **NFR1.1**: Process price tick and generate signals within 5 seconds
- **NFR1.2**: Execute order placement within 10 seconds
- **NFR1.3**: Excel save operation within 3 seconds (normal case)

### NFR2: Reliability
- **NFR2.1**: 99.9% uptime during market hours (excluding exchange outages)
- **NFR2.2**: Survive network disconnections up to 60 seconds
- **NFR2.3**: Auto-recover from API rate limiting

### NFR3: Security
- **NFR3.1**: Store API credentials in Excel (user responsibility for file security)
- **NFR3.2**: Cache tokens with file system permissions (user read/write only)
- **NFR3.3**: No credentials in logs or console output

### NFR4: Maintainability
- **NFR4.1**: All runtime configuration via Excel (zero code changes for parameter tuning)
- **NFR4.2**: Structured logging with timestamps
- **NFR4.3**: Type-safe code with Python dataclasses

### NFR5: Usability
- **NFR5.1**: Single Excel file configuration
- **NFR5.2**: Clear console output with status messages
- **NFR5.3**: Korean and English messages (bilingual)
- **NFR5.4**: Telegram notifications for remote monitoring

### NFR6: Scalability
- **NFR6.1**: Support 240 tiers without performance degradation
- **NFR6.2**: Handle batch orders of 20+ tiers simultaneously
- **NFR6.3**: Process tick data at 1-second intervals (if needed)

### NFR7: Compatibility
- **NFR7.1**: Run on Windows 10/11 (64-bit)
- **NFR7.2**: Python 3.8+ required
- **NFR7.3**: Excel 2016+ or compatible (openpyxl library)
- **NFR7.4**: KIS REST API (64-bit compatible)

---

## 4. Out of Scope

### Not Implemented
- ❌ Stop-loss or position-based risk management
- ❌ Multiple ticker support (SOXL only)
- ❌ Portfolio rebalancing
- ❌ Multi-account support
- ❌ Web dashboard or GUI
- ❌ Backtesting framework
- ❌ Machine learning / AI predictions

### Intentional Design Decisions
- No stop-loss: Strategy relies on mean reversion
- No shorting: Long-only strategy
- No leverage beyond SOXL's inherent 3x
- No database: Excel serves as single source of truth

---

## 5. Success Metrics

### Product Success
- Achieve +3% profit per filled tier on average
- Maintain <0.1% slippage rate (limit orders)
- Handle 95%+ of market hours without manual intervention

### Technical Success
- Zero data loss on crashes (Excel persistence)
- <5 second latency from price change to order execution
- 100% fill confirmation accuracy

---

## 6. Dependencies

### External Systems
- KIS (Korea Investment & Securities) REST API
- NYSE/AMEX/NASDAQ market data
- Telegram Bot API (optional)

### Technology Stack
- Python 3.8+
- openpyxl (Excel I/O)
- requests (HTTP client)
- Standard library (dataclasses, datetime, logging)

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Strong downtrend | All 240 tiers filled, capital locked | User accepts risk, no auto-stop-loss |
| KIS API outage | Cannot trade | Retry logic, manual monitoring |
| Excel file corruption | State loss | Regular backups, append-only log sheet |
| Partial fills on large orders | Incorrect position tracking | Distribute fills across tiers |
| Gap down at open | Miss buy opportunities | Tier 1 updates before market open |

---

## 8. Future Enhancements (Backlog)

- Multi-ticker support (TQQQ, SOXL, etc.)
- Web dashboard for monitoring
- Position restoration on restart (read Excel positions)
- Advanced risk management (max drawdown limits)
- Backtesting engine
- Machine learning price prediction

---

## Appendix: Key Terms

- **Tier 1**: Highest observed price (high water mark)
- **Tier N**: Price level N × 0.5% below Tier 1
- **Grid Trading**: Buy on dips, sell on bounces, repeat
- **Batch Order**: Single API call for multiple tier orders
- **Limit Order**: Order at specified price (prevent slippage)
- **Fill Confirmation**: Polling-based check if order executed
- **Tier 1 Custom Mode**: Optional trading when price > Tier 1
