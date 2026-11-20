import uuid

from django.core.validators import RegexValidator
from django.db import models


def generate_account_number():
    return f"{uuid.uuid4().int % 10**14:014d}"


class BankAccount(models.Model):
    account_number = models.CharField(
        max_length=14,
        unique=True,
        default=generate_account_number,
        validators=[
            RegexValidator(
                r"\A[0-9]{14}\Z",
                "Account number must be exactly 14 digits.",
            )
        ],
    )
    owner_name = models.CharField(max_length=120)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner_name} ({self.account_number})"


class BankTransaction(models.Model):
    class Type(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        TRANSFER = "transfer", "Transfer"

    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    from_account = models.ForeignKey(
        BankAccount,
        related_name="outgoing_transactions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    to_account = models.ForeignKey(
        BankAccount,
        related_name="incoming_transactions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    from_account_number = models.CharField(max_length=14, blank=True, default="")
    from_account_name = models.CharField(max_length=120, blank=True, default="")
    to_account_number = models.CharField(max_length=14, blank=True, default="")
    to_account_name = models.CharField(max_length=120, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def save(self, *args, **kwargs):
        if self.from_account_id:
            account = self.from_account
            self.from_account_number = (
                self.from_account_number or account.account_number
            )
            self.from_account_name = self.from_account_name or account.owner_name
        if self.to_account_id:
            account = self.to_account
            self.to_account_number = self.to_account_number or account.account_number
            self.to_account_name = self.to_account_name or account.owner_name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.amount}"
