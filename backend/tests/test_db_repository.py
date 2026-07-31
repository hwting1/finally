from __future__ import annotations

import pytest

from app.db.repository import (
    DEFAULT_SNAPSHOT_LIMIT,
    DatabaseValidationError,
    TradeExecutionError,
    add_chat_message,
    add_watchlist_ticker,
    execute_trade,
    get_cash_balance,
    get_chat_messages,
    get_portfolio_snapshots,
    get_position,
    get_positions,
    get_user_profile,
    get_watchlist,
    list_trades,
    record_portfolio_snapshot,
    remove_watchlist_ticker,
    validate_quantity,
    validate_ticker,
)
from app.db.schema import DEFAULT_WATCHLIST_TICKERS, initialize_database


def test_lazy_initialization_seeds_default_user_and_watchlist(tmp_path) -> None:
    db_path = tmp_path / "finally.db"

    profile = get_user_profile(db_path=db_path)
    watchlist = get_watchlist(db_path=db_path)

    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert watchlist == list(DEFAULT_WATCHLIST_TICKERS)

    initialize_database(db_path)
    assert get_watchlist(db_path=db_path) == list(DEFAULT_WATCHLIST_TICKERS)


def test_watchlist_repository_normalizes_and_deduplicates_tickers(tmp_path) -> None:
    db_path = tmp_path / "finally.db"

    added = add_watchlist_ticker(" amd ", db_path=db_path)
    duplicate = add_watchlist_ticker("AMD", db_path=db_path)
    removed = remove_watchlist_ticker("amd", db_path=db_path)
    removed_again = remove_watchlist_ticker("AMD", db_path=db_path)

    assert added == {"ticker": "AMD", "added": True}
    assert duplicate == {"ticker": "AMD", "added": False}
    assert removed == {"ticker": "AMD", "removed": True}
    assert removed_again == {"ticker": "AMD", "removed": False}


@pytest.mark.parametrize("ticker", ["", "TOOLONG", "A1", "BRK.B"])
def test_validate_ticker_rejects_invalid_symbols(ticker: str) -> None:
    with pytest.raises(DatabaseValidationError) as exc_info:
        validate_ticker(ticker)

    assert exc_info.value.code == "INVALID_TICKER"


@pytest.mark.parametrize("quantity", [0, -1, "abc", True, "1.1234567"])
def test_validate_quantity_rejects_invalid_quantities(quantity) -> None:
    with pytest.raises(DatabaseValidationError):
        validate_quantity(quantity)


def test_execute_trade_buy_sell_math_and_auto_watchlist(tmp_path) -> None:
    db_path = tmp_path / "finally.db"

    buy = execute_trade(ticker="amd", side="buy", quantity="10.5", price=100, db_path=db_path)
    second_buy = execute_trade(ticker="AMD", side="buy", quantity=1.5, price=120, db_path=db_path)
    sell = execute_trade(ticker="AMD", side="sell", quantity=2, price=130, db_path=db_path)

    position = get_position("AMD", db_path=db_path)

    assert buy["trade"]["ticker"] == "AMD"
    assert buy["added_to_watchlist"] is True
    assert second_buy["position"]["quantity"] == 12.0
    assert second_buy["position"]["avg_cost"] == pytest.approx(102.5)
    assert sell["cash_balance"] == pytest.approx(9030.0)
    assert position["quantity"] == pytest.approx(10.0)
    assert position["avg_cost"] == pytest.approx(102.5)
    assert "AMD" in get_watchlist(db_path=db_path)
    assert len(list_trades(db_path=db_path)) == 3
    assert len(get_portfolio_snapshots(db_path=db_path)) == 3


def test_execute_trade_rolls_back_on_insufficient_shares(tmp_path) -> None:
    db_path = tmp_path / "finally.db"
    execute_trade(ticker="MSFT", side="buy", quantity=1, price=100, db_path=db_path)
    cash_before = get_cash_balance(db_path=db_path)
    trades_before = list_trades(db_path=db_path)

    with pytest.raises(TradeExecutionError) as exc_info:
        execute_trade(ticker="MSFT", side="sell", quantity=2, price=100, db_path=db_path)

    assert exc_info.value.code == "INSUFFICIENT_SHARES"
    assert get_cash_balance(db_path=db_path) == cash_before
    assert get_position("MSFT", db_path=db_path)["quantity"] == 1
    assert list_trades(db_path=db_path) == trades_before


def test_execute_trade_rejects_insufficient_cash_before_mutation(tmp_path) -> None:
    db_path = tmp_path / "finally.db"

    with pytest.raises(TradeExecutionError) as exc_info:
        execute_trade(ticker="AAPL", side="buy", quantity=101, price=100, db_path=db_path)

    assert exc_info.value.code == "INSUFFICIENT_CASH"
    assert get_cash_balance(db_path=db_path) == 10000.0
    assert get_positions(db_path=db_path) == []
    assert list_trades(db_path=db_path) == []


def test_portfolio_snapshots_are_bounded(tmp_path) -> None:
    db_path = tmp_path / "finally.db"

    for value in range(5):
        record_portfolio_snapshot(10000 + value, limit=3, db_path=db_path)

    snapshots = get_portfolio_snapshots(limit=DEFAULT_SNAPSHOT_LIMIT, db_path=db_path)
    assert [snapshot["total_value"] for snapshot in snapshots] == [10002.0, 10003.0, 10004.0]


def test_chat_messages_round_trip_actions_and_limit(tmp_path) -> None:
    db_path = tmp_path / "finally.db"

    add_chat_message(role="user", content="Analyze my portfolio", db_path=db_path)
    assistant = add_chat_message(
        role="assistant",
        content="Bought AMD.",
        actions={"trades": [{"ticker": "AMD", "side": "buy", "status": "executed"}]},
        db_path=db_path,
    )

    messages = get_chat_messages(limit=1, db_path=db_path)

    assert assistant["actions"]["trades"][0]["ticker"] == "AMD"
    assert messages == [assistant]
