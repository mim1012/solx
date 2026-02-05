# Phoenix Trading System - 타임라인 다이어그램

**작성일**: 2026-01-24
**버전**: v4.1
**목적**: 시스템 동작 흐름 시각화

---

## 1. 시스템 초기화 시퀀스

```mermaid
sequenceDiagram
    participant User
    participant Main as PhoenixTradingSystem
    participant Excel as ExcelBridge
    participant Grid as GridEngine
    participant KIS as KisRestAdapter
    participant TG as TelegramNotifier

    User->>Main: PhoenixTrading.exe 실행
    Main->>Excel: load_workbook()
    Excel-->>Main: GridSettings

    Main->>Grid: GridEngine(settings)
    Grid-->>Main: 초기화 완료

    Main->>KIS: login()
    KIS->>KIS: Access Token 발급
    KIS->>KIS: Approval Key 발급
    KIS->>KIS: 토큰 캐싱
    KIS-->>Main: 인증 성공

    Main->>KIS: get_overseas_price("SOXL")
    KIS-->>Main: 현재가 $50.30

    Main->>KIS: get_balance()
    KIS-->>Main: 잔고 $5,000.00

    Main->>Grid: tier1_price = $50.30
    Main->>Grid: account_balance = $5,000.00

    Main->>TG: notify_system_start()
    TG-->>User: 📱 "시스템 시작" 알림

    Main->>Main: _wait_for_market_open()
    Note over Main: 시장 개장까지 대기
```

---

## 2. 거래 루프 (단일 사이클)

```mermaid
sequenceDiagram
    participant Main as PhoenixTradingSystem
    participant Grid as GridEngine
    participant KIS as KisRestAdapter
    participant Excel as ExcelBridge
    participant TG as TelegramNotifier

    loop 매 40초마다
        Main->>KIS: get_overseas_price("SOXL")
        KIS-->>Main: current_price

        Main->>Grid: process_tick(current_price)
        Grid->>Grid: update_tier1()
        Grid->>Grid: 매도 배치 확인
        Grid->>Grid: 매수 배치 확인
        Grid-->>Main: List[TradeSignal]

        alt 매매 신호 있음
            Main->>Main: _process_signal(signal)
            Main->>KIS: send_order()
            KIS-->>Main: order_id

            Main->>Main: _wait_for_fill(order_id)
            loop 최대 10회 (2초 간격)
                Main->>KIS: get_order_fill_status(order_id)
                KIS-->>Main: fill_status

                alt 체결 완료
                    Main->>Grid: execute_buy/sell()
                    Grid->>Grid: 포지션 생성/제거
                    Grid-->>Main: Position/profit
                    Main->>TG: notify_buy/sell_executed()
                    TG-->>Main: 알림 전송 완료
                end
            end
        end

        Main->>Main: Excel 업데이트 시간 확인
        alt 업데이트 주기 도달 (1초)
            Main->>Grid: get_system_state()
            Grid-->>Main: SystemState

            Main->>Excel: update_program_info(state)
            Main->>Excel: update_program_area(positions)
            Main->>Excel: append_history_log()
            Main->>Excel: save_workbook()
            Excel-->>Main: 저장 완료
        end

        Main->>Main: sleep(40초)
    end
```

---

## 3. 매수 주문 플로우

```mermaid
flowchart TD
    Start([시세 조회: $49.50]) --> CheckTier1[Tier 1 갱신 확인]
    CheckTier1 --> |포지션 0개 & 신고가| UpdateTier1[Tier 1 갱신]
    CheckTier1 --> |조건 불충족| CheckBuy
    UpdateTier1 --> CheckBuy[매수 배치 확인]

    CheckBuy --> LoopTiers{Tier 2~240 순회}
    LoopTiers --> |각 티어| CheckCondition{매수 조건 충족?}
    CheckCondition --> |미보유 & 현재가 ≤ 티어가| AddBatch[배치 추가]
    CheckCondition --> |조건 불충족| LoopTiers
    AddBatch --> LoopTiers

    LoopTiers --> |순회 완료| CheckBalance{잔고 충분?}
    CheckBalance --> |Yes| CreateSignal[TradeSignal 생성]
    CheckBalance --> |No| Skip([신호 없음])

    CreateSignal --> SendOrder[KIS API 주문]
    SendOrder --> OrderAccepted{주문 접수?}
    OrderAccepted --> |실패| Error([주문 실패])
    OrderAccepted --> |성공| WaitFill[체결 확인 폴링]

    WaitFill --> |10회 × 2초| CheckFill{체결 확인?}
    CheckFill --> |체결| ExecuteBuy[GridEngine.execute_buy]
    CheckFill --> |미체결| Timeout([타임아웃])

    ExecuteBuy --> BatchCheck{배치 주문?}
    BatchCheck --> |Yes| DistributeTiers[티어별 수량 분배]
    BatchCheck --> |No| SinglePosition[단일 포지션 생성]

    DistributeTiers --> PartialCheck{부분 체결?}
    PartialCheck --> |Yes| FirstTierOnly[첫 티어에 전량 할당]
    PartialCheck --> |No| EqualDistribution[균등 분배]

    FirstTierOnly --> UpdateBalance[잔고 차감]
    EqualDistribution --> UpdateBalance
    SinglePosition --> UpdateBalance

    UpdateBalance --> Notify[텔레그램 알림]
    Notify --> End([완료])
```

---

## 4. 매도 주문 플로우

```mermaid
flowchart TD
    Start([시세 조회: $51.00]) --> CheckSell[매도 배치 확인]

    CheckSell --> LoopPositions{보유 포지션 순회}
    LoopPositions --> |높은 티어부터| CalcTarget[티어 매도가 계산]

    CalcTarget --> Formula["tier_sell_price = <br/>tier_buy_price × 1.03"]
    Formula --> CheckPrice{현재가 ≥ 매도가?}

    CheckPrice --> |Yes| AddBatch[배치 추가]
    CheckPrice --> |No| LoopPositions
    AddBatch --> LoopPositions

    LoopPositions --> |순회 완료| HasBatch{매도 배치 존재?}
    HasBatch --> |No| Skip([신호 없음])
    HasBatch --> |Yes| CreateSignal[TradeSignal 생성]

    CreateSignal --> SendOrder[KIS API 주문]
    SendOrder --> OrderAccepted{주문 접수?}
    OrderAccepted --> |실패| Error([주문 실패])
    OrderAccepted --> |성공| WaitFill[체결 확인 폴링]

    WaitFill --> CheckFill{체결 확인?}
    CheckFill --> |체결| ExecuteSell[GridEngine.execute_sell]
    CheckFill --> |미체결| Timeout([타임아웃])

    ExecuteSell --> BatchCheck{배치 주문?}
    BatchCheck --> |Yes| PartialCheck{부분 체결?}
    BatchCheck --> |No| SingleSell[단일 포지션 제거]

    PartialCheck --> |Yes| HighTierFirst[높은 티어부터 제거]
    PartialCheck --> |No| RemoveAll[모든 티어 제거]

    HighTierFirst --> CalcProfit[수익 계산]
    RemoveAll --> CalcProfit
    SingleSell --> CalcProfit

    CalcProfit --> Formula2["profit = <br/>sell_amount - invested"]
    Formula2 --> UpdateBalance[잔고 증가]

    UpdateBalance --> Notify[텔레그램 알림]
    Notify --> End([완료])
```

---

## 5. 에러 처리 플로우

```mermaid
flowchart TD
    Start([API 호출]) --> RateLimit[Rate Limiting]
    RateLimit --> CheckInterval{200ms 경과?}
    CheckInterval --> |No| Sleep[sleep 대기]
    CheckInterval --> |Yes| TokenCheck[토큰 만료 확인]
    Sleep --> TokenCheck

    TokenCheck --> IsExpired{만료 5분 전?}
    IsExpired --> |Yes| RefreshToken[토큰 재발급]
    IsExpired --> |No| MakeRequest[HTTP 요청]
    RefreshToken --> MakeRequest

    MakeRequest --> Response{응답 상태}

    Response --> |200 OK| ParseJSON[JSON 파싱]
    Response --> |401 Unauthorized| AuthError[인증 에러]
    Response --> |Timeout| NetworkError[네트워크 에러]
    Response --> |500 Server Error| ServerError[서버 에러]

    ParseJSON --> CheckCode{rt_cd == "0"?}
    CheckCode --> |Yes| Success([성공])
    CheckCode --> |No| APIError[API 에러]

    AuthError --> Login[login 재시도]
    Login --> LoginSuccess{성공?}
    LoginSuccess --> |Yes| MakeRequest
    LoginSuccess --> |No| FatalError([치명적 에러])

    NetworkError --> Retry{재시도 가능?}
    Retry --> |Yes, 1회| Sleep5[5초 대기]
    Retry --> |No| Warning([경고 로그])
    Sleep5 --> MakeRequest

    ServerError --> Warning
    APIError --> Warning
    Warning --> Continue([다음 루프 계속])
```

---

## 6. Excel 저장 플로우

```mermaid
flowchart TD
    Start([Excel 저장 요청]) --> PrepareData[데이터 준비]
    PrepareData --> UpdateB[영역 B 업데이트<br/>프로그램 정보]
    UpdateB --> UpdateD[영역 D 업데이트<br/>240개 티어]
    UpdateD --> AppendLog[시트 2 로그 추가]

    AppendLog --> TrySave[workbook.save 시도]
    TrySave --> SaveResult{저장 성공?}

    SaveResult --> |성공| Success([저장 완료])
    SaveResult --> |PermissionError| CheckRetry{재시도 횟수 < 3?}
    SaveResult --> |기타 에러| OtherError([에러 로그])

    CheckRetry --> |Yes| LogRetry[재시도 로그]
    CheckRetry --> |No| MaxRetry([최대 재시도 초과])

    LogRetry --> Sleep1[1초 대기]
    Sleep1 --> TrySave

    Success --> Log[INFO 로그 기록]
    MaxRetry --> ErrorLog[ERROR 로그 기록]
    OtherError --> ErrorLog

    Log --> End([종료])
    ErrorLog --> End
```

---

## 7. 시스템 종료 플로우

```mermaid
flowchart TD
    Start([Ctrl+C 또는 에러]) --> SignalHandler[시그널 핸들러]
    SignalHandler --> SetFlag[stop_requested = True]

    SetFlag --> BreakLoop[거래 루프 탈출]
    BreakLoop --> Shutdown[shutdown 메서드]

    Shutdown --> GetState[최종 상태 조회]
    GetState --> UpdateExcel[Excel 업데이트]
    UpdateExcel --> SaveExcel{저장 성공?}

    SaveExcel --> |Yes| CloseExcel[Excel 파일 닫기]
    SaveExcel --> |No| ErrorLog[에러 로그]

    CloseExcel --> Disconnect[KIS API 연결 해제]
    ErrorLog --> Disconnect

    Disconnect --> SendNotify[텔레그램 종료 알림]
    SendNotify --> FinalLog[최종 로그 기록]

    FinalLog --> ExitCode{종료 코드}
    ExitCode --> |0| NormalExit([정상 종료])
    ExitCode --> |10| StoppedExit([시스템 중지])
    ExitCode --> |20+| ErrorExit([에러 종료])

    NormalExit --> DisplayMsg[종료 메시지 출력]
    StoppedExit --> DisplayMsg
    ErrorExit --> DisplayMsg

    DisplayMsg --> WaitInput["Press Enter to exit..."]
    WaitInput --> End([프로세스 종료])
```

---

## 8. Tier 1 갱신 결정 트리

```mermaid
flowchart TD
    Start([현재가 수신]) --> CheckSetting{tier1_auto_update<br/>설정 확인}

    CheckSetting --> |FALSE| NoUpdate([갱신 안 함])
    CheckSetting --> |TRUE| CheckPositions{총 보유 수량<br/>확인}

    CheckPositions --> |> 0<br/>보유 중| NoUpdate
    CheckPositions --> |= 0<br/>청산 완료| CheckPrice{현재가 vs<br/>Tier 1 가격}

    CheckPrice --> |현재가 ≤ Tier 1| NoUpdate
    CheckPrice --> |현재가 > Tier 1| UpdateTier1[Tier 1 갱신]

    UpdateTier1 --> LogUpdate[갱신 로그 기록]
    LogUpdate --> RecalcTiers[모든 티어 재계산]

    RecalcTiers --> Example["예: $50.00 → $52.00<br/>Tier 2: $51.74<br/>Tier 3: $51.48<br/>..."]

    Example --> Notify[텔레그램 알림]
    Notify --> End([갱신 완료])
```

---

## 9. 거래 시간 관리

```mermaid
gantt
    title Phoenix Trading System - 24시간 운영 사이클
    dateFormat HH:mm
    axisFormat %H:%M

    section 한국 시간
    장 마감 (대기)     :done,    wait1, 06:00, 17h30m
    장 시작 준비       :active,  prep,  23:25, 5m
    정규장 (거래)      :crit,    trade, 23:30, 6h30m
    장 마감 (대기)     :done,    wait2, 06:00, 0m

    section 미국 시간
    금요일 마감        :done,    us_close, 16:00, 0m
    주말 (휴장)        :         weekend,  16:00, 65h30m
    월요일 개장        :crit,    us_open,  09:30, 0m
    정규장             :crit,    us_trade, 09:30, 6h30m
```

---

## 10. 배치 주문 vs 개별 주문 비교

```mermaid
flowchart LR
    subgraph 기존 방식 [개별 주문 방식]
        A1[시세 조회 #1<br/>$48.00] --> B1[Tier 5 매수]
        B1 --> C1[KIS API 호출]
        C1 --> D1[40초 대기]
        D1 --> A2[시세 조회 #2<br/>$47.90]
        A2 --> B2[Tier 6 매수]
        B2 --> C2[KIS API 호출]
        C2 --> D2[40초 대기]
        D2 --> A3[시세 조회 #3<br/>$47.85]
        A3 --> B3[Tier 7 매수]
        B3 --> C3[KIS API 호출]
    end

    subgraph 배치 방식 [배치 주문 방식]
        X1[시세 조회 #1<br/>$48.00] --> Y1[Tier 5,6,7<br/>동시 매수]
        Y1 --> Z1[KIS API 호출 1회]
        Z1 --> W1[40초 대기]
        W1 --> X2[다음 시세 조회]
    end

    기존 방식 -.->|슬리피지 위험| Risk[가격 변동 노출<br/>$48.00 → $47.85]
    배치 방식 -.->|가격 일관성| Safe[동일 가격 보장<br/>$48.00 × 3]
```

---

## 11. 체결 확인 폴링 타임라인

```mermaid
gantt
    title 체결 확인 프로세스 (최대 20초)
    dateFormat ss
    axisFormat %S초

    section 주문
    주문 전송          :milestone, m1, 00, 0s

    section 체결 확인
    시도 #1 (0초)      :done,    c1, 00, 2s
    시도 #2 (2초)      :done,    c2, 02, 2s
    시도 #3 (4초)      :done,    c3, 04, 2s
    시도 #4 (6초)      :active,  c4, 06, 2s
    시도 #5 (8초)      :         c5, 08, 2s
    시도 #6 (10초)     :         c6, 10, 2s
    시도 #7 (12초)     :         c7, 12, 2s
    시도 #8 (14초)     :         c8, 14, 2s
    시도 #9 (16초)     :         c9, 16, 2s
    시도 #10 (18초)    :         c10, 18, 2s

    section 결과
    체결 완료          :milestone, m2, 06, 0s
    포지션 생성        :crit,    pos, 06, 1s
```

---

## 12. 수익 실현 전체 플로우

```mermaid
graph TB
    Start([투자 시작<br/>$5,000]) --> Buy1[매수 #1<br/>Tier 3,4 @ $49.48<br/>-$98.96]
    Buy1 --> State1[잔고: $4,901.04<br/>포지션: 2개]

    State1 --> Buy2[매수 #2<br/>Tier 5 @ $47.48<br/>-$284.88]
    Buy2 --> State2[잔고: $4,616.16<br/>포지션: 3개]

    State2 --> Price1{가격 변동}
    Price1 --> |상승| Sell1[매도 #1<br/>Tier 3,4 @ $51.00<br/>+$102.00]

    Sell1 --> Profit1[실현 수익: $3.04<br/>수익률: 3.07%]
    Profit1 --> State3[잔고: $4,718.16<br/>포지션: 1개]

    State3 --> Price2{가격 변동}
    Price2 --> |추가 상승| Sell2[매도 #2<br/>Tier 5 @ $50.98<br/>+$305.88]

    Sell2 --> Profit2[실현 수익: $21.00<br/>수익률: 7.37%]
    Profit2 --> State4[잔고: $5,024.04<br/>포지션: 0개]

    State4 --> UpdateT1[Tier 1 갱신<br/>$50.30 → $52.50]
    UpdateT1 --> Final([최종 자산: $5,024.04<br/>총 수익: +$24.04<br/>+0.48%])

    style Start fill:#e1f5ff
    style Final fill:#d4edda
    style Profit1 fill:#fff3cd
    style Profit2 fill:#fff3cd
```

---

**문서 작성**: AI Agent (Claude Code)
**다이어그램 도구**: Mermaid
**최종 수정**: 2026-01-24

