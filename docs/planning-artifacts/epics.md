---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
inputDocuments:
  - "docs/planning-artifacts/prd.md"
  - "docs/planning-artifacts/architecture.md"
workflowCompleted: true
completedDate: "2026-01-25"
---

# Phoenix Trading System - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Phoenix Trading System, decomposing the requirements from the PRD and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR1: System Initialization and Authentication**
- FR1.1: Read configuration from Excel file `phoenix_grid_template_v3.xlsx`
- FR1.2: Authenticate using OAuth2 with APP KEY and APP SECRET
- FR1.3: Cache access token (24-hour expiry) to `kis_token_cache.json`
- FR1.4: Validate all required Excel fields (19 fields in B12-B22)
- FR1.5: Initialize Telegram notifications if enabled

**FR2: Tier 1 (High Water Mark) Management**
- FR2.1: Initialize Tier 1 price to current market price on first run
- FR2.2: Update Tier 1 to new highs when current price exceeds Tier 1
- FR2.3: Persist Tier 1 price to Excel B18
- FR2.4: Update Tier 1 automatically after full position clearance

**FR3: Price Tier Calculation**
- FR3.1: Calculate tier N buy price: `Tier1_price × (1 - (N-1) × 0.005)` (0.5% intervals)
- FR3.2: Calculate tier N sell price: `Tier_buy_price × 1.03` (+3% profit target)
- FR3.3: Store tier table (240 rows) to Excel C25:G264

**FR4: Market Data Acquisition**
- FR4.1: Query current price every polling interval (default 40 seconds)
- FR4.2: Auto-detect exchange (NAS/AMS/NYS) for ticker
- FR4.3: Handle API rate limiting (5 requests/second max, 200ms interval)
- FR4.4: Cache price data with timestamp

**FR5: Batch Buy Signal Generation**
- FR5.1: Identify all tiers where `current_price ≤ tier_buy_price` AND position not held
- FR5.2: Group eligible tiers into single batch signal
- FR5.3: Skip buy signal if 240th tier already filled
- FR5.4: Respect max tiers limit (240 tiers)

**FR6: Batch Sell Signal Generation**
- FR6.1: Identify all tiers where `current_price ≥ tier_sell_price` AND position held
- FR6.2: Group eligible sell tiers into single batch signal
- FR6.3: Support full clearance when all positions sold

**FR7: Order Execution (Buy)**
- FR7.1: Place limit buy order at `current_price` (or lower)
- FR7.2: Calculate quantity: `Tier_investment_amount / current_price`
- FR7.3: Submit order via KIS REST API `/uapi/overseas-stock/v1/trading/order`
- FR7.4: Wait up to 20 seconds for fill confirmation (10 retries × 2 seconds)
- FR7.5: Handle partial fills by distributing quantity across tiers

**FR8: Order Execution (Sell)**
- FR8.1: Place limit sell order at `current_price` (or higher)
- FR8.2: Calculate quantity from held position
- FR8.3: Submit order via KIS REST API
- FR8.4: Wait up to 20 seconds for fill confirmation
- FR8.5: Update Tier 1 if all positions cleared

**FR9: Tier 1 Custom Trading Mode**
- FR9.1: Enable/disable via Excel B20 (`TRUE`/`FALSE`)
- FR9.2: When enabled and `current_price > Tier1_price × (1 + buy_percent)`:
  - Buy at Tier 1 designated price (not current price)
  - Invest fixed percentage (Excel B21, e.g., 10% = $1000 of $10,000)
- FR9.3: Sell when `current_price ≥ Tier1_buy_price × 1.03`
- FR9.4: Purpose: Capture gap-up profits

**FR10: Position Management**
- FR10.1: Store position data: tier, quantity, avg_price, invested_amount, opened_at
- FR10.2: Update positions on every fill confirmation
- FR10.3: Persist positions to Excel (tier table C25:G264)
- FR10.4: Support partial fill handling

**FR11: Excel State Persistence**
- FR11.1: Save 4 Excel areas on every state change:
  - Area A: Settings (B12-B22)
  - Area B: Program info (H12-H22)
  - Area C: Tier table (C25:G264)
  - Area D: Simulation (I25:M264)
- FR11.2: Append operation logs to Sheet 2 "02_운용로그_히스토리"
- FR11.3: Retry save up to 3 times with 1-second delay on PermissionError
- FR11.4: Warn user if Excel locked

**FR12: Trading Hours Management**
- FR12.1: Convert Korea time (UTC+9) to US Eastern time
- FR12.2: Detect market open: 23:30 KST (09:30 EST)
- FR12.3: Detect market close: 06:00 KST next day (16:00 EST)
- FR12.4: Pause trading outside market hours
- FR12.5: Auto-resume on next market open

**FR13: Error Handling and Recovery**
- FR13.1: Retry failed API calls (3 attempts with exponential backoff)
- FR13.2: Handle token expiry by re-authentication
- FR13.3: Handle rate limiting with 200ms delays
- FR13.4: Handle partial order fills
- FR13.5: Log all errors to console and `phoenix_trading.log`

**FR14: Telegram Notifications**
- FR14.1: Enable/disable via Excel B16
- FR14.2: Send notifications for:
  - System start/stop
  - Buy/sell order executions
  - Tier 1 updates
  - Errors
- FR14.3: Use Telegram Bot API with token from Excel B17

**FR15: Graceful Shutdown**
- FR15.1: Catch SIGINT/SIGTERM signals
- FR15.2: Save final state to Excel
- FR15.3: Close KIS API connection
- FR15.4: Exit with status code

### Non-Functional Requirements

**NFR1: Performance**
- NFR1.1: Process price tick and generate signals within 5 seconds
- NFR1.2: Execute order placement within 10 seconds
- NFR1.3: Excel save operation within 3 seconds (normal case)

**NFR2: Reliability**
- NFR2.1: 99.9% uptime during market hours (excluding exchange outages)
- NFR2.2: Survive network disconnections up to 60 seconds
- NFR2.3: Auto-recover from API rate limiting

**NFR3: Security**
- NFR3.1: Store API credentials in Excel (user responsibility for file security)
- NFR3.2: Cache tokens with file system permissions (user read/write only)
- NFR3.3: No credentials in logs or console output

**NFR4: Maintainability**
- NFR4.1: All runtime configuration via Excel (zero code changes for parameter tuning)
- NFR4.2: Structured logging with timestamps
- NFR4.3: Type-safe code with Python dataclasses

**NFR5: Usability**
- NFR5.1: Single Excel file configuration
- NFR5.2: Clear console output with status messages
- NFR5.3: Korean and English messages (bilingual)
- NFR5.4: Telegram notifications for remote monitoring

**NFR6: Scalability**
- NFR6.1: Support 240 tiers without performance degradation
- NFR6.2: Handle batch orders of 20+ tiers simultaneously
- NFR6.3: Process tick data at 1-second intervals (if needed)

**NFR7: Compatibility**
- NFR7.1: Run on Windows 10/11 (64-bit)
- NFR7.2: Python 3.8+ required
- NFR7.3: Excel 2016+ or compatible (openpyxl library)
- NFR7.4: KIS REST API (64-bit compatible)

### Additional Requirements

**From Architecture Document:**

- **API Integration**: KIS REST API integration replacing legacy 32-bit COM API
  - OAuth2 authentication with token caching
  - Access Token (24-hour expiry) and Approval Key for WebSocket
  - HTTP-based REST calls for order placement and market data
  - Cross-platform compatibility (64-bit Python)

- **Excel I/O Architecture**: Four-area Excel structure on Sheet 1
  - Area A: Settings (B12-B22) - 19 configuration fields
  - Area B: Program Info (H12-H22) - Real-time status display
  - Area C: Tier Table (C25:G264) - 240 tier position tracking
  - Area D: Simulation (I25:M264) - Projected buy/sell prices
  - Sheet 2: Append-only history log with 17 columns

- **Data Models**: Immutable frozen dataclasses for type safety
  - `Position`: tier, quantity, avg_price, invested_amount, opened_at
  - `TradeSignal`: action, tier, price, quantity, reason, tiers (batch), timestamp
  - `GridSettings`: 20+ configuration parameters from Excel

- **Logging and Monitoring**: Dual-output logging system
  - Console output with colored status messages (Korean/English)
  - File logging to `phoenix_trading.log` with timestamps
  - Excel history log for audit trail
  - Optional Telegram notifications

- **Retry and Resilience Patterns**:
  - API call retry: 3 attempts with exponential backoff
  - Excel save retry: 3 attempts with 1-second delay
  - Fill confirmation polling: 10 retries × 2 seconds = 20 seconds max
  - Token caching to reduce authentication overhead

- **Market Hours Handling**: Timezone-aware trading schedule
  - US Eastern Time (NYSE/AMEX/NASDAQ): 09:30-16:00
  - Korea Time conversion: 23:30 KST - 06:00 KST (next day)
  - Weekend detection and auto-pause
  - Monday market open auto-resume

### FR Coverage Map

- **FR1**: Epic 1 - System initialization and authentication
- **FR2**: Epic 2 - Tier 1 (High Water Mark) management
- **FR3**: Epic 2 - Price tier calculation (240 tiers)
- **FR4**: Epic 2 - Market data acquisition (SOXL real-time price)
- **FR5**: Epic 2 - Batch buy signal generation
- **FR6**: Epic 2 - Batch sell signal generation
- **FR7**: Epic 2 - Order execution (Buy) with limit orders
- **FR8**: Epic 2 - Order execution (Sell) with limit orders
- **FR9**: Epic 3 - Tier 1 custom trading mode (gap-up strategy)
- **FR10**: Epic 4 - Position management
- **FR11**: Epic 4 - Excel state persistence (4 areas + history log)
- **FR12**: Epic 5 - Trading hours management (US market hours)
- **FR13**: Epic 5 - Error handling and recovery
- **FR14**: Epic 5 - Telegram notifications
- **FR15**: Epic 1 - Graceful shutdown

**Coverage: 15/15 FRs mapped to epics** ✅

## Epic List

### Epic 1: 거래 시스템 설정 및 시작
**Goal**: Enable users to configure all settings via Excel file, connect to KIS brokerage account, and safely start/stop the automated trading system.

**User Outcomes:**
- Configure API keys, account number, and trading parameters in Excel template
- Authenticate with KIS REST API and obtain tokens
- Verify system initialization is complete
- Safely shutdown system with Ctrl+C

**FRs covered:** FR1, FR15
**NFRs addressed:** NFR3 (Security), NFR4 (Maintainability), NFR5 (Usability)

---

### Epic 2: 자동화된 240단계 그리드 거래
**Goal**: Enable users to automatically manage 240 price tiers for SOXL ETF, buying on dips and selling on bounces to realize profits.

**User Outcomes:**
- Automatic tracking and updating of Tier 1 (High Water Mark)
- Automatic calculation of buy/sell prices for 240 tiers
- Real-time SOXL price queries (40-second intervals)
- Batch buy signal generation (multiple tiers simultaneously)
- Batch sell signal generation (multiple tiers simultaneously)
- Slippage prevention through limit orders
- Order fill confirmation (20-second polling)
- Partial fill handling

**FRs covered:** FR2, FR3, FR4, FR5, FR6, FR7, FR8
**NFRs addressed:** NFR1 (Performance), NFR2 (Reliability), NFR6 (Scalability)

---

### Epic 3: 갭 상승 대응 전략 (Tier 1 커스텀 모드)
**Goal**: Enable users to capture profit opportunities from market gap-ups by trading at Tier 1 price level.

**User Outcomes:**
- Enable/disable Tier 1 trading via Excel settings
- Buy at specified percentage above Tier 1 when price gaps up
- Sell when +3% profit target reached from Tier 1 entry
- Capture gap-up profits

**FRs covered:** FR9
**NFRs addressed:** NFR4 (Maintainability - Excel configuration)

---

### Epic 4: 실시간 포지션 및 상태 추적
**Goal**: Enable users to view all tier-by-tier positions, trade history, and system status in real-time via Excel file with zero data loss.

**User Outcomes:**
- Track quantity, average price, invested amount for each tier
- Real-time updates of 4 Excel areas (Settings, Program Info, Tier Table, Simulation)
- All trade history recorded in Sheet 2 (append-only log)
- Retry logic when Excel file is locked (3 attempts)
- Accurate partial fill handling

**FRs covered:** FR10, FR11
**NFRs addressed:** NFR2 (Reliability - no data loss), NFR4 (Maintainability), NFR5 (Usability)

---

### Epic 5: 24/7 안정적 운영 및 원격 모니터링
**Goal**: Enable users to run the system unattended 24/7 with automatic US market hours detection, remote Telegram monitoring, and automatic recovery from all error conditions.

**User Outcomes:**
- Automatic US market hours detection (23:30-06:00 KST)
- Automatic weekend pause, Monday auto-resume
- Automatic retry on API call failures (3 attempts, exponential backoff)
- Automatic re-authentication on token expiry
- Automatic rate limiting handling (200ms delays)
- Telegram notifications (start/stop, buy/sell, Tier 1 updates, errors)
- Structured logging (console + file + Excel)

**FRs covered:** FR12, FR13, FR14
**NFRs addressed:** NFR2 (Reliability), NFR3 (Security - no credentials in logs), NFR4 (Maintainability - logging), NFR5 (Usability - Telegram)

---

## Epic 1: 거래 시스템 설정 및 시작

**Goal**: Enable users to configure all settings via Excel file, connect to KIS brokerage account, and safely start/stop the automated trading system.

### Story 1.1: Excel 설정 파일 로드 및 필수 필드 검증

As a **trader**,
I want **the system to load configuration from Excel file and validate all required fields**,
So that **I can ensure my trading parameters are correctly set before starting automated trading**.

**Acceptance Criteria:**

**Given** the Excel file `phoenix_grid_template_v3.xlsx` exists in the project directory
**When** the system initializes
**Then** the system reads all configuration from Sheet 1 "01_매매전략_기준설정"
**And** validates 19 required fields in cells B12-B22:
- B12: KIS APP KEY (not empty)
- B13: KIS APP SECRET (not empty)
- B14: Account number (not empty)
- B15: System enabled flag (TRUE/FALSE)
- B16: Telegram enabled (TRUE/FALSE)
- B17: Telegram bot token (if B16=TRUE)
- B18: Tier 1 price (numeric > 0)
- B19: Total capital (numeric > 0)
- B20: Tier 1 custom trading enabled (TRUE/FALSE)
- B21: Tier 1 buy percentage (numeric 0-100 if B20=TRUE)
- B22: Price check interval (numeric > 0)
**And** displays validation results in console with clear Korean/English messages
**And** returns InitStatus.ERROR_EXCEL (code 20) if file missing
**And** returns InitStatus.ERROR_API_KEY (code 21) if API keys missing

**Given** Excel B15 (System enabled) is set to FALSE
**When** the system initializes
**Then** the system displays "시스템 중지 상태 (B15=FALSE)" message
**And** returns InitStatus.STOPPED (code 10)
**And** exits gracefully without attempting authentication

---

### Story 1.2: KIS REST API OAuth2 인증 및 토큰 획득

As a **trader**,
I want **the system to authenticate with KIS REST API using my credentials**,
So that **I can execute real trades through my brokerage account**.

**Acceptance Criteria:**

**Given** valid KIS APP KEY and APP SECRET are loaded from Excel B12-B13
**When** the system performs authentication
**Then** the system sends OAuth2 token request to `https://openapi.koreainvestment.com:9443/oauth2/tokenP`
**And** includes request body:
```json
{
  "grant_type": "client_credentials",
  "appkey": "<B12 value>",
  "appsecret": "<B13 value>"
}
```
**And** receives Access Token with 24-hour expiry
**And** sends Approval Key request to `/oauth2/Approval`
**And** receives Approval Key for WebSocket authentication
**And** displays "✅ KIS API 인증 성공" in console

**Given** invalid API credentials are provided
**When** the system performs authentication
**Then** the system retries up to 3 times with exponential backoff (1s, 2s, 4s)
**And** displays error message "❌ KIS API 인증 실패: [error details]"
**And** returns InitStatus.ERROR_LOGIN (code 22)
**And** exits without proceeding to trading

---

### Story 1.3: 토큰 캐싱 및 재사용

As a **trader**,
I want **the system to cache authentication tokens and reuse them**,
So that **I avoid unnecessary authentication calls and reduce API rate limiting**.

**Acceptance Criteria:**

**Given** successful authentication with Access Token and Approval Key
**When** the system receives tokens
**Then** the system saves tokens to `kis_token_cache.json` with structure:
```json
{
  "access_token": "<token>",
  "access_token_expires_at": "<ISO 8601 timestamp>",
  "approval_key": "<key>",
  "cached_at": "<ISO 8601 timestamp>"
}
```
**And** sets file permissions to user read/write only (NFR3.2)
**And** displays "토큰 캐시 저장 완료" message

**Given** `kis_token_cache.json` exists with valid unexpired token
**When** the system initializes on subsequent runs
**Then** the system reads cached token
**And** checks if `access_token_expires_at` > current time
**And** reuses cached token without re-authentication
**And** displays "캐시된 토큰 재사용 (만료: [timestamp])" message
**And** skips OAuth2 authentication flow

**Given** cached token is expired (current time >= expires_at)
**When** the system checks cache
**Then** the system performs new authentication (Story 1.2)
**And** overwrites `kis_token_cache.json` with new tokens

---

### Story 1.4: 시스템 초기화 완료 확인 및 상태 표시

As a **trader**,
I want **clear confirmation that system initialization is complete and trading is ready**,
So that **I know the system is operating correctly before leaving it unattended**.

**Acceptance Criteria:**

**Given** all initialization steps are successful (Excel loaded, KIS authenticated, tokens cached)
**When** the system completes 9-step initialization process:
1. Excel file validation
2. Excel settings load
3. System enabled check (B15=TRUE)
4. KIS API key validation
5. GridEngine initialization
6. KIS API login
7. Initial price query
8. Account balance query
9. Telegram initialization (if enabled)
**Then** the system displays initialization summary:
```
========================================
✅ Phoenix Trading System 초기화 완료
========================================
[19:00:05] 1/9 Excel 파일 로드 완료
[19:00:06] 2/9 설정 검증 완료 (19개 필드)
[19:00:06] 3/9 시스템 활성화 확인 (B15=TRUE)
[19:00:07] 4/9 KIS API 키 검증 완료
[19:00:07] 5/9 Grid Engine 초기화 완료
[19:00:10] 6/9 KIS API 로그인 완료
[19:00:12] 7/9 SOXL 현재가 조회: $45.23
[19:00:13] 8/9 계좌 잔고 조회: $10,000.00
[19:00:14] 9/9 텔레그램 알림 초기화 완료
========================================
🚀 자동매매 시작 준비 완료
========================================
```
**And** returns InitStatus.SUCCESS (code 0)
**And** sends Telegram notification (if enabled): "🚀 Phoenix Trading System 시작됨"

**Given** any initialization step fails (e.g., price query fails)
**When** the system encounters the failure
**Then** the system displays specific error:
- InitStatus.ERROR_PRICE (code 23) for price query failure
- InitStatus.ERROR_BALANCE (code 24) for balance query failure
**And** shows at which step initialization failed
**And** exits gracefully without starting trading loop

---

### Story 1.5: 안전한 종료 (SIGINT/SIGTERM 처리)

As a **trader**,
I want **the system to handle Ctrl+C and shutdown signals gracefully**,
So that **all positions and state are saved before the system stops**.

**Acceptance Criteria:**

**Given** the system is running in the main trading loop
**When** the user presses Ctrl+C (SIGINT signal)
**Then** the system catches the signal
**And** displays "🛑 종료 신호 수신 중... 안전하게 종료합니다"
**And** executes shutdown sequence:
1. Stop accepting new trading signals
2. Wait for any in-flight orders to complete (max 30 seconds)
3. Save final state to Excel (all 4 areas)
4. Save final Excel workbook with retry logic (3 attempts)
5. Close KIS API connection
6. Flush all logs to `phoenix_trading.log`
**And** displays "✅ 모든 상태 저장 완료"
**And** sends Telegram notification (if enabled): "🛑 Phoenix Trading System 종료됨"
**And** exits with status code 0

**Given** the system receives SIGTERM signal (system shutdown)
**When** the signal is received
**Then** the system executes the same graceful shutdown sequence
**And** exits with status code 0

**Given** Excel file is locked during shutdown
**When** the system tries to save final state
**Then** the system retries up to 3 times with 1-second delay
**And** displays warning "⚠️  Excel 파일 잠금: 재시도 중 ([attempt]/3)"
**And** if all retries fail, displays "❌ Excel 저장 실패: 파일이 잠겨 있습니다"
**And** exits with status code 1 (indicating incomplete shutdown)

---

## Epic 2: 자동화된 240단계 그리드 거래

**Goal**: Enable users to automatically manage 240 price tiers for SOXL ETF, buying on dips and selling on bounces to realize profits.

### Story 2.1: Tier 1 (High Water Mark) 초기화 및 자동 갱신

As a **trader**,
I want **the system to automatically track and update the highest price (Tier 1) observed**,
So that **my grid trading always adapts to new market highs and maximizes profit opportunities**.

**Acceptance Criteria:**

**Given** the system is initializing for the first time (no Tier 1 in Excel B18)
**When** the system queries SOXL current price (e.g., $45.50)
**Then** the system sets Tier 1 price = current price ($45.50)
**And** saves Tier 1 to Excel B18
**And** displays "Tier 1 초기화: $45.50 (현재가 기준)"
**And** all subsequent tier calculations use this as baseline

**Given** the system is running with Tier 1 = $45.50
**When** current price rises to $46.20 (new high)
**Then** the system detects current_price > Tier 1
**And** updates Tier 1 = $46.20
**And** saves new Tier 1 to Excel B18
**And** recalculates all 240 tier prices based on new Tier 1
**And** displays "🔼 Tier 1 갱신: $45.50 → $46.20 (+$0.70)"
**And** sends Telegram notification (if enabled): "Tier 1 신고가 갱신: $46.20"

**Given** all positions are cleared (no holdings across all 240 tiers)
**When** current price is $47.00
**Then** the system automatically updates Tier 1 = $47.00
**And** resets grid to new baseline
**And** displays "✅ 전체 청산 완료 → Tier 1 갱신: $47.00"

**Given** the system has positions in Tier 10, 15, 20
**When** current price rises above Tier 1
**Then** the system does NOT update Tier 1 (positions still held)
**And** waits for all positions to be sold before updating

---

### Story 2.2: 240개 티어 가격 계산 및 Excel 테이블 저장

As a **trader**,
I want **the system to calculate buy and sell prices for all 240 tiers and display them in Excel**,
So that **I can visualize the entire grid structure and verify price levels**.

**Acceptance Criteria:**

**Given** Tier 1 price = $50.00
**When** the system calculates tier prices
**Then** the system applies formula for each tier N (1 to 240):
- Tier N buy price = `Tier1 × (1 - (N-1) × 0.005)`
- Tier N sell price = `Tier N buy price × 1.03` (+3% profit)
**And** tier prices are calculated as:
```
Tier 1:  Buy $50.00, Sell $51.50 (Tier 1 × 1.03)
Tier 2:  Buy $49.75 (50 × 0.995), Sell $51.24
Tier 3:  Buy $49.50 (50 × 0.990), Sell $50.99
...
Tier 240: Buy $10.05 (50 × 0.4025), Sell $10.35
```
**And** displays calculation summary in console:
```
Grid 계산 완료:
  Tier 1:   $50.00 (High Water Mark)
  Tier 240: $10.05 (최대 하락 -79.9%)
  간격:     0.5% per tier
  목표수익: +3.0% per tier
```

**Given** tier prices are calculated
**When** the system updates Excel Sheet 1
**Then** the system writes 240 rows to cells C25:G264:
- Column C (Tier): 1, 2, 3, ..., 240
- Column D (Buy Price): Calculated buy prices
- Column E (Sell Price): Calculated sell prices
- Column F (Quantity): Empty (filled on buy)
- Column G (Avg Price): Empty (filled on buy)
**And** saves Excel workbook
**And** displays "Excel 티어 테이블 업데이트 완료 (240 tiers)"

**Given** Tier 1 is updated from $50.00 to $52.00
**When** recalculation is triggered
**Then** all 240 tier prices are recalculated with new baseline
**And** Excel C25:G264 is updated with new prices
**And** existing position prices remain unchanged (Column G)
**And** displays "Tier 1 갱신 → 240개 티어 재계산 완료"

---

### Story 2.3: SOXL 실시간 시세 조회 및 거래소 자동 감지

As a **trader**,
I want **the system to query SOXL real-time price every 40 seconds with automatic exchange detection**,
So that **I receive accurate market data regardless of which exchange SOXL trades on**.

**Acceptance Criteria:**

**Given** the system is configured with ticker = "SOXL" and price_check_interval = 40 seconds
**When** the system queries current price
**Then** the system attempts exchanges in order: ["NAS", "AMS", "NYS"]
**And** sends KIS API request to `/uapi/overseas-price/v1/quotations/price`
**And** includes headers:
- tr_id: "HHDFS00000300" (for overseas stock price)
- Authorization: "Bearer {access_token}"
**And** includes query params:
- AUTH: (empty for stock)
- EXCD: "NAS" (first attempt)
- SYMB: "SOXL"

**Given** SOXL is found on AMEX exchange (EXCD=AMS)
**When** NAS returns no data and AMS returns valid price
**Then** the system caches exchange = "AMS" for future queries
**And** receives response with current price (e.g., $45.23)
**And** displays "[23:31:45] SOXL 현재가 조회: $45.23 (AMS)"
**And** updates current_price in GridEngine

**Given** API request fails (network error, timeout)
**When** the query is attempted
**Then** the system retries up to 3 times with exponential backoff (1s, 2s, 4s)
**And** displays "⚠️  시세 조회 실패: 재시도 중 ([attempt]/3)"
**And** if all retries fail, logs error and waits for next polling interval
**And** does NOT crash or stop trading loop

**Given** rate limiting is encountered (5 requests/second limit)
**When** the system makes rapid API calls
**Then** the system enforces 200ms minimum interval between calls
**And** displays "⏱️  Rate limiting: 200ms 대기 중"
**And** waits before next request

**Given** price query is successful every 40 seconds
**When** the system is running
**Then** console displays price updates:
```
[23:31:45] SOXL $45.23 | Tier 1: $50.00 | Positions: 5 tiers
[23:32:25] SOXL $45.10 | Tier 1: $50.00 | Positions: 5 tiers
[23:33:05] SOXL $45.35 | Tier 1: $50.00 | Positions: 5 tiers
```

---

### Story 2.4: 배치 매수 신호 생성 (여러 티어 동시)

As a **trader**,
I want **the system to identify all eligible tiers for buying in a single price check**,
So that **I maximize efficiency by placing multiple tier orders simultaneously**.

**Acceptance Criteria:**

**Given** Tier 1 = $50.00, current price = $48.50, no positions held
**When** the system processes tick in GridEngine.process_tick()
**Then** the system identifies all tiers where:
- `tier_buy_price >= current_price` (price has fallen to or below tier level)
- `tier has no existing position`
**And** eligible tiers are: Tier 4 ($49.25), Tier 5 ($49.00), Tier 6 ($48.75), Tier 7 ($48.50)
**And** generates TradeSignal:
```python
TradeSignal(
  action="BUY",
  tier=4,  # Lowest eligible tier
  price=48.50,  # Current price (limit order price)
  quantity=calculated_from_tier_investment,
  reason="Batch buy: 4 tiers eligible",
  tiers=(4, 5, 6, 7),  # All tiers in batch
  timestamp=datetime.now()
)
```
**And** displays "📊 배치 매수 신호: 4개 티어 (Tier 4-7) @ $48.50"

**Given** Tier 240 already has a position (last tier filled)
**When** current price falls further
**Then** the system generates NO buy signal
**And** displays "⚠️  Tier 240 도달: 추가 매수 중단"
**And** continues monitoring for sell signals only

**Given** current price = $49.80, Tier 2 buy price = $49.75, Tier 2 has no position
**When** the system processes tick
**Then** the system generates buy signal for Tier 2 only
**And** displays "📊 매수 신호: Tier 2 @ $49.80"

**Given** all eligible tiers already have positions
**When** current price falls
**Then** the system generates NO buy signal
**And** displays "✓ 모든 해당 티어 보유 중"

---

### Story 2.5: 지정가 매수 주문 실행 및 체결 확인

As a **trader**,
I want **the system to execute buy orders as limit orders and wait for fill confirmation**,
So that **I avoid slippage and ensure orders are filled at my target price or better**.

**Acceptance Criteria:**

**Given** a buy signal for Tier 5 at current price $49.00
**When** the system executes the buy order
**Then** the system calculates quantity:
- `quantity = tier_investment_amount / current_price`
- Example: $500 / $49.00 = 10.20 shares → rounds to 10 shares
**And** places limit buy order via KIS API `/uapi/overseas-stock/v1/trading/order`:
```json
{
  "CANO": "<account_number>",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "AMS",
  "PDNO": "SOXL",
  "ORD_QTY": "10",
  "OVRS_ORD_UNPR": "49.00",
  "ORD_SVR_DVSN_CD": "0",
  "ORD_DVSN": "00"  # Limit order
}
```
**And** receives order ID (e.g., "KR1234567890")
**And** displays "[23:32:10] ⬇️  매수 주문: Tier 5, 10 shares @ $49.00 (주문번호: KR1234567890)"

**Given** order is placed with ID "KR1234567890"
**When** the system waits for fill confirmation
**Then** the system polls order status every 2 seconds (max 10 retries = 20 seconds)
**And** sends GET request to `/uapi/overseas-stock/v1/trading/inquire-ccnl`
**And** checks if order is filled (status = "02")
**And** retrieves fill details:
- Filled quantity: 10 shares
- Average fill price: $48.95 (at or below limit price $49.00)

**Given** order is filled: 10 shares @ $48.95
**When** fill confirmation is received
**Then** the system calls GridEngine.execute_buy(tier=5, quantity=10, avg_price=48.95)
**And** creates Position object:
```python
Position(
  tier=5,
  quantity=10,
  avg_price=48.95,
  invested_amount=489.50,
  opened_at=datetime.now()
)
```
**And** updates Excel Column F (Quantity) = 10, Column G (Avg Price) = $48.95 for Tier 5 row
**And** displays "[23:32:14] ✅ 매수 체결: Tier 5, 10 shares @ $48.95 (투자: $489.50)"
**And** sends Telegram notification (if enabled): "매수 완료: Tier 5, 10주 @ $48.95"

**Given** order is partially filled (6 shares out of 10)
**When** fill confirmation is received after 20 seconds
**Then** the system accepts partial fill
**And** creates Position with quantity=6
**And** displays "[23:32:30] ⚠️  부분 체결: Tier 5, 6/10 shares @ $48.96"
**And** Story 2.8 handles distribution logic

**Given** fill confirmation polling times out (20 seconds elapsed)
**When** no fill confirmation is received
**Then** the system logs warning "⚠️  체결 확인 타임아웃: 주문번호 KR1234567890"
**And** continues trading (does not crash)
**And** next tick will re-evaluate if buy signal needed

---

### Story 2.6: 배치 매도 신호 생성 (여러 티어 동시)

As a **trader**,
I want **the system to identify all eligible tiers for selling in a single price check**,
So that **I realize profits across multiple tiers simultaneously when price bounces**.

**Acceptance Criteria:**

**Given** positions held at Tier 10 (buy $47.50, sell $48.93), Tier 15 (buy $46.63, sell $48.03), Tier 20 (buy $45.75, sell $47.12)
**When** current price rises to $49.00
**Then** the system identifies all tiers where:
- `current_price >= tier_sell_price`
- `tier has existing position`
**And** eligible tiers are: Tier 10 ($48.93), Tier 15 ($48.03)
**And** generates TradeSignal:
```python
TradeSignal(
  action="SELL",
  tier=10,  # Lowest eligible tier
  price=49.00,  # Current price (limit order price)
  quantity=sum_of_all_quantities,
  reason="Batch sell: 2 tiers profitable",
  tiers=(10, 15),
  timestamp=datetime.now()
)
```
**And** displays "📊 배치 매도 신호: 2개 티어 (Tier 10, 15) @ $49.00"

**Given** current price = $48.50, Tier 15 sell price = $48.03, Tier 15 has 8 shares
**When** the system processes tick
**Then** the system generates sell signal for Tier 15 only
**And** displays "📊 매도 신호: Tier 15, 8 shares @ $48.50 (수익: +$3.76)"

**Given** all positions are sold (no holdings)
**When** current price rises
**Then** the system generates NO sell signal
**And** checks if Tier 1 should be updated (Story 2.1)
**And** displays "✅ 전체 청산 완료 → Tier 1 갱신 대기"

**Given** current price is below all tier sell prices
**When** the system processes tick
**Then** the system generates NO sell signal
**And** displays "✓ 매도 조건 미달: 반등 대기 중"

---

### Story 2.7: 지정가 매도 주문 실행 및 체결 확인

As a **trader**,
I want **the system to execute sell orders as limit orders and confirm fills**,
So that **I secure my +3% profit target and avoid selling below target price**.

**Acceptance Criteria:**

**Given** a sell signal for Tier 10 with 12 shares at current price $49.20
**When** the system executes the sell order
**Then** the system retrieves position quantity from held Position object (12 shares)
**And** places limit sell order via KIS API:
```json
{
  "CANO": "<account_number>",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "AMS",
  "PDNO": "SOXL",
  "ORD_QTY": "12",
  "OVRS_ORD_UNPR": "49.20",
  "ORD_SVR_DVSN_CD": "0",
  "ORD_DVSN": "00"  # Limit order
}
```
**And** receives order ID
**And** displays "[23:45:10] ⬆️  매도 주문: Tier 10, 12 shares @ $49.20 (주문번호: KR9876543210)"

**Given** sell order is placed
**When** the system waits for fill confirmation
**Then** the system polls order status every 2 seconds (max 10 retries)
**And** checks fill status via `/uapi/overseas-stock/v1/trading/inquire-ccnl`

**Given** order is filled: 12 shares @ $49.25 (at or above limit price $49.20)
**When** fill confirmation is received
**Then** the system calculates profit:
- Buy cost: 12 × $47.80 = $573.60
- Sell proceeds: 12 × $49.25 = $591.00
- Profit: $591.00 - $573.60 = $17.40 (+3.04%)
**And** calls GridEngine.execute_sell(tier=10)
**And** removes Position object for Tier 10
**And** updates Excel: clears Column F (Quantity) and Column G (Avg Price) for Tier 10
**And** displays "[23:45:14] ✅ 매도 체결: Tier 10, 12 shares @ $49.25 | 수익: +$17.40 (+3.04%)"
**And** sends Telegram notification: "매도 완료: Tier 10, 12주 @ $49.25, 수익 $17.40"

**Given** all positions are sold (last position cleared)
**When** sell is executed
**Then** the system checks if all 240 tiers are empty
**And** triggers Tier 1 update to current price (Story 2.1)
**And** displays "🎉 전체 청산 완료 → Tier 1 갱신 준비"

**Given** sell order partially fills (8 shares out of 12)
**When** timeout occurs after 20 seconds
**Then** the system accepts partial fill
**And** updates Position to remaining quantity (4 shares)
**And** displays "[23:45:30] ⚠️  부분 체결: Tier 10, 8/12 shares @ $49.26 (4 shares 보유 유지)"

---

### Story 2.8: 부분 체결 처리 (배치 주문)

As a **trader**,
I want **the system to correctly handle partial fills when batch orders are placed**,
So that **my position tracking remains accurate even with incomplete order fills**.

**Acceptance Criteria:**

**Given** batch buy signal for Tiers 5, 6, 7 (total 30 shares: 10 + 10 + 10)
**When** order is placed for 30 shares but only 18 shares are filled
**Then** the system distributes filled quantity across tiers proportionally:
- Tier 5: 6 shares (10/30 × 18 = 6)
- Tier 6: 6 shares
- Tier 7: 6 shares
**And** creates 3 Position objects with 6 shares each
**And** updates Excel rows for Tiers 5, 6, 7 with quantity=6
**And** displays "[23:33:20] ⚠️  부분 체결 (배치): 18/30 shares → Tier 5-7 각 6주"

**Given** batch buy signal for Tiers 10, 11 (total 20 shares)
**When** only 7 shares are filled (less than per-tier quantity)
**Then** the system assigns all filled shares to first tier:
- Tier 10: 7 shares
- Tier 11: 0 shares (no position created)
**And** displays "[23:34:10] ⚠️  부분 체결 (소량): 7 shares → Tier 10만 할당"

**Given** batch sell signal for Tiers 15, 20 (positions: 12 + 8 = 20 shares)
**When** order is placed for 20 shares but only 12 shares are filled
**Then** the system assumes Tier 15 fully sold (12 shares)
**And** Tier 20 position remains (8 shares)
**And** displays "[23:40:15] ⚠️  부분 체결 (매도): Tier 15 청산, Tier 20 보유 유지"

**Given** any partial fill occurs
**When** position is updated
**Then** the system logs to Excel Sheet 2 history log:
```
[Timestamp] | SOXL | Tier 5-7 | Partial Fill | Buy | 18/30 shares | $48.50 | ...
```
**And** ensures accurate position count for next tick processing

---

## Epic 3: 갭 상승 대응 전략 (Tier 1 커스텀 모드)

**Goal**: Enable users to capture profit opportunities from market gap-ups by trading at Tier 1 price level.

### Story 3.1: Tier 1 커스텀 모드 활성화 및 설정 관리

As a **trader**,
I want **to enable or disable Tier 1 custom trading mode via Excel settings**,
So that **I can decide whether to trade gap-up scenarios based on my risk tolerance**.

**Acceptance Criteria:**

**Given** Excel B20 (Tier 1 custom trading enabled) = TRUE
**When** the system loads settings
**Then** the system enables Tier 1 custom trading mode
**And** reads B21 (Tier 1 buy percentage) = 10.0 (example: 10% of capital)
**And** validates B21 is between 0 and 100
**And** displays "✅ Tier 1 커스텀 모드 활성화 (매수 비율: 10%)"
**And** sets GridSettings.tier1_trading_enabled = True
**And** sets GridSettings.tier1_buy_percent = 0.10

**Given** Excel B20 = FALSE
**When** the system loads settings
**Then** the system disables Tier 1 custom trading mode
**And** displays "Tier 1 커스텀 모드: 비활성화"
**And** ignores B21 value
**And** skips Tier 1 gap-up trading logic entirely

**Given** B20 = TRUE but B21 is invalid (e.g., -5 or 150)
**When** the system validates settings
**Then** the system displays error "❌ B21 값 오류: Tier 1 매수 비율은 0-100 범위여야 합니다"
**And** returns InitStatus.ERROR_EXCEL (code 20)
**And** exits without starting trading

---

### Story 3.2: 갭 상승 시 Tier 1 매수 신호 생성 및 실행

As a **trader**,
I want **the system to buy at Tier 1 price when market gaps up above Tier 1**,
So that **I can profit from gap-up momentum before price potentially reverses**.

**Acceptance Criteria:**

**Given** Tier 1 = $50.00, Tier 1 custom mode enabled, buy percent = 10%, capital = $10,000
**When** current price = $51.00 (2% above Tier 1) and no Tier 1 position exists
**Then** the system checks condition: `current_price > Tier1 × (1 + buy_percent/100)`
**And** calculates: $51.00 > $50.00 × 1.10 = $55.00? → NO
**And** generates NO buy signal (gap not large enough)

**Given** current price = $56.00 (12% above Tier 1)
**When** gap-up condition is met: $56.00 > $55.00
**Then** the system generates Tier 1 buy signal:
```python
TradeSignal(
  action="BUY",
  tier=1,  # Special: Tier 1 position
  price=50.00,  # Tier 1 designated price (NOT current price)
  quantity=calculated_from_capital,
  reason="Tier 1 gap-up trading",
  timestamp=datetime.now()
)
```
**And** calculates investment: $10,000 × 10% = $1,000
**And** calculates quantity: $1,000 / $50.00 = 20 shares
**And** displays "🔥 Tier 1 갭 상승 매수: 20 shares @ $50.00 (현재가: $56.00)"

**Given** Tier 1 buy signal is generated
**When** the system places order
**Then** the system places limit buy order at Tier 1 price ($50.00, NOT current price $56.00)
**And** waits for fill confirmation (20 seconds polling)
**And** if filled, creates Position with tier=1
**And** displays "[02:15:20] ✅ Tier 1 매수 체결: 20 shares @ $50.05"
**And** sends Telegram notification: "Tier 1 갭 상승 매수 완료: 20주 @ $50.05"

**Given** Tier 1 position already exists
**When** another gap-up occurs
**Then** the system generates NO additional Tier 1 buy signal
**And** displays "✓ Tier 1 포지션 보유 중 (추가 매수 없음)"

---

### Story 3.3: Tier 1 포지션 매도 및 수익 실현

As a **trader**,
I want **the system to sell Tier 1 position when price reaches +3% profit target**,
So that **I secure gap-up profits consistent with my grid trading strategy**.

**Acceptance Criteria:**

**Given** Tier 1 position: 20 shares @ $50.05, Tier 1 sell price = $50.05 × 1.03 = $51.55
**When** current price rises to $51.60
**Then** the system generates Tier 1 sell signal (current_price >= sell_price)
**And** displays "📊 Tier 1 매도 신호: 20 shares @ $51.60 (목표: $51.55)"

**Given** Tier 1 sell signal is generated
**When** the system places sell order
**Then** the system places limit sell order at current price ($51.60)
**And** waits for fill confirmation
**And** if filled at $51.62, calculates profit:
- Buy cost: 20 × $50.05 = $1,001.00
- Sell proceeds: 20 × $51.62 = $1,032.40
- Profit: $31.40 (+3.14%)
**And** removes Tier 1 Position
**And** displays "[02:45:30] ✅ Tier 1 매도 체결: 20 shares @ $51.62 | 수익: +$31.40 (+3.14%)"
**And** sends Telegram notification: "Tier 1 매도 완료: 20주 @ $51.62, 수익 $31.40 🎉"

**Given** Tier 1 position is sold
**When** the system continues trading
**Then** Tier 1 custom mode remains enabled
**And** system monitors for next gap-up opportunity
**And** can create new Tier 1 position on future gap-ups

**Given** Tier 1 custom mode = FALSE
**When** any gap-up occurs
**Then** the system never generates Tier 1 buy/sell signals
**And** only regular grid tiers (2-240) are traded

---

## Epic 4: 실시간 포지션 및 상태 추적

**Goal**: Enable users to view all tier-by-tier positions, trade history, and system status in real-time via Excel file with zero data loss.

### Story 4.1: 포지션 데이터 모델 및 추적

As a **trader**,
I want **the system to track each position with complete details using immutable data structures**,
So that **position data is accurate and cannot be accidentally modified**.

**Acceptance Criteria:**

**Given** a buy order is filled for Tier 5: 10 shares @ $49.00
**When** the system creates position
**Then** the system creates frozen dataclass Position:
```python
@dataclass(frozen=True)
class Position:
    tier: int = 5
    quantity: int = 10
    avg_price: float = 49.00
    invested_amount: float = 490.00
    opened_at: datetime = datetime(2026, 1, 24, 23, 32, 14)
```
**And** adds Position to GridEngine.positions list
**And** Position object is immutable (cannot be modified after creation)

**Given** position tracking is active
**When** multiple tiers have positions (Tier 5, 10, 15)
**Then** the system maintains positions list with 3 Position objects
**And** can query position by tier: `get_position(tier=10)` returns Position(tier=10, ...)
**And** can calculate total positions: `len(positions)` = 3
**And** can calculate total invested: sum of all `invested_amount` values

**Given** Tier 10 position is sold
**When** the system removes position
**Then** the system creates new positions list without Tier 10
**And** Position object is not modified (immutable pattern)
**And** displays position count update: "Positions: 2 tiers (Tier 5, 15)"

---

### Story 4.2: Excel 4개 영역 실시간 업데이트

As a **trader**,
I want **the system to update all 4 Excel areas on every state change**,
So that **I can monitor the system by simply refreshing Excel file**.

**Acceptance Criteria:**

**Given** the system state changes (buy/sell execution, Tier 1 update)
**When** the system updates Excel
**Then** the system writes to 4 areas on Sheet 1 "01_매매전략_기준설정":

**Area A: Settings (B12-B22) - Read-only for system**
- No changes written by system
- User configures these manually

**Area B: Program Info (H12-H22) - Real-time status**
```
H12: Last Update Time = "2026-01-24 23:45:30"
H13: Current Tier = "5, 10, 15" (comma-separated list)
H14: Current Price = "$48.50"
H15: Account Balance = "$9,200.00"
H16: Total Quantity = "28 shares" (sum across all positions)
H17: Buy Status = "Monitoring" or "Order Placed"
H18: Sell Status = "Monitoring" or "Profit Target Met"
```

**Area C: Tier Table (C25:G264) - 240 tier rows**
For each tier row (example Tier 5 at row 29):
```
C29: Tier = 5
D29: Buy Price = $49.00 (calculated from Tier 1)
E29: Sell Price = $50.47 (buy price × 1.03)
F29: Quantity = 10 (if position held, else empty)
G29: Avg Price = $49.00 (if position held, else empty)
```

**Area D: Simulation (I25:M264) - Projected prices**
For each tier:
```
I29: Tier = 5
J29: Simulated Buy = $49.00
K29: Simulated Sell = $50.47
L29: Projected Profit = "$14.70" (if fully filled)
M29: Status = "Holding" or "Available"
```

**And** saves Excel workbook after updates
**And** displays "Excel 업데이트 완료 (4 areas)"

**Given** Excel file is locked (user has it open)
**When** the system tries to save
**Then** the system retries up to 3 times with 1-second delay
**And** displays "⚠️  Excel 잠금: 재시도 중 (1/3)"
**And** if successful on retry, displays "✅ Excel 저장 성공 (재시도 2회)"
**And** if all retries fail, logs error but continues trading
**And** displays "❌ Excel 저장 실패: 다음 틱에 재시도"

---

### Story 4.3: Excel Sheet 2 거래 히스토리 로그

As a **trader**,
I want **every trade and system event logged to Sheet 2 with full details**,
So that **I have a complete audit trail of all trading activity**.

**Acceptance Criteria:**

**Given** a buy order is executed and filled
**When** the system logs the trade
**Then** the system appends row to Sheet 2 "02_운용로그_히스토리" with 17 columns:
```
Col 1:  Update Time = "2026-01-24 23:32:14"
Col 2:  Date = "2026-01-24"
Col 3:  Sheet = "Sheet1"
Col 4:  Ticker = "SOXL"
Col 5:  Tier = "5"
Col 6:  Action = "BUY"
Col 7:  Quantity = "10"
Col 8:  Price = "$49.00"
Col 9:  Invested = "$490.00"
Col 10: Tier 1 = "$50.00"
Col 11: Current Price = "$48.95"
Col 12: Positions Count = "3"
Col 13: Total Invested = "$1,450.00"
Col 14: Balance = "$8,550.00"
Col 15: Reason = "Batch buy: Tier 5"
Col 16: Order ID = "KR1234567890"
Col 17: Status = "Filled"
```
**And** history log is append-only (never modified)
**And** each log entry has unique timestamp

**Given** a sell order is executed with profit
**When** the system logs the sell
**Then** the system appends sell log with additional profit column:
```
Col 18: Profit = "$15.20"
Col 19: Profit % = "+3.1%"
```

**Given** Tier 1 is updated
**When** the system logs event
**Then** the system appends log with Action = "TIER1_UPDATE":
```
Tier = "1"
Action = "TIER1_UPDATE"
Reason = "New high observed"
Col 10: Old Tier 1 = "$50.00"
Col 11: New Tier 1 = "$51.50"
```

**Given** Sheet 2 reaches 10,000 rows
**When** system continues logging
**Then** the system continues appending (no row limit enforcement)
**And** displays "⚠️  히스토리 로그: 10,000+ rows (성능 저하 가능)"

---

### Story 4.4: 부분 체결 정확한 처리 및 추적

As a **trader**,
I want **the system to accurately handle partial fills and update positions correctly**,
So that **my position tracking matches actual holdings in my brokerage account**.

**Acceptance Criteria:**

**Given** batch buy order for Tiers 5, 6, 7 (30 shares total) is partially filled with 18 shares
**When** the system processes partial fill
**Then** the system distributes 18 shares proportionally:
- Tier 5: 6 shares (creates Position)
- Tier 6: 6 shares (creates Position)
- Tier 7: 6 shares (creates Position)
**And** updates Excel F/G columns for all 3 tiers
**And** logs partial fill event to Sheet 2:
```
Action = "PARTIAL_FILL"
Quantity = "18/30"
Reason = "Batch buy partial: distributed across 3 tiers"
```
**And** displays "[23:33:20] ⚠️  부분 체결: 18/30 shares → Tier 5-7 각 6주 할당"

**Given** single tier buy order (Tier 10, 10 shares) is partially filled with 6 shares
**When** the system processes fill
**Then** the system creates Position(tier=10, quantity=6)
**And** Excel row for Tier 10 shows quantity=6
**And** does NOT create positions for other tiers
**And** logs: "PARTIAL_FILL: Tier 10, 6/10 shares"

**Given** partial fill occurs on sell order (8 shares sold out of 12)
**When** the system updates position
**Then** the system updates Position to remaining quantity (4 shares)
**And** Excel shows Tier position with quantity=4
**And** logs partial sell to Sheet 2
**And** displays remaining shares: "⚠️  부분 매도: 8/12 shares, 4주 보유 유지"

---

## Epic 5: 24/7 안정적 운영 및 원격 모니터링

**Goal**: Enable users to run the system unattended 24/7 with automatic US market hours detection, remote Telegram monitoring, and automatic recovery from all error conditions.

### Story 5.1: 미국 시장 시간 자동 감지 및 거래 일시정지

As a **trader**,
I want **the system to automatically detect US market hours and pause trading when market is closed**,
So that **I don't waste resources querying prices during non-trading hours**.

**Acceptance Criteria:**

**Given** current Korea time is 23:30 (Friday, Jan 24, 2026)
**When** the system checks market hours
**Then** the system converts to US Eastern Time: 09:30 EST (Friday)
**And** detects market is OPEN (09:30-16:00 EST weekdays)
**And** displays "🟢 시장 개장: 거래 활성화 (09:30 EST)"
**And** continues trading loop

**Given** current Korea time is 06:10 (Saturday, Jan 25, 2026)
**When** the system checks market hours
**Then** the system converts to 16:10 EST (Friday)
**And** detects market is CLOSED (after 16:00 EST)
**And** displays "🔴 시장 마감: 거래 일시정지 (16:10 EST)"
**And** pauses trading loop
**And** sleeps until next market open
**And** displays "⏰ 다음 개장: 월요일 23:30 KST (09:30 EST)"

**Given** current Korea time is Sunday 15:00
**When** the system checks market hours
**Then** the system detects weekend (Saturday/Sunday)
**And** displays "🔴 주말: 거래 중단"
**And** calculates time until Monday 23:30 KST
**And** sleeps for calculated duration
**And** displays "⏰ 월요일 개장까지: 32시간 30분"

**Given** Monday 23:30 KST arrives
**When** the system wakes from sleep
**Then** the system displays "🟢 시장 개장: 거래 재개 (월요일 09:30 EST)"
**And** resumes trading loop
**And** sends Telegram notification: "시장 개장 - 자동매매 재개"

---

### Story 5.2: API 호출 실패 자동 재시도 및 복구

As a **trader**,
I want **the system to automatically retry failed API calls with exponential backoff**,
So that **temporary network issues don't stop my trading system**.

**Acceptance Criteria:**

**Given** API call to query price fails with network timeout
**When** the first attempt fails
**Then** the system logs error: "⚠️  API 호출 실패 (시도 1/3): Timeout"
**And** waits 1 second (exponential backoff: 2^0 = 1s)
**And** retries the API call

**Given** second attempt also fails
**When** retry is executed
**Then** the system logs: "⚠️  API 호출 실패 (시도 2/3): Timeout"
**And** waits 2 seconds (2^1 = 2s)
**And** retries again

**Given** third attempt succeeds
**When** API returns valid data
**Then** the system logs: "✅ API 호출 성공 (재시도 2회 후)"
**And** continues normal operation
**And** does NOT crash or stop trading

**Given** all 3 attempts fail
**When** maximum retries exhausted
**Then** the system logs: "❌ API 호출 실패 (3회 재시도 실패): 다음 틱 대기"
**And** skips current tick
**And** waits for next polling interval (40 seconds)
**And** tries again on next tick
**And** does NOT exit or crash

**Given** rate limiting error (429 status code) is received
**When** the system detects rate limit
**Then** the system waits 200ms before retry
**And** displays "⏱️  Rate limiting 감지: 200ms 대기"
**And** enforces minimum 200ms between all API calls going forward

---

### Story 5.3: 토큰 만료 시 자동 재인증

As a **trader**,
I want **the system to automatically re-authenticate when access token expires**,
So that **trading continues uninterrupted beyond the 24-hour token lifetime**.

**Acceptance Criteria:**

**Given** access token expires after 24 hours
**When** the system makes API call with expired token
**Then** KIS API returns 401 Unauthorized error
**And** the system detects token expiry
**And** displays "⚠️  토큰 만료 감지: 재인증 시작"
**And** calls KisRestAdapter.login() to get new token
**And** saves new token to `kis_token_cache.json`
**And** retries original API call with new token
**And** displays "✅ 재인증 완료: 거래 재개"
**And** logs event to Sheet 2: "TOKEN_REFRESH"

**Given** re-authentication succeeds
**When** new token is obtained
**Then** the system updates cached token expiry to +24 hours
**And** continues trading without interruption
**And** user sees no impact on trading operations

**Given** re-authentication fails (invalid credentials)
**When** login attempt fails
**Then** the system logs: "❌ 재인증 실패: API 키 확인 필요"
**And** sends Telegram alert: "긴급: 재인증 실패 - API 키 확인 필요"
**And** pauses trading
**And** waits for user intervention
**And** exits with error code 22 (ERROR_LOGIN)

---

### Story 5.4: 텔레그램 알림 및 원격 모니터링

As a **trader**,
I want **to receive Telegram notifications for all important trading events**,
So that **I can monitor my system remotely without checking logs or Excel**.

**Acceptance Criteria:**

**Given** Excel B16 (Telegram enabled) = TRUE and B17 (bot token) is valid
**When** the system initializes
**Then** the system connects to Telegram Bot API
**And** sends test message: "✅ Phoenix Trading System 연결됨"
**And** displays "Telegram 알림 활성화"

**Given** Telegram is enabled and system starts trading
**When** initialization completes successfully
**Then** the system sends notification:
```
🚀 Phoenix Trading System 시작됨
━━━━━━━━━━━━━━━━━━
Tier 1: $50.00
총 자본: $10,000
시스템: 활성화
━━━━━━━━━━━━━━━━━━
```

**Given** a buy order is filled
**When** fill confirmation is received
**Then** the system sends notification:
```
⬇️ 매수 완료
━━━━━━━━━━━━━━━━━━
Tier: 5
수량: 10 shares
가격: $49.00
투자: $490.00
━━━━━━━━━━━━━━━━━━
```

**Given** a sell order is filled with profit
**When** sell confirmation is received
**Then** the system sends notification:
```
⬆️ 매도 완료 🎉
━━━━━━━━━━━━━━━━━━
Tier: 10
수량: 12 shares
가격: $49.25
수익: +$17.40 (+3.04%)
━━━━━━━━━━━━━━━━━━
```

**Given** Tier 1 is updated to new high
**When** update occurs
**Then** the system sends notification:
```
🔼 Tier 1 신고가 갱신
━━━━━━━━━━━━━━━━━━
$50.00 → $51.50
상승: +$1.50 (+3.0%)
━━━━━━━━━━━━━━━━━━
```

**Given** error occurs (API failure, Excel lock, etc.)
**When** error is detected
**Then** the system sends alert:
```
⚠️ 에러 발생
━━━━━━━━━━━━━━━━━━
유형: API 호출 실패
상세: Timeout after 3 retries
상태: 다음 틱 대기 중
━━━━━━━━━━━━━━━━━━
```

**Given** Excel B16 = FALSE
**When** any event occurs
**Then** the system does NOT send Telegram notifications
**And** all events are logged to console and file only

---

### Story 5.5: 구조화된 로깅 (콘솔 + 파일 + Excel)

As a **trader**,
I want **the system to log all events to console, file, and Excel in structured format**,
So that **I can troubleshoot issues and audit all trading activity**.

**Acceptance Criteria:**

**Given** the system is running
**When** any event occurs (trade, error, status change)
**Then** the system logs to THREE destinations:

**1. Console Output (real-time):**
```
[23:32:14] INFO  | ⬇️  매수 주문: Tier 5, 10 shares @ $49.00
[23:32:16] INFO  | ✅ 매수 체결: Tier 5, 10 shares @ $48.95
[23:32:16] INFO  | 📊 Positions: 3 tiers | Invested: $1,450
```
- Timestamp in [HH:MM:SS] format
- Log level (INFO, WARNING, ERROR)
- Korean/English mixed messages
- Emoji for visual clarity

**2. File Logging (`phoenix_trading.log`):**
```
2026-01-24 23:32:14 | INFO  | BUY_ORDER_PLACED | tier=5 qty=10 price=49.00 order_id=KR1234567890
2026-01-24 23:32:16 | INFO  | BUY_ORDER_FILLED | tier=5 qty=10 avg_price=48.95 invested=489.50
2026-01-24 23:32:16 | INFO  | POSITION_UPDATE  | positions_count=3 total_invested=1450.00
```
- Full ISO timestamp
- Structured key=value format
- Machine-parseable
- No emojis (plain text)

**3. Excel History Log (Sheet 2):**
- 17-column structured table (Story 4.3)
- Append-only audit trail
- Complete trade details

**Given** an error occurs (API failure)
**When** error is logged
**Then** the system logs to all three destinations:
- Console: `[23:35:20] ERROR | ❌ API 호출 실패: Timeout (재시도 1/3)`
- File: `2026-01-24 23:35:20 | ERROR | API_CALL_FAILED | endpoint=/quotations/price retry=1/3 error=Timeout`
- Excel: Action="API_ERROR", Reason="Timeout after 3 retries"

**Given** NFR3.3 (No credentials in logs)
**When** any log entry is written
**Then** the system NEVER logs:
- API keys (APP KEY, APP SECRET)
- Account numbers (masked as "****1234")
- Access tokens (masked as "token_abc...xyz")
**And** only logs non-sensitive data
**And** displays credentials only during initialization (console only, not file/Excel)

---

### Story 5.6: 시스템 상태 주기적 저장 및 복구 준비

As a **trader**,
I want **the system to periodically save all state to Excel**,
So that **if system crashes, I can manually verify positions and restart safely**.

**Acceptance Criteria:**

**Given** the system is running normally
**When** 10 ticks complete (10 × 40 seconds = 6.67 minutes)
**Then** the system triggers periodic state save
**And** updates all 4 Excel areas (Story 4.2)
**And** saves Excel workbook
**And** displays "💾 주기적 저장 완료 (10 ticks)"

**Given** a buy or sell order is executed
**When** order is filled
**Then** the system immediately saves state to Excel
**And** does NOT wait for periodic save interval
**And** ensures Excel has latest position data

**Given** Tier 1 is updated
**When** update occurs
**Then** the system immediately saves Tier 1 to Excel B18
**And** saves all recalculated tier prices to Excel C25:G264
**And** displays "💾 Tier 1 갱신 저장 완료"

**Given** system crashes or loses power
**When** user restarts system
**Then** Excel file contains last saved state:
- Latest Tier 1 value (B18)
- All positions in tier table (F/G columns)
- Complete history log in Sheet 2
**And** user can manually verify positions against brokerage account
**And** user can decide whether to restart or adjust settings
**And** displays on startup: "⚠️  이전 세션 감지: Excel 상태 확인 권장"
