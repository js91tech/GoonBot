"""Goon session persistence mixin."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace

import config
from utils.goon_session import (
    GoonSessionState,
    clamp_meter,
    cooldown_remaining,
    finish_payout,
    ruin_cost,
    safe_finish_streak,
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
    held: bool = False
    shielded: bool = False
    dare_paid: float = 0.0
    streak_kept: int = 0


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
                condom_charges INTEGER NOT NULL DEFAULT 0,
                dare_expires_at REAL NOT NULL DEFAULT 0,
                lifetime_group_rounds INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
            """,
        )
        await self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goon_group_calls (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL DEFAULT 0,
                phase TEXT NOT NULL DEFAULT 'call',
                amount REAL NOT NULL DEFAULT 0,
                condoms INTEGER NOT NULL DEFAULT 0,
                host_id BIGINT NOT NULL DEFAULT 0,
                call_expires_at REAL NOT NULL DEFAULT 0,
                round_ends_at REAL NOT NULL DEFAULT 0,
                free_join_until REAL NOT NULL DEFAULT 0,
                prompt TEXT NOT NULL DEFAULT '',
                joiners TEXT NOT NULL DEFAULT '[]',
                edges TEXT NOT NULL DEFAULT '{}',
                leaked TEXT NOT NULL DEFAULT '{}',
                finished TEXT NOT NULL DEFAULT '{}'
            )
            """,
        )
        extra = [
            ("condom_charges", "INTEGER NOT NULL DEFAULT 0"),
            ("dare_expires_at", "REAL NOT NULL DEFAULT 0"),
            ("lifetime_group_rounds", "INTEGER NOT NULL DEFAULT 0"),
        ]
        await self._add_goon_session_columns(extra)
        await self.conn.commit()

    async def _add_goon_session_columns(self, cols: list[tuple[str, str]]) -> None:
        if getattr(self, "is_postgres", False):
            for col, typedef in cols:
                cursor = await self.conn.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = ANY (current_schemas(true))
                      AND table_name = 'goon_sessions' AND column_name = ?
                    """,
                    (col,),
                )
                if await cursor.fetchone() is None:
                    await self.conn.execute(
                        f"ALTER TABLE goon_sessions ADD COLUMN {col} {typedef}",
                    )
            return
        cursor = await self.conn.execute("PRAGMA table_info(goon_sessions)")
        existing = {row[1] for row in await cursor.fetchall()}
        for col, typedef in cols:
            if col not in existing:
                await self.conn.execute(
                    f"ALTER TABLE goon_sessions ADD COLUMN {col} {typedef}",
                )

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
                lifetime_edges = ?, lifetime_ruins = ?, lifetime_finishes = ?,
                condom_charges = ?, dare_expires_at = ?, lifetime_group_rounds = ?
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
                state.condom_charges,
                state.dare_expires_at,
                state.lifetime_group_rounds,
                user_id,
                guild_id,
            ),
        )

    def _dare_payout(self, state: GoonSessionState, now: float) -> tuple[GoonSessionState, float]:
        if state.dare_expires_at <= 0 or now > state.dare_expires_at:
            return state, 0.0
        return replace(state, dare_expires_at=0.0), float(config.GOON_DARE_PAYOUT)

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
        """Chat/VC/job/daily meter tick. Jobs/daily pass cooldown=0. No forced leak."""
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
            new_state = replace(
                state,
                meter=new_meter,
                session_started_at=started,
                last_passive_at=now,
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
        payout = 0.0
        dare_paid = 0.0
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
            overflow = state.meter + applied > config.GOON_METER_MAX
            started = state.session_started_at if state.session_started_at > 0 else now
            edged = replace(
                state,
                last_edge_at=now,
                lifetime_edges=state.lifetime_edges + 1,
                ruined_by=None,
            )
            edged, dare_paid = self._dare_payout(edged, now)
            held = False
            leaked = False
            if overflow and edged.condom_charges > 0:
                held = True
                new_state = replace(
                    edged,
                    meter=config.GOON_METER_MAX,
                    streak=edged.streak + 1,
                    session_started_at=started,
                    condom_charges=edged.condom_charges - 1,
                )
            elif overflow:
                leaked = True
                would = finish_payout(edged.streak + 1, config.GOON_METER_MAX)
                payout = round(would * config.GOON_SELF_RUIN_FRAC, 2)
                new_state = replace(
                    edged,
                    meter=0.0,
                    streak=0,
                    session_started_at=0.0,
                    last_ruin_at=now,
                    ruined_by=user_id,
                    lifetime_ruins=edged.lifetime_ruins + 1,
                    dare_expires_at=0.0,
                )
                dare_paid = 0.0
            else:
                new_state = replace(
                    edged,
                    meter=clamp_meter(state.meter + applied),
                    streak=edged.streak + 1,
                    session_started_at=started,
                )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
        if payout > 0:
            await self.credit_wallet(user_id, guild_id, payout)
        if dare_paid > 0:
            await self.credit_wallet(user_id, guild_id, dare_paid)
        return GoonActionResult(
            ok=True,
            error=None,
            state=new_state,
            gained=applied,
            leaked=leaked,
            held=held,
            payout=payout,
            dare_paid=dare_paid,
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
            charges = state.condom_charges
            kept = 0
            if charges > 0:
                kept = safe_finish_streak(state.streak)
                charges -= 1
            new_state = replace(
                state,
                meter=0.0,
                streak=kept,
                session_started_at=now if kept else 0.0,
                last_finish_at=now,
                ruined_by=None,
                lifetime_finishes=state.lifetime_finishes + 1,
                condom_charges=charges,
                dare_expires_at=0.0,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
        await self.credit_wallet(user_id, guild_id, payout)
        return GoonActionResult(
            ok=True, error=None, state=new_state, payout=payout, streak_kept=kept,
        )

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
            new_state = replace(
                state,
                meter=0.0,
                streak=0,
                session_started_at=0.0,
                last_ruin_at=now,
                ruined_by=user_id,
                lifetime_ruins=state.lifetime_ruins + 1,
                dare_expires_at=0.0,
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
        cost_mult: float = 1.0,
    ) -> GoonActionResult:
        if actor_id == target_id:
            return await self.apply_goon_ruin_self(actor_id, guild_id, now=now)
        target = await self.get_goon_session(target_id, guild_id)
        would = finish_payout(target.streak, target.meter)
        if would <= 0:
            return GoonActionResult(ok=False, error="target_dry", state=target)
        cost = ruin_cost(target.streak, cost_mult=cost_mult)
        stolen = round(would * config.GOON_RUIN_STEAL_FRAC, 2)
        ok = await self.debit_wallet(actor_id, guild_id, cost)
        if not ok:
            return GoonActionResult(ok=False, error="funds", state=target, cost=cost)
        refund = False
        shielded = False
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(target_id, guild_id)
            state = await self._load_session_unlocked(target_id, guild_id)
            would_now = finish_payout(state.streak, state.meter)
            if would_now <= 0:
                await self.conn.commit()
                refund = True
            elif state.condom_charges > 0:
                shielded = True
                new_state = replace(state, condom_charges=state.condom_charges - 1)
                await self._save_session_unlocked(target_id, guild_id, new_state)
                await self.conn.commit()
                state = new_state
            else:
                new_state = replace(
                    state,
                    meter=0.0,
                    streak=0,
                    session_started_at=0.0,
                    last_ruin_at=now,
                    ruined_by=actor_id,
                    lifetime_ruins=state.lifetime_ruins + 1,
                    dare_expires_at=0.0,
                )
                await self._save_session_unlocked(target_id, guild_id, new_state)
                await self.conn.commit()
                stolen = round(would_now * config.GOON_RUIN_STEAL_FRAC, 2)
                would = would_now
                state = new_state
        if refund:
            await self.credit_wallet(actor_id, guild_id, cost)
            return GoonActionResult(ok=False, error="target_dry", state=state, cost=cost)
        if shielded:
            await self.credit_wallet(actor_id, guild_id, cost)
            return GoonActionResult(
                ok=False, error="shielded", state=state, cost=cost, shielded=True,
            )
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
        cost: float | None = None,
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
        tease_cost = float(config.GOON_TEASE_COST if cost is None else cost)
        ok = await self.debit_wallet(actor_id, guild_id, tease_cost)
        if not ok:
            return GoonActionResult(
                ok=False, error="funds", state=actor, cost=tease_cost,
            )
        payout = 0.0
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(actor_id, guild_id)
            await self._ensure_goon_session_no_lock(target_id, guild_id)
            actor_state = await self._load_session_unlocked(actor_id, guild_id)
            target_state = await self._load_session_unlocked(target_id, guild_id)
            overflow = target_state.meter + gain > config.GOON_METER_MAX
            started = (
                target_state.session_started_at if target_state.session_started_at > 0 else now
            )
            held = False
            leaked = False
            if overflow and target_state.condom_charges > 0:
                held = True
                new_target = replace(
                    target_state,
                    meter=config.GOON_METER_MAX,
                    session_started_at=started,
                    condom_charges=target_state.condom_charges - 1,
                )
            elif overflow:
                leaked = True
                would = finish_payout(target_state.streak, config.GOON_METER_MAX)
                payout = round(would * config.GOON_SELF_RUIN_FRAC, 2)
                new_target = replace(
                    target_state,
                    meter=0.0,
                    streak=0,
                    session_started_at=0.0,
                    last_ruin_at=now,
                    ruined_by=actor_id,
                    lifetime_ruins=target_state.lifetime_ruins + 1,
                    dare_expires_at=0.0,
                )
            else:
                new_target = replace(
                    target_state,
                    meter=clamp_meter(target_state.meter + gain),
                    session_started_at=started,
                )
            new_actor = replace(actor_state, last_tease_at=now)
            await self._save_session_unlocked(target_id, guild_id, new_target)
            await self._save_session_unlocked(actor_id, guild_id, new_actor)
            await self.conn.commit()
        if payout > 0:
            await self.credit_wallet(target_id, guild_id, payout)
        return GoonActionResult(
            ok=True,
            error=None,
            state=new_target,
            gained=gain,
            cost=tease_cost,
            leaked=leaked,
            held=held,
            payout=payout,
        )

    async def ruin_goon_from_hack(self, user_id: int, guild_id: int, *, now: float) -> GoonActionResult:
        """Contagious goon detonation wipes the holder's session with no payout."""
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            if state.streak <= 0 and state.meter < 1:
                await self.conn.commit()
                return GoonActionResult(ok=True, error=None, state=state)
            new_state = replace(
                state,
                meter=0.0,
                streak=0,
                session_started_at=0.0,
                last_ruin_at=now,
                ruined_by=None,
                lifetime_ruins=state.lifetime_ruins + 1,
                dare_expires_at=0.0,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return GoonActionResult(ok=True, error=None, state=new_state)

    async def add_condom_charges(
        self, user_id: int, guild_id: int, *, charges: int = 1,
    ) -> GoonSessionState:
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            new_state = replace(
                state, condom_charges=state.condom_charges + max(0, charges),
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return new_state

    async def start_goon_dare(
        self, user_id: int, guild_id: int, *, now: float, seconds: float | None = None,
    ) -> GoonSessionState:
        duration = float(config.GOON_DARE_SECONDS if seconds is None else seconds)
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            new_state = replace(state, dare_expires_at=now + duration)
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return new_state

    async def bump_group_rounds(self, user_id: int, guild_id: int) -> GoonSessionState:
        async with self._write_lock:
            await self._ensure_goon_session_no_lock(user_id, guild_id)
            state = await self._load_session_unlocked(user_id, guild_id)
            new_state = replace(
                state, lifetime_group_rounds=state.lifetime_group_rounds + 1,
            )
            await self._save_session_unlocked(user_id, guild_id, new_state)
            await self.conn.commit()
            return new_state

    async def goon_session_leaderboard(
        self, guild_id: int, column: str, *, limit: int = 10,
    ) -> list:
        allowed = {
            "streak",
            "lifetime_finishes",
            "lifetime_edges",
            "lifetime_ruins",
            "lifetime_group_rounds",
        }
        if column not in allowed:
            msg = f"Invalid goon leaderboard column: {column}"
            raise ValueError(msg)
        cursor = await self.conn.execute(
            f"""
            SELECT user_id, {column} AS score
            FROM goon_sessions
            WHERE guild_id = ? AND {column} > 0
            ORDER BY {column} DESC, user_id ASC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        return list(await cursor.fetchall())

    async def upsert_goon_group_call(self, payload: dict) -> None:
        async with self._write_lock:
            await self.conn.execute(
                """
                INSERT INTO goon_group_calls (
                    channel_id, guild_id, message_id, phase, amount, condoms,
                    host_id, call_expires_at, round_ends_at, free_join_until,
                    prompt, joiners, edges, leaked, finished
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel_id) DO UPDATE SET
                    guild_id = excluded.guild_id,
                    message_id = excluded.message_id,
                    phase = excluded.phase,
                    amount = excluded.amount,
                    condoms = excluded.condoms,
                    host_id = excluded.host_id,
                    call_expires_at = excluded.call_expires_at,
                    round_ends_at = excluded.round_ends_at,
                    free_join_until = excluded.free_join_until,
                    prompt = excluded.prompt,
                    joiners = excluded.joiners,
                    edges = excluded.edges,
                    leaked = excluded.leaked,
                    finished = excluded.finished
                """,
                (
                    int(payload["channel_id"]),
                    int(payload["guild_id"]),
                    int(payload.get("message_id") or 0),
                    str(payload.get("phase") or "call"),
                    float(payload.get("amount") or 0),
                    int(payload.get("condoms") or 0),
                    int(payload.get("host_id") or 0),
                    float(payload.get("call_expires_at") or 0),
                    float(payload.get("round_ends_at") or 0),
                    float(payload.get("free_join_until") or 0),
                    str(payload.get("prompt") or ""),
                    json.dumps(list(payload.get("joiners") or [])),
                    json.dumps(payload.get("edges") or {}),
                    json.dumps(payload.get("leaked") or {}),
                    json.dumps(payload.get("finished") or {}),
                ),
            )
            await self.conn.commit()

    async def delete_goon_group_call(self, channel_id: int) -> None:
        async with self._write_lock:
            await self.conn.execute(
                "DELETE FROM goon_group_calls WHERE channel_id = ?",
                (channel_id,),
            )
            await self.conn.commit()

    async def list_goon_group_calls(self) -> list[dict]:
        cursor = await self.conn.execute("SELECT * FROM goon_group_calls")
        rows = await cursor.fetchall()
        out: list[dict] = []
        for row in rows:
            def _obj(key: str, default):
                raw = row[key]
                if not raw:
                    return default
                try:
                    return json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    return default

            out.append(
                {
                    "channel_id": int(row["channel_id"]),
                    "guild_id": int(row["guild_id"]),
                    "message_id": int(row["message_id"] or 0),
                    "phase": str(row["phase"] or "call"),
                    "amount": float(row["amount"] or 0),
                    "condoms": int(row["condoms"] or 0),
                    "host_id": int(row["host_id"] or 0),
                    "call_expires_at": float(row["call_expires_at"] or 0),
                    "round_ends_at": float(row["round_ends_at"] or 0),
                    "free_join_until": float(row["free_join_until"] or 0),
                    "prompt": str(row["prompt"] or ""),
                    "joiners": [int(x) for x in _obj("joiners", [])],
                    "edges": {int(k): float(v) for k, v in _obj("edges", {}).items()},
                    "leaked": {int(k): float(v) for k, v in _obj("leaked", {}).items()},
                    "finished": {int(k): float(v) for k, v in _obj("finished", {}).items()},
                }
            )
        return out
