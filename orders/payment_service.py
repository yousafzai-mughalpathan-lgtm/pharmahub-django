from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional
import uuid


@dataclass
class PaymentServiceResult:
    success: bool
    message: str
    transaction_id: str = ""
    amount: Optional[Decimal] = None
    status: str = "failed"  # pending/success/failed for Payment model
    response_data: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "transaction_id": self.transaction_id,
            "amount": str(self.amount) if self.amount is not None else None,
            "status": self.status,
            "response_data": self.response_data or {},
        }


class PaymentService:
    """Payment logic abstraction.

    In this project we don't integrate real gateways; instead we simulate
    successful/failed outcomes for examiner tests and store a Payment row.
    """

    def process_payment(self, order, gateway: str, test_mode: bool = True) -> Dict[str, Any]:
        """Process payment and persist a Payment row.

        Returns a dict used by templates via session.
        """
        from .models import Payment

        amount = getattr(order, "total_amount", None)
        if amount is None:
            amount = Decimal("0.00")

        # COD: no external transaction.
        if gateway == 'COD':
            result = PaymentServiceResult(
                success=True,
                message="Order confirmed (Cash on Delivery).",
                transaction_id="",
                amount=amount,
                status="success",
                response_data={"gateway": gateway, "mode": "COD"},
            )

            Payment.objects.update_or_create(
                order=order,
                defaults={
                    "gateway": gateway,
                    "transaction_id": "",
                    "amount": amount,
                    "status": "success",
                    "response_data": result.response_data or {},
                },
            )
            return result.to_dict()

        # Non-COD: simulate gateway transaction
        if test_mode:
            forced_fail = str(gateway).lower() in {"fail", "failed"}
            if forced_fail:
                result = PaymentServiceResult(
                    success=False,
                    message="Payment failed.",
                    transaction_id="",
                    amount=amount,
                    status="failed",
                    response_data={"gateway": gateway, "mode": "test", "reason": "forced_fail"},
                )
            else:
                txn = f"TXN-{uuid.uuid4().hex[:12].upper()}"
                result = PaymentServiceResult(
                    success=True,
                    message="Payment successful.",
                    transaction_id=txn,
                    amount=amount,
                    status="success",
                    response_data={
                        "gateway": gateway,
                        "mode": "test",
                        "transaction_id": txn,
                    },
                )

            Payment.objects.update_or_create(
                order=order,
                defaults={
                    "gateway": gateway,
                    "transaction_id": result.transaction_id,
                    "amount": amount,
                    "status": result.status,
                    "response_data": result.response_data or {},
                },
            )
            return result.to_dict()

        # Non-test (real integration not implemented)
        result = PaymentServiceResult(
            success=False,
            message="Real payment gateway integration not configured.",
            transaction_id="",
            amount=amount,
            status="failed",
            response_data={"gateway": gateway, "mode": "prod", "reason": "not_configured"},
        )
        Payment.objects.update_or_create(
            order=order,
            defaults={
                "gateway": gateway,
                "transaction_id": "",
                "amount": amount,
                "status": "failed",
                "response_data": result.response_data or {},
            },
        )
        return result.to_dict()

