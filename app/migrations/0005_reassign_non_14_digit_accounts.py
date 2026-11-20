import uuid

from django.db import migrations


def reassign_non_14_digit_accounts(apps, schema_editor):
    bank_account = apps.get_model("app", "BankAccount")
    database = schema_editor.connection.alias

    for account in bank_account.objects.using(database).iterator():
        number = account.account_number
        if len(number) == 14 and number.isascii() and number.isdigit():
            continue

        while True:
            replacement = f"{uuid.uuid4().int % 10**14:014d}"
            exists = bank_account.objects.using(database).filter(
                account_number=replacement
            ).exists()
            if not exists:
                bank_account.objects.using(database).filter(pk=account.pk).update(
                    account_number=replacement
                )
                break


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_alter_bankaccount_account_number"),
    ]

    operations = [
        migrations.RunPython(
            reassign_non_14_digit_accounts,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
