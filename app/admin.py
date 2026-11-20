from django.contrib import admin
from app.models import BankAccount, BankTransaction

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("account_number", "owner_name", "balance", "created_at")
    search_fields = ("account_number", "owner_name")
    readonly_fields = ("created_at",)

@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_type",
        "from_account_number",
        "from_account_name",
        "to_account_number",
        "to_account_name",
        "amount",
        "created_at",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = (
        "from_account_number",
        "from_account_name",
        "to_account_number",
        "to_account_name",
    )
    readonly_fields = (
        "created_at",
        "from_account_number",
        "from_account_name",
        "to_account_number",
        "to_account_name",
    )
