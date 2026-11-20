from django.core.management.base import BaseCommand
from django.db.models import Q

from app.banking import create_account, deposit, transfer, withdraw
from app.models import BankAccount, BankTransaction


class Command(BaseCommand):
    help = "Run the local demo banking CLI."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "MyBank CLI — LOCAL DEMO ONLY. No real money or personal data."
        ))
        self.stdout.write(
            "This prototype has no authentication; account numbers are not credentials."
        )

        while True:
            self.stdout.write("\n1. Create account\n2. Open account\n3. Exit")
            choice = input("Choose an option: ").strip()
            if choice == "1":
                try:
                    account = create_account(input("Account holder name: "))
                except ValueError as error:
                    self.stdout.write(self.style.ERROR(str(error)))
                    continue
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Account created. Your demo account number is {account.account_number}."
                    )
                )
                self._account_menu(account)
            elif choice == "2":
                account_number = input("Account number: ").strip().upper()
                try:
                    account = BankAccount.objects.get(account_number=account_number)
                except BankAccount.DoesNotExist:
                    self.stdout.write(self.style.ERROR("Account was not found."))
                    continue
                self._account_menu(account)
            elif choice == "3":
                self.stdout.write("Goodbye.")
                return
            else:
                self.stdout.write(self.style.ERROR("Choose 1, 2, or 3."))

    def _account_menu(self, account):
        while True:
            self.stdout.write(
                f"\nAccount: {account.owner_name} · {account.account_number}"
                "\n1. Check balance\n2. Deposit\n3. Withdraw"
                "\n4. Transfer\n5. Transaction history\n6. Sign out"
            )
            choice = input("Choose an option: ").strip()
            try:
                if choice == "1":
                    account.refresh_from_db()
                    self.stdout.write(f"Balance: ${account.balance:,.2f}")
                elif choice == "2":
                    account = deposit(
                        account.account_number, input("Deposit amount: $")
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"New balance: ${account.balance:,.2f}")
                    )
                elif choice == "3":
                    account = withdraw(
                        account.account_number, input("Withdrawal amount: $")
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"New balance: ${account.balance:,.2f}")
                    )
                elif choice == "4":
                    destination = input("Destination account number: ").strip().upper()
                    source, _ = transfer(
                        account.account_number,
                        destination,
                        input("Transfer amount: $"),
                    )
                    account = source
                    self.stdout.write(
                        self.style.SUCCESS(f"Transfer complete. Balance: ${account.balance:,.2f}")
                    )
                elif choice == "5":
                    self._show_history(account)
                elif choice == "6":
                    return
                else:
                    self.stdout.write(self.style.ERROR("Choose an option from 1 to 6."))
            except ValueError as error:
                self.stdout.write(self.style.ERROR(str(error)))
            except BankAccount.DoesNotExist:
                self.stdout.write(self.style.ERROR("Account was not found."))

    def _show_history(self, account):
        entries = BankTransaction.objects.filter(
            Q(from_account=account) | Q(to_account=account)
        )[:10]
        if not entries:
            self.stdout.write("No transactions yet.")
            return

        self.stdout.write("Recent transactions:")
        for entry in entries:
            if entry.transaction_type == BankTransaction.Type.DEPOSIT:
                direction = "Deposit"
                signed_amount = f"+${entry.amount:,.2f}"
            elif entry.transaction_type == BankTransaction.Type.WITHDRAWAL:
                direction = "Withdrawal"
                signed_amount = f"-${entry.amount:,.2f}"
            elif entry.from_account_id == account.pk:
                direction = f"Transfer to {entry.to_account.account_number}"
                signed_amount = f"-${entry.amount:,.2f}"
            else:
                direction = f"Transfer from {entry.from_account.account_number}"
                signed_amount = f"+${entry.amount:,.2f}"
            self.stdout.write(f"{entry.created_at:%Y-%m-%d %H:%M}  {direction}: {signed_amount}")
