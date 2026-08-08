"""Per-Run cancellation, deadline, and model budget enforcement."""

import asyncio
from datetime import UTC, datetime

from app.agent.errors import (
    AgentDeadlineExceededError,
    BudgetExceededError,
    RunCancelledError,
    StructuredOutputError,
)
from app.schemas.agent_runs import RuntimeConfigSnapshot


class CancellationToken:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RunCancelledError


class BudgetGuard:
    def __init__(
        self,
        config: RuntimeConfigSnapshot,
        deadline_at: datetime,
        cancellation: CancellationToken,
    ) -> None:
        self._config = config
        self._deadline_at = deadline_at
        self._cancellation = cancellation
        self.llm_calls = 0
        self.format_repairs = 0
        self.business_repairs = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def check(self) -> None:
        self._cancellation.raise_if_cancelled()
        if datetime.now(UTC) >= self._deadline_at:
            raise AgentDeadlineExceededError
        if self.tokens_in + self.tokens_out > self._config.max_total_tokens:
            raise BudgetExceededError(
                "total_tokens "
                f"{self.tokens_in + self.tokens_out} > {self._config.max_total_tokens}"
            )

    def remaining_seconds(self) -> float:
        self.check()
        return max((self._deadline_at - datetime.now(UTC)).total_seconds(), 0.001)

    def record_llm_call(self, tokens_in: int, tokens_out: int) -> None:
        if self.llm_calls >= self._config.max_llm_calls:
            raise BudgetExceededError(
                f"llm_calls {self.llm_calls + 1} > {self._config.max_llm_calls}"
            )
        if tokens_in > self._config.max_input_tokens_per_call:
            raise BudgetExceededError(
                "input_tokens "
                f"{tokens_in} > {self._config.max_input_tokens_per_call}"
            )
        if tokens_out > self._config.max_output_tokens_per_call:
            raise BudgetExceededError(
                "output_tokens "
                f"{tokens_out} > {self._config.max_output_tokens_per_call}"
            )
        self.llm_calls += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.check()

    def claim_format_repair(self) -> None:
        if self.format_repairs >= 1:
            raise StructuredOutputError
        self.format_repairs += 1

    def claim_business_repair(self) -> bool:
        if self.business_repairs >= 1:
            return False
        self.business_repairs += 1
        return True
