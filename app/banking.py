from decimal import Decimal, InvalidOperation
from django.db import transaction
from app.models import BankAccount, BankTransaction

MAX_BALANCE = Decimal("9999999999.99")
CENT = Decimal("0.01")

def normalize_account_number(value):
    if not isinstance(value, str):
        raise ValueError("Account number must be exactly 14 digits.")
    account_number = value.strip()
    if (
        len(account_number) != 14
        or not account_number.isascii()
        or not account_number.isdigit()
    ):
        raise ValueError("Account number must be exactly 14 digits.")
    return account_number

def parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount.") from None

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    if amount > MAX_BALANCE:
        raise ValueError("Amount is too large.")
    if amount != amount.quantize(CENT):
        raise ValueError("Amount must have no more than two decimal places.")
    return amount

def create_account(owner_name, account_number=None):
    owner_name = owner_name.strip()
    if not owner_name:
        raise ValueError("Account holder name cannot be empty.")
    if len(owner_name) > 120:
        raise ValueError("Account holder name must be 120 characters or fewer.")
    if account_number is not None:
        account_number = normalize_account_number(account_number)
        if BankAccount.objects.filter(account_number=account_number).exists():
            raise ValueError("Account already exists.")
        return BankAccount.objects.create(
            owner_name=owner_name,
            account_number=account_number,
        )
    return BankAccount.objects.create(owner_name=owner_name)

@transaction.atomic
def deposit(account_number, value):
    account_number = normalize_account_number(account_number)
    amount = parse_amount(value)
    account = BankAccount.objects.select_for_update().get(
        account_number=account_number
    )
    if account.balance + amount > MAX_BALANCE:
        raise ValueError("Deposit would exceed the maximum account balance.")

    account.balance += amount
    account.save(update_fields=["balance"])
    BankTransaction.objects.create(
        transaction_type=BankTransaction.Type.DEPOSIT,
        to_account=account,
        amount=amount,
    )
    return account

@transaction.atomic
def withdraw(account_number, value):
    account_number = normalize_account_number(account_number)
    amount = parse_amount(value)
    account = BankAccount.objects.select_for_update().get(
        account_number=account_number
    )
    if account.balance < amount:
        raise ValueError("Insufficient funds.")

    account.balance -= amount
    account.save(update_fields=["balance"])
    BankTransaction.objects.create(
        transaction_type=BankTransaction.Type.WITHDRAWAL,
        from_account=account,
        amount=amount,
    )
    return account

@transaction.atomic
def transfer(from_account_number, to_account_number, value):
    from_account_number = normalize_account_number(from_account_number)
    to_account_number = normalize_account_number(to_account_number)
    if from_account_number == to_account_number:
        raise ValueError("Choose a different destination account.")
    amount = parse_amount(value)

    accounts = {
        account.account_number: account
        for account in BankAccount.objects.select_for_update()
        .filter(account_number__in=[from_account_number, to_account_number])
        .order_by("account_number")
    }
    if from_account_number not in accounts:
        raise BankAccount.DoesNotExist
    if to_account_number not in accounts:
        raise ValueError("Destination account was not found.")

    source = accounts[from_account_number]
    destination = accounts[to_account_number]
    if source.balance < amount:
        raise ValueError("Insufficient funds.")
    if destination.balance + amount > MAX_BALANCE:
        raise ValueError("Transfer would exceed the destination account balance limit.")

    source.balance -= amount
    destination.balance += amount
    source.save(update_fields=["balance"])
    destination.save(update_fields=["balance"])
    BankTransaction.objects.create(
        transaction_type=BankTransaction.Type.TRANSFER,
        from_account=source,
        to_account=destination,
        amount=amount,
    )
    return source, destination