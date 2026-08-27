"""Goon session persistence mixin."""
from __future__ import annotations

from dataclasses import dataclass

import config
from utils.goon_session import (
    GoonSessionState,
    clamp_meter,
    cooldown_remaining,
    finish_payout,
    ruin_cost,
    session_from_row,
)


@dataclass(frozen=True)
class GoonActionResult:
    ok: bool
    error: str | None
    state: GoonSessionState
    gained: float = 0.0
    payout: float = 0.0
    stolen: float = 0.0
    cost: float = 0.0
    cooldown: float = 0.0
    watchers: int = 0
    leaked: bool = False


class DatabaseGoonSessionMixin:
    async def _migrate_goon_sessions(self) -> None:
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goon_sessions (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                meter REAL NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                session_started_at REAL NOT NULL DEFAULT 0,
                last_edge_at REAL NOT NULL DEFAULT 0,
                last_passive_at REAL NOT NULL DEFAULT 0,
                last_tease_at REAL NOT NULL DEFAULT 0,
                last_ruin_at REAL NOT NULL DEFAULT 0,
                last_finish_at REAL NOT NULL DEFAULT 0,
                ruined_by BIGINT,
                lifetime_edges INTEGER NOT NULL DEFAULT 0,
                lifetime_ruins INTEGER NOT NULL DEFAULT 0,
                lifetime_finishes INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
            """,
        )
        await self.conn.commit()

    async def _ensure_goon_session_no_lock(self, user_id: int, guild_id: int) -> None:
        await self._ensure_user_no_lock(user_id, guild_id)
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO goon_sessions (user_id, guild_id)
            VALUES (?, ?)
            """,
            (user_id, guild_id),
        )

    async def get_goon_session(self, user_id: int, guild_id: int) -> GoonSessionState:
        await self.ensure_user(user_id, guild_id)
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            await self.conn.commit()
        cursor = await self.conn.execute(
            """
            SELECT * FROM goon_sessions
            WHERE user_id = ? AND guild_id = ?
            """,
            (user_id, guild_id),
        )
        return session_from_row(await cursor.fetchone())

    async def _load_session_unlocked(self, user_id: int, guild_id: int) -> GoonSessionState:
        await self._ensure_goon_session_no_lock(user_id, guild_id)
        cursor = await self.conn.execute(
            """
            SELECT * FROM goon_sessions
            WHERE user_id = ? AND guild_id = ?
            """,
            (user_id, guild_id),
        )
        return session_from_row(await cursor.fetchone())

    async def _save_session_unlocked(self, user_id: int, guild_id: int, state: GoonSessionState) -> None:
        await self.conn.execute(
            """
            UPDATE goon_sessions
            SET meter = ?, streak = ?, session_started_at = ?,
                last_edge_at = ?, last_passive_at = ?, last_tease_at = ?,
                last_ruin_at = ?, last_finish_at = ?, ruined_by = ?,
                lifetime_edges = ?, lifetime_ruins = ?, lifetime_finishes = ?
            WHERE user_id = ? AND guild_id = ?
            """,
            (
                state.meter,
                state.streak,
                state.session_started_at,
                state.last_edge_at,
                state.last_passive_at,
                state.last_tease_at,
                state.last_ruin_at,
                state.last_finish_at,
                state.ruined_by,
                state.lifetime_edges,
                state.lifetime_ruins,
                state.lifetime_finishes,
                user_id,
                guild_id,
            ),
        )

    async def tick_goon_passive(
        self,
        user_id: int,
        guild_id: int,
        *,
        gain: float,
        now: float,
        cooldown: float,
        watch_mult: float = 1.0,
    ) -> GoonActionResult:
        """Chat/VC/job/daily meter tick. Jobs/daily pass cooldown=0."""
        if gain <= 0:
            state = await self.get_goon_session(user_id, guild_id)
            return GoonActionResult(ok=False, error="noop", state=state)
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            remaining = cooldown_remaining(state.last_passive_at, cooldown, now)
            if remaining > 0:
                await self.conn.commit()
                return GoonActionResult(
                    ok=False, error="cooldown", state=state, cooldown=remaining,
                )
            applied = gain * max(1.0, watch_mult)
            new_meter = clamp_meter(state.meter + applied)
            leaked = state.meter + applied > config.GOON_METER_MAX
            started = state.session_started_at if state.session_started_at > 0 else now
            new_state = GoonSessionState(
                meter=new_meter,
                streak=state.streak,
                session_started_at=started,
                last_edge_at=state.last_edge_at,
                last_passive_at=now,
                last_tease_at=state.last_tease_at,
                last_ruin_at=state.last_ruin_at,
                last_finish_at=state.last_finish_at,
                ruined_by=state.ruined_by,
                lifetime_edges=state.lifetime_edges,
                lifetime_ruins=state.lifetime_ruins,
                lifetime_finishes=state.lifetime_finishes,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return GoonActionResult(
                ok=True,
                error=None,
                state=new_state,
                gained=applied,
                leaked=leaked,
            )

    async def apply_goon_edge(
        self,
        user_id: int,
        guild_id: int,
        *,
        gain: float,
        now: float,
        watch_mult: float = 1.0,
        watchers: int = 0,
    ) -> GoonActionResult:
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            remaining = cooldown_remaining(
                state.last_edge_at, config.GOON_EDGE_COOLDOWN_SECONDS, now,
            )
            if remaining > 0:
                await self.conn.commit()
                return GoonActionResult(
                    ok=False, error="cooldown", state=state, cooldown=remaining,
                )
            applied = gain * max(1.0, watch_mult)
            new_meter = clamp_meter(state.meter + applied)
            leaked = state.meter + applied > config.GOON_METER_MAX
            started = state.session_started_at if state.session_started_at > 0 else now
            new_state = GoonSessionState(
                meter=new_meter,
                streak=state.streak + 1,
                session_started_at=started,
                last_edge_at=now,
                last_passive_at=state.last_passive_at,
                last_tease_at=state.last_tease_at,
                last_ruin_at=state.last_ruin_at,
                last_finish_at=state.last_finish_at,
                ruined_by=None,
                lifetime_edges=state.lifetime_edges + 1,
                lifetime_ruins=state.lifetime_ruins,
                lifetime_finishes=state.lifetime_finishes,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return GoonActionResult(
                ok=True,
                error=None,
                state=new_state,
                gained=applied,
                leaked=leaked,
                watchers=watchers,
            )

    async def apply_goon_finish(
        self,
        user_id: int,
        guild_id: int,
        *,
        now: float,
    ) -> GoonActionResult:
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            payout = finish_payout(state.streak, state.meter)
            if payout <= 0:
                await self.conn.commit()
                return GoonActionResult(ok=False, error="not_edged", state=state)
            new_state = GoonSessionState(
                meter=0.0,
                streak=0,
                session_started_at=0.0,
                last_edge_at=state.last_edge_at,
                last_passive_at=state.last_passive_at,
                last_tease_at=state.last_tease_at,
                last_ruin_at=state.last_ruin_at,
                last_finish_at=now,
                ruined_by=None,
                lifetime_edges=state.lifetime_edges,
                lifetime_ruins=state.lifetime_ruins,
                lifetime_finishes=state.lifetime_finishes + 1,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
        await self.credit_wallet(user_id, guild_id, payout)
        return GoonActionResult(ok=True, error=None, state=new_state, payout=payout)

    async def apply_goon_ruin_self(
        self,
        user_id: int,
        guild_id: int,
        *,
        now: float,
    ) -> GoonActionResult:
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            would = finish_payout(state.streak, state.meter)
            if would <= 0:
                await self.conn.commit()
                return GoonActionResult(ok=False, error="not_edged", state=state)
            payout = round(would * config.GOON_SELF_RUIN_FRAC, 2)
            new_state = GoonSessionState(
                meter=0.0,
                streak=0,
                session_started_at=0.0,
                last_edge_at=state.last_edge_at,
                last_passive_at=state.last_passive_at,
                last_tease_at=state.last_tease_at,
                last_ruin_at=now,
                last_finish_at=state.last_finish_at,
                ruined_by=user_id,
                lifetime_edges=state.lifetime_edges,
                lifetime_ruins=state.lifetime_ruins + 1,
                lifetime_finishes=state.lifetime_finishes,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
        if payout > 0:
            await self.credit_wallet(user_id, guild_id, payout)
        return GoonActionResult(ok=True, error=None, state=new_state, payout=payout)

    async def apply_goon_ruin_other(
        self,
        actor_id: int,
        target_id: int,
        guild_id: int,
        *,
        now: float,
    ) -> GoonActionResult:
        if actor_id == target_id:
            return await self.apply_goon_ruin_self(actor_id, guild_id, now=now)
        target = await self.get_goon_session(target_id, guild_id)
        would = finish_payout(target.streak, target.meter)
        if would <= 0:
            return GoonActionResult(ok=False, error="target_dry", state=target)
        cost = ruin_cost(target.streak)
        stolen = round(would * config.GOON_RUIN_STEAL_FRAC, 2)
        ok = await self.debit_wallet(actor_id, guild_id, cost)
        if not ok:
            return GoonActionResult(ok=False, error="funds", state=target, cost=cost)
        refund = False
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(target_id, guild_id)
            state = await self._load_session_unlocked(target_id, guild_id)
            would_now = finish_payout(state.streak, state.meter)
            if would_now <= 0:
                await self.conn.commit()
                refund = True
            else:
                new_state = GoonSessionState(
                    meter=0.0,
                    streak=0,
                    session_started_at=0.0,
                    last_edge_at=state.last_edge_at,
                    last_passive_at=state.last_passive_at,
                    last_tease_at=state.last_tease_at,
                    last_ruin_at=now,
                    last_finish_at=state.last_finish_at,
                    ruined_by=actor_id,
                    lifetime_edges=state.lifetime_edges,
                    lifetime_ruins=state.lifetime_ruins + 1,
                    lifetime_finishes=state.lifetime_finishes,
                )
                await self._save_session_unlocked(target_id, guild_id, new_state)
                await self.conn.commit()
                stolen = round(would_now * config.GOON_RUIN_STEAL_FRAC, 2)
                would = would_now
                state = new_state
        if refund:
            await self.credit_wallet(actor_id, guild_id, cost)
            return GoonActionResult(ok=False, error="target_dry", state=state, cost=cost)
        await self.credit_wallet(actor_id, guild_id, stolen)
        leftover = max(0.0, would - stolen)
        if leftover > 0:
            await self.credit_house_pot(guild_id, leftover)
        return GoonActionResult(
            ok=True, error=None, state=state, stolen=stolen, cost=cost, payout=would,
        )

    async def apply_goon_tease(
        self,
        actor_id: int,
        target_id: int,
        guild_id: int,
        *,
        gain: float,
        now: float,
    ) -> GoonActionResult:
        if actor_id == target_id:
            state = await self.get_goon_session(actor_id, guild_id)
            return GoonActionResult(ok=False, error="self", state=state)
        actor = await self.get_goon_session(actor_id, guild_id)
        remaining = cooldown_remaining(
            actor.last_tease_at, config.GOON_TEASE_COOLDOWN_SECONDS, now,
        )
        if remaining > 0:
            return GoonActionResult(
                ok=False, error="cooldown", state=actor, cooldown=remaining,
            )
        ok = await self.debit_wallet(actor_id, guild_id, config.GOON_TEASE_COST)
        if not ok:
            return GoonActionResult(
                ok=False, error="funds", state=actor, cost=config.GOON_TEASE_COST,
            )
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(actor_id, guild_id)
            await self._ensure_goon_session_no_lock(target_id, guild_id)
            actor_state = await self._load_session_unlocked(actor_id, guild_id)
            target_state = await self._load_session_unlocked(target_id, guild_id)
            new_meter = clamp_meter(target_state.meter + gain)
            leaked = target_state.meter + gain > config.GOON_METER_MAX
            started = (
                target_state.session_started_at if target_state.session_started_at > 0 else now
            )
            new_target = GoonSessionState(
                meter=new_meter,
                streak=target_state.streak,
                session_started_at=started,
                last_edge_at=target_state.last_edge_at,
                last_passive_at=target_state.last_passive_at,
                last_tease_at=target_state.last_tease_at,
                last_ruin_at=target_state.last_ruin_at,
                last_finish_at=target_state.last_finish_at,
                ruined_by=target_state.ruined_by,
                lifetime_edges=target_state.lifetime_edges,
                lifetime_ruins=target_state.lifetime_ruins,
                lifetime_finishes=target_state.lifetime_finishes,
            )
            new_actor = GoonSessionState(
                meter=actor_state.meter,
                streak=actor_state.streak,
                session_started_at=actor_state.session_started_at,
                last_edge_at=actor_state.last_edge_at,
                last_passive_at=actor_state.last_passive_at,
                last_tease_at=now,
                last_ruin_at=actor_state.last_ruin_at,
                last_finish_at=actor_state.last_finish_at,
                ruined_by=actor_state.ruined_by,
                lifetime_edges=actor_state.lifetime_edges,
                lifetime_ruins=actor_state.lifetime_ruins,
                lifetime_finishes=actor_state.lifetime_finishes,
            )
            await self._save_session_unlocked(target_id, guild_id, new_target)
            await self._save_session_unlocked(actor_id, guild_id, new_actor)
            await self.conn.commit()
        return GoonActionResult(
            ok=True,
            error=None,
            state=new_target,
            gained=gain,
            cost=config.GOON_TEASE_COST,
            leaked=leaked,
        )

    async def ruin_goon_from_hack(self, user_id: int, guild_id: int, *, now: float) -> GoonActionResult:
        """Contagious goon detonation wipes the holder's session with no payout."""
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            if state.streak <= 0 and state.meter < 1:
                await self.conn.commit()
                return GoonActionResult(ok=True, error=None, state=state)
            new_state = GoonSessionState(
                meter=0.0,
                streak=0,
                session_started_at=0.0,
                last_edge_at=state.last_edge_at,
                last_passive_at=state.last_passive_at,
                last_tease_at=state.last_tease_at,
                last_ruin_at=now,
                last_finish_at=state.last_finish_at,
                ruined_by=None,
                lifetime_edges=state.lifetime_edges,
                lifetime_ruins=state.lifetime_ruins + 1,
                lifetime_finishes=state.lifetime_finishes,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return GoonActionResult(ok=True, error=None, state=new_state)
