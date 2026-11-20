from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.contrib import admin
from django.test import TestCase

from app.banking import create_account, deposit, transfer, withdraw
from app.models import BankAccount, BankTransaction


class DashboardTests(TestCase):
    def test_account_lookup_verifies_holder_for_14_digit_numbers(self):
        account = BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan Davis",
        )

        response = self.client.get(
            "/accounts/lookup/",
            {"account_number": account.account_number},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"found": True, "owner_name": "Jordan Davis"},
        )

        response = self.client.get(
            "/accounts/lookup/",
            {"account_number": "123"},
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/accounts/lookup/",
            {"account_number": "12345678901235"},
        )
        self.assertEqual(response.status_code, 404)

    def test_dashboard_shows_database_accounts_and_real_transactions(self):
        account = BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan Davis",
            balance=Decimal("25.00"),
        )
        deposit(account.account_number, "10.00")

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Davis")
        self.assertContains(response, "12345678901234")
        self.assertContains(response, "₹35.00")
        self.assertContains(response, "Deposit")
        self.assertContains(response, 'maxlength="14"')
        self.assertContains(response, "ACCOUNT NUMBER")
        self.assertContains(response, "ACCOUNT HOLDER NAME")
        self.assertContains(response, "BANKING APPLICATION")
        self.assertContains(response, "Add an account")
        self.assertNotContains(response, "Banking Mini Project")

    def test_account_edit_and_delete_panels_have_close_buttons(self):
        BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan Davis",
        )

        response = self.client.get("/")

        self.assertContains(response, 'aria-label="Close edit account options"')
        self.assertContains(response, 'aria-label="Close delete account options"')
        self.assertContains(response, 'class="account-close" type="button"')

    def test_selected_customer_balance_is_separate_from_bank_wide_balance(self):
        BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan Davis",
            balance=Decimal("125.00"),
        )
        BankAccount.objects.create(
            account_number="12345678901235",
            owner_name="Jordan Davis",
            balance=Decimal("75.00"),
        )
        BankAccount.objects.create(
            account_number="12345678901236",
            owner_name="Riley Chen",
            balance=Decimal("300.00"),
        )

        response = self.client.get("/", {"customer": "Jordan Davis"})

        self.assertEqual(response.context["customer_balance"], Decimal("200.00"))
        self.assertEqual(response.context["customer_account_count"], 2)
        self.assertEqual(response.context["total_balance"], Decimal("500.00"))
        self.assertContains(response, "₹200.00")
        self.assertContains(response, "₹500.00")
        self.assertContains(response, "Total bank balance")
        self.assertContains(response, "total-bank-icon")

    def test_account_can_be_edited_without_changing_transaction_history(self):
        account = BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan Davis",
            balance=Decimal("25.00"),
        )
        deposit(account.account_number, "10.00")

        response = self.client.post(
            "/",
            {
                "action": "edit",
                "account_number": account.account_number,
                "owner_name": "Jordan Smith",
                "updated_account_number": "12345678901235",
            },
            follow=True,
        )

        account.refresh_from_db()
        self.assertEqual(account.owner_name, "Jordan Smith")
        self.assertEqual(account.account_number, "12345678901235")
        self.assertEqual(account.balance, Decimal("35.00"))
        transaction_record = BankTransaction.objects.get()
        self.assertEqual(transaction_record.to_account_name, "Jordan Davis")
        self.assertEqual(transaction_record.to_account_number, "12345678901234")
        self.assertContains(response, "Account updated for Jordan Smith")
        self.assertContains(response, "Edit account")

    def test_account_edit_rejects_duplicate_or_invalid_details(self):
        account = BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan Davis",
        )
        BankAccount.objects.create(
            account_number="12345678901235",
            owner_name="Riley Chen",
        )

        response = self.client.post(
            "/",
            {
                "action": "edit",
                "account_number": account.account_number,
                "owner_name": "Jordan Smith",
                "updated_account_number": "12345678901235",
            },
            follow=True,
        )
        self.assertContains(response, "Account number already exists.")

        response = self.client.post(
            "/",
            {
                "action": "edit",
                "account_number": account.account_number,
                "owner_name": "Jordan Smith",
                "updated_account_number": "123",
            },
            follow=True,
        )
        self.assertContains(response, "Account number must be exactly 14 digits.")

        response = self.client.post(
            "/",
            {
                "action": "edit",
                "account_number": account.account_number,
                "owner_name": " ",
                "updated_account_number": account.account_number,
            },
            follow=True,
        )
        self.assertContains(response, "Account holder name cannot be empty.")

        account.refresh_from_db()
        self.assertEqual(account.owner_name, "Jordan Davis")
        self.assertEqual(account.account_number, "12345678901234")

    def test_create_account_and_deposit_and_withdraw_from_dashboard(self):
        create_response = self.client.post(
            "/",
            {
                "action": "create",
                "owner_name": "Taylor Jordan",
                "account_number": "12345678901235",
            },
        )
        account = BankAccount.objects.get(owner_name="Taylor Jordan")
        self.assertEqual(account.account_number, "12345678901235")
        self.assertRedirects(create_response, "/")

        self.client.post(
            "/",
            {
                "action": "deposit",
                "account_number": account.account_number,
                "amount": "25.50",
            },
        )
        self.client.post(
            "/",
            {
                "action": "withdraw",
                "account_number": account.account_number,
                "amount": "5.50",
            },
        )
        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("20.00"))
        self.assertEqual(BankTransaction.objects.count(), 2)

    def test_invalid_operation_keeps_balance_unchanged_and_shows_error(self):
        account = BankAccount.objects.create(
            account_number="12345678901234",
            owner_name="Jordan",
        )
        response = self.client.post(
            "/",
            {
                "action": "withdraw",
                "account_number": account.account_number,
                "amount": "1.00",
            },
            follow=True,
        )

        account.refresh_from_db()
        self.assertEqual(account.balance, Decimal("0.00"))
        self.assertContains(response, "Insufficient funds.")
        self.assertFalse(BankTransaction.objects.exists())

    def test_confirmed_account_deletion_preserves_searchable_transaction_history(self):
        account = BankAccount.objects.create(owner_name="Jordan")
        deposit(account.account_number, "20.00")
        withdraw(account.account_number, "5.00")

        response = self.client.post(
            "/",
            {
                "action": "delete",
                "account_number": account.account_number,
                "confirm_delete": "yes",
            },
            follow=True,
        )

        self.assertFalse(BankAccount.objects.filter(pk=account.pk).exists())
        self.assertEqual(BankTransaction.objects.count(), 2)
        deposit_record = BankTransaction.objects.get(
            transaction_type=BankTransaction.Type.DEPOSIT
        )
        self.assertIsNone(deposit_record.to_account)
        self.assertEqual(deposit_record.to_account_number, account.account_number)
        self.assertEqual(deposit_record.to_account_name, "Jordan")
        self.assertContains(response, "transaction history has been preserved")
        self.assertContains(response, account.account_number)
        self.assertContains(response, "ACCOUNT HOLDER NAME")
        self.assertEqual(len(response.context["transactions"]), 2)

        withdrawal_record = BankTransaction.objects.get(
            transaction_type=BankTransaction.Type.WITHDRAWAL
        )
        self.assertIsNone(withdrawal_record.from_account)
        self.assertEqual(withdrawal_record.from_account_number, account.account_number)
        self.assertEqual(withdrawal_record.from_account_name, "Jordan")

        search_response = self.client.get("/", {"q": account.account_number})
        self.assertContains(search_response, "Jordan")

    def test_account_deletion_requires_explicit_confirmation(self):
        account = BankAccount.objects.create(owner_name="Jordan")

        response = self.client.post(
            "/",
            {
                "action": "delete",
                "account_number": account.account_number,
            },
            follow=True,
        )

        self.assertTrue(BankAccount.objects.filter(pk=account.pk).exists())
        self.assertContains(response, "Confirm account deletion to continue.")

    def test_account_and_transaction_models_are_registered_in_admin(self):
        self.assertIn(BankAccount, admin.site._registry)
        self.assertIn(BankTransaction, admin.site._registry)


class BankingServiceTests(TestCase):
    def setUp(self):
        self.jordan = BankAccount.objects.create(owner_name="Jordan Davis")
        self.riley = BankAccount.objects.create(owner_name="Riley Chen")

    def test_deposit_withdraw_and_transfer_update_balances_and_history(self):
        deposit(self.jordan.account_number, "50.00")
        transfer(self.jordan.account_number, self.riley.account_number, "12.35")
        withdraw(self.riley.account_number, "2.35")

        self.jordan.refresh_from_db()
        self.riley.refresh_from_db()
        self.assertEqual(self.jordan.balance, Decimal("37.65"))
        self.assertEqual(self.riley.balance, Decimal("10.00"))
        self.assertEqual(BankTransaction.objects.count(), 3)

    def test_invalid_or_unfunded_withdrawal_does_not_change_balance(self):
        with self.assertRaisesMessage(ValueError, "Amount must have no more"):
            deposit(self.jordan.account_number, "1.001")
        with self.assertRaisesMessage(ValueError, "Insufficient funds"):
            withdraw(self.jordan.account_number, "1.00")

        self.jordan.refresh_from_db()
        self.assertEqual(self.jordan.balance, Decimal("0.00"))
        self.assertFalse(BankTransaction.objects.exists())

    def test_account_numbers_must_be_exactly_14_ascii_digits(self):
        for invalid_number in (
            "123456789012345",
            "1234567890123456",
            "1234567890123",
            "1234567890123A",
            "１２３４５６７８９０１２３４",
        ):
            with self.subTest(account_number=invalid_number):
                with self.assertRaisesMessage(
                    ValueError,
                    "Account number must be exactly 14 digits.",
                ):
                    create_account("Taylor Jordan", invalid_number)

        account = create_account("Taylor Jordan", "12345678901235")
        self.assertEqual(account.account_number, "12345678901235")

    def test_cli_creates_account_and_records_deposit(self):
        output = StringIO()
        with patch(
            "builtins.input",
            side_effect=["1", "Taylor Jordan", "2", "25.00", "6", "3"],
        ):
            call_command("bank", stdout=output)

        account = BankAccount.objects.get(owner_name="Taylor Jordan")
        self.assertEqual(account.balance, Decimal("25.00"))
        self.assertEqual(len(account.account_number), 14)
        self.assertTrue(account.account_number.isascii() and account.account_number.isdigit())
        self.assertIn("Account created.", output.getvalue())
        self.assertIn("New balance: $25.00", output.getvalue())
