"""
Fix #10 검증: Excel 템플릿 수정 후 load_settings() 테스트
"""
from src.excel_bridge import ExcelBridge

def main():
    print('=== Testing ExcelBridge.load_settings() ===')
    print('Template: phoenix_grid_template_v3.xlsx')
    print()

    try:
        bridge = ExcelBridge('phoenix_grid_template_v3.xlsx')
        settings = bridge.load_settings()

        print('[OK] load_settings() succeeded!')
        print()
        print('=== Loaded Settings ===')
        print(f'ticker: {settings.ticker}')
        print(f'investment_usd: ${settings.investment_usd:.2f}')
        print(f'buy_interval: {settings.buy_interval} ({settings.buy_interval*100:.2f}%)')
        print(f'sell_target: {settings.sell_target} ({settings.sell_target*100:.2f}%)')
        print(f'seed_ratio: {settings.seed_ratio} ({settings.seed_ratio*100:.2f}%)')
        print(f'tier1_trading_enabled: {settings.tier1_trading_enabled}')
        print(f'telegram_enabled: {settings.telegram_enabled}')
        print(f'excel_update_interval: {settings.excel_update_interval}')
        print()

        # 값 검증
        assert settings.buy_interval == 0.005, f"buy_interval should be 0.005, got {settings.buy_interval}"
        assert settings.sell_target == 0.03, f"sell_target should be 0.03, got {settings.sell_target}"
        assert settings.seed_ratio == 0.05, f"seed_ratio should be 0.05, got {settings.seed_ratio}"
        assert settings.excel_update_interval == 40.0, f"excel_update_interval should be 40.0, got {settings.excel_update_interval}"

        print('[SUCCESS] All parameters loaded correctly!')
        print('[SUCCESS] Fix #10 validation PASSED!')
        return True

    except Exception as e:
        print(f'[ERROR] {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
