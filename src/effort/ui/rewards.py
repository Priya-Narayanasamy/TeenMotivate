"""Rewards — the catalogue, the balance, and spending points.

Nothing here can reduce points *earned*. Redeeming spends against a balance,
and an unaffordable reward is simply not clickable — it never errors, and it
never puts the balance below zero.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..points import total_earned
from ..rewards import (
    balance,
    load_ledger,
    load_rewards,
    redeem,
    save_rewards,
    total_redeemed,
)
from .common import get_data, problems_panel, rules_expander, source_caption


def _catalogue_editor(catalogue: pd.DataFrame) -> pd.DataFrame:
    st.subheader("What you can spend points on")
    st.caption("Edit a name or a cost, or add a row. Changes save when you press the button.")

    edited = st.data_editor(
        catalogue.rename(columns={"name": "Reward", "cost": "Cost"}),
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="rewards_editor",
        column_config={
            "Reward": st.column_config.TextColumn("Reward", required=True, width="large"),
            "Cost": st.column_config.NumberColumn("Cost", min_value=0, step=10, format="%d pts"),
        },
    )

    if st.button("Save the list", type="secondary"):
        saved = save_rewards(edited.rename(columns={"Reward": "name", "Cost": "cost"}))
        st.success(f"Saved {len(saved)} rewards.")
        st.rerun()

    return edited.rename(columns={"Reward": "name", "Cost": "cost"})


def _reward_card(row: pd.Series, available: int, index: int) -> None:
    name = str(row["name"]).strip()
    cost = int(row["cost"])
    if not name:
        return

    affordable = available >= cost
    left, right = st.columns([3, 1], vertical_alignment="center")

    with left:
        if affordable:
            st.markdown(f"**{name}**")
            st.caption(f"{cost} points")
        else:
            # Greyed out, with the gap spelled out rather than just being dead.
            st.markdown(f":grey[**{name}**]")
            st.caption(f":grey[{cost} points — {cost - available} more to go]")

    with right:
        if st.button(
            "Redeem" if affordable else "Locked",
            key=f"redeem_{index}_{name}",
            disabled=not affordable,
            width="stretch",
        ):
            redeem(name, cost)
            st.session_state["just_redeemed"] = name
            st.rerun()


def render() -> None:
    valid, problems = get_data()

    st.title("Rewards")
    problems_panel(problems)

    earned = total_earned(valid)
    ledger = load_ledger()
    spent = total_redeemed(ledger)
    available = balance(earned, ledger)

    if claimed := st.session_state.pop("just_redeemed", None):
        st.success(f"**{claimed}** redeemed. Enjoy it — you earned it.", icon="🎉")

    top = st.columns(3)
    top[0].metric("Points earned", earned, help="Every point ever earned. This only goes up.")
    top[1].metric("Points spent", spent)
    top[2].metric("Balance", available, help="What's left to spend.")

    catalogue = _catalogue_editor(load_rewards())

    st.subheader("Spend points")
    live = catalogue.copy()
    live["cost"] = pd.to_numeric(live["cost"], errors="coerce").fillna(0).clip(lower=0).astype("int64")
    live = live.loc[live["name"].astype("string").str.strip() != ""]

    if live.empty:
        st.info("No rewards on the list yet — add one above.", icon="🎁")
    else:
        for index, row in live.sort_values("cost").reset_index(drop=True).iterrows():
            _reward_card(row, available, index)
            st.divider()

    if not ledger.empty:
        with st.expander(f"Already redeemed ({len(ledger)})"):
            history = ledger.sort_values("redeemed_at", ascending=False).copy()
            history["redeemed_at"] = history["redeemed_at"].dt.strftime("%d %b %Y, %I:%M %p")
            st.dataframe(
                history.rename(columns={"redeemed_at": "When", "reward": "Reward", "cost": "Cost"}),
                hide_index=True,
                width="stretch",
            )
            st.caption("The ledger is append-only — redeeming never takes away points you earned.")

    rules_expander()
    source_caption()
