from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from arg_options.broker.exceptions import BrokerError
from arg_options.broker.interfaces import AccountService
from arg_options.broker.models import (
    Account,
    Balance,
    BalancesAndPositions,
    BankAccount,
    CurrencyAvailability,
    InvestingProfile,
    InvestingProfileAnswer,
    InvestingProfileQuestion,
    Movement,
    Officer,
    Position,
)
from ppi_client.models.account_movements import AccountMovements as PpiAccountMovements
from ppi_client.models.bank_account_request import BankAccountRequest
from ppi_client.models.cancel_bank_account_request import CancelBankAccountRequest
from ppi_client.models.investing_profile import (
    InvestingProfile as PpiInvestingProfile,
)
from ppi_client.models.investing_profile_answer import (
    InvestingProfileAnswer as PpiInvestingProfileAnswer,
)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class PpiAccountService(AccountService):
    def __init__(self, ppi: Any) -> None:
        self._ppi = ppi

    def get_accounts(self) -> list[Account]:
        try:
            data = self._ppi.account.get_accounts()
            results = []
            for d in data:
                officer = None
                if d.get("officer"):
                    officer = Officer(
                        name=d["officer"].get("name", ""),
                        email=d["officer"].get("eMail", ""),
                        phone=d["officer"].get("phone", ""),
                    )
                results.append(
                    Account(
                        account_number=d.get("accountNumber", ""),
                        name=d.get("name", ""),
                        officer=officer,
                    )
                )
            return results
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_bank_accounts(self, account_number: str) -> list[BankAccount]:
        try:
            data = self._ppi.account.get_bank_accounts(account_number)
            return [
                BankAccount(
                    bank_name=d.get("bankName", ""),
                    bank_account_number=d.get("bankAccountNumber", ""),
                    bank_identifier=d.get("bankIdentifier", ""),
                    currency=d.get("currency", ""),
                    tax_holder_identifier=d.get("taxHolderIdentifier", ""),
                )
                for d in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_available_balance(self, account_number: str) -> list[Balance]:
        try:
            data = self._ppi.account.get_available_balance(account_number)
            return [
                Balance(
                    name=d.get("name", ""),
                    symbol=d.get("simbol", ""),
                    amount=d.get("amount", 0),
                    settlement=d.get("settlement", ""),
                )
                for d in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_balance_and_positions(
        self, account_number: str
    ) -> BalancesAndPositions:
        try:
            data = self._ppi.account.get_balance_and_positions(account_number)

            grouped_availability = []
            for group in data.get("groupedAvailability", []):
                availabilities = [
                    Balance(
                        name=b.get("name", ""),
                        symbol=b.get("simbol", ""),
                        amount=b.get("amount", 0),
                        settlement=b.get("settlement", ""),
                    )
                    for b in group.get("availability", [])
                ]
                grouped_availability.append(
                    CurrencyAvailability(
                        currency=group.get("currency", ""),
                        availability=availabilities,
                    )
                )

            positions = []
            for group in data.get("groupedInstruments", []):
                group_name = group.get("name", "")
                for inst in group.get("instruments", []):
                    positions.append(
                        Position(
                            ticker=inst.get("ticker", ""),
                            price=inst.get("price", 0),
                            amount=inst.get("amount", 0),
                            instrument=group_name,
                        )
                    )

            return BalancesAndPositions(
                grouped_availability=grouped_availability,
                grouped_instruments=positions,
            )
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_movements(
        self,
        account_number: str,
        date_from: datetime,
        date_to: datetime,
        ticker: Optional[str] = None,
    ) -> list[Movement]:
        try:
            ppi_movements = PpiAccountMovements(
                account_number=account_number,
                date_from=date_from,
                date_to=date_to,
                ticker=ticker,
            )
            data = self._ppi.account.get_movements(ppi_movements)
            return [
                Movement(
                    agreement_date=_parse_datetime(m.get("agreementDate")),
                    settlement_date=_parse_datetime(m.get("settlementDate")),
                    currency=m.get("currency", ""),
                    amount=m.get("amount", 0),
                    price=m.get("price", 0),
                    description=m.get("description", ""),
                    ticker=m.get("ticker"),
                    quantity=m.get("quantity", 0),
                    balance=m.get("balance", 0),
                )
                for m in data
            ]
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_investing_profile_questions(self) -> list[InvestingProfileQuestion]:
        try:
            data = self._ppi.account.get_investing_profile_questions()
            results = []
            for q in data:
                answers = [
                    InvestingProfileAnswer(
                        question_code=a.get("questionCode", ""),
                        answer_code=a.get("answerCode", ""),
                    )
                    for a in q.get("answers", [])
                ]
                results.append(
                    InvestingProfileQuestion(
                        code=q.get("code", ""),
                        description=q.get("description", ""),
                        answers=answers,
                    )
                )
            return results
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_investing_profile_instrument_types(self) -> list[str]:
        try:
            return self._ppi.account.get_investing_profile_instrument_types()
        except Exception as e:
            raise BrokerError(str(e)) from e

    def get_investing_profile(self, account_number: str) -> InvestingProfile:
        try:
            data = self._ppi.account.get_investing_profile(account_number)
            return InvestingProfile(
                date=_parse_datetime(data.get("date")),
                type=data.get("type", ""),
                description=data.get("description", ""),
            )
        except Exception as e:
            raise BrokerError(str(e)) from e

    def set_investing_profile(
        self,
        account_number: str,
        answers: list[dict],
        instrument_types: list[str],
    ) -> InvestingProfile:
        try:
            ppi_answers = [
                PpiInvestingProfileAnswer(
                    question_code=a["question_code"],
                    answer_code=a["answer_code"],
                )
                for a in answers
            ]
            ppi_profile = PpiInvestingProfile(
                answers=ppi_answers,
                instrument_types=instrument_types,
            )
            data = self._ppi.account.set_investing_profile(ppi_profile)
            return InvestingProfile(
                date=_parse_datetime(data.get("date")),
                type=data.get("type", ""),
                description=data.get("description", ""),
            )
        except Exception as e:
            raise BrokerError(str(e)) from e

    def register_bank_account(
        self,
        account_number: str,
        currency: str,
        cbu: str,
        cuit: str,
        alias: str,
        bank_account_number: str,
    ) -> str:
        try:
            request = BankAccountRequest(
                account_number=account_number,
                currency=currency,
                cbu=cbu,
                cuit=cuit,
                alias=alias,
                bank_account_number=bank_account_number,
            )
            result = self._ppi.account.register_bank_account(request)
            return str(result)
        except Exception as e:
            raise BrokerError(str(e)) from e

    def cancel_bank_account(
        self,
        account_number: str,
        cbu: str,
        bank_account_number: str,
    ) -> str:
        try:
            request = CancelBankAccountRequest(
                account_number=account_number,
                cbu=cbu,
                bank_account_number=bank_account_number,
            )
            result = self._ppi.account.cancel_bank_account(request)
            return str(result)
        except Exception as e:
            raise BrokerError(str(e)) from e
