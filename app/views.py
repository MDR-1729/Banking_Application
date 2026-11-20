from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from app.banking import create_account, deposit, normalize_account_number, withdraw
from app.models import BankAccount, BankTransaction


def dashboard(request):
    """Show accounts, balances, and transaction history from the database."""
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create":
                account = create_account(
                    request.POST.get("owner_name", ""),
                    request.POST.get("account_number", ""),
                )
                messages.success(
                    request,
                    f"Account created for {account.owner_name} "
                    f"({account.account_number}).",
                )
            elif action == "edit":
                account_number = normalize_account_number(
                    request.POST.get("account_number", "")
                )
                account = BankAccount.objects.get(account_number=account_number)
                owner_name = request.POST.get("owner_name", "").strip()
                if not owner_name:
                    raise ValueError("Account holder name cannot be empty.")
                if len(owner_name) > 120:
                    raise ValueError(
                        "Account holder name must be 120 characters or fewer."
                    )

                updated_account_number = normalize_account_number(
                    request.POST.get("updated_account_number", "")
                )
                if BankAccount.objects.filter(
                    account_number=updated_account_number
                ).exclude(pk=account.pk).exists():
                    raise ValueError("Account number already exists.")

                account.owner_name = owner_name
                account.account_number = updated_account_number
                try:
                    with transaction.atomic():
                        account.save(update_fields=["owner_name", "account_number"])
                except IntegrityError:
                    raise ValueError("Account number already exists.") from None
                messages.success(
                    request,
                    f"Account updated for {account.owner_name} "
                    f"({account.account_number}).",
                )
            elif action in {"deposit", "withdraw"}:
                account_number = request.POST.get("account_number", "").strip()
                amount = request.POST.get("amount", "")
                account = (
                    deposit(account_number, amount)
                    if action == "deposit"
                    else withdraw(account_number, amount)
                )
                verb = "Deposited to" if action == "deposit" else "Withdrawn from"
                messages.success(
                    request,
                    f"{verb} {account.account_number}. "
                    f"New balance: ₹{account.balance:,.2f}.",
                )
            elif action == "delete":
                if request.POST.get("confirm_delete") != "yes":
                    raise ValueError("Confirm account deletion to continue.")
                account_number = normalize_account_number(
                    request.POST.get("account_number", "")
                )
                account = BankAccount.objects.get(account_number=account_number)
                account.delete()
                messages.success(
                    request,
                    "Account deleted. Its transaction history has been preserved.",
                )
            else:
                messages.error(request, "Choose a valid banking action.")
        except ValueError as error:
            messages.error(request, str(error))
        except BankAccount.DoesNotExist:
            messages.error(request, "Account not found.")
        return redirect("dashboard")

    accounts = BankAccount.objects.order_by("created_at", "pk")
    transactions = BankTransaction.objects.select_related(
        "from_account", "to_account"
    )

    active_filter = request.GET.get("type", "all")
    search_query = request.GET.get("q", "").strip()

    if active_filter in {"income", "expenses"}:
        transaction_type = (
            BankTransaction.Type.DEPOSIT
            if active_filter == "income"
            else BankTransaction.Type.WITHDRAWAL
        )
        transactions = transactions.filter(transaction_type=transaction_type)
    else:
        active_filter = "all"

    if search_query:
        transactions = transactions.filter(
            Q(from_account__account_number__icontains=search_query)
            | Q(from_account__owner_name__icontains=search_query)
            | Q(to_account__account_number__icontains=search_query)
            | Q(to_account__owner_name__icontains=search_query)
            | Q(from_account_number__icontains=search_query)
            | Q(from_account_name__icontains=search_query)
            | Q(to_account_number__icontains=search_query)
            | Q(to_account_name__icontains=search_query)
        )

    customers = BankAccount.objects.order_by("owner_name").values_list(
        "owner_name",
        flat=True,
    ).distinct()
    selected_customer = request.GET.get("customer", "").strip()
    customer_balance = None
    customer_account_count = 0
    if selected_customer:
        customer_summary = BankAccount.objects.filter(
            owner_name=selected_customer
        ).aggregate(total=Sum("balance"), account_count=Count("pk"))
        customer_account_count = customer_summary["account_count"]
        if customer_account_count:
            customer_balance = customer_summary["total"] or Decimal("0.00")
        else:
            selected_customer = ""

    return render(
        request,
        "app/dashboard.html",
        {
            "accounts": accounts,
            "customers": customers,
            "selected_customer": selected_customer,
            "customer_balance": customer_balance,
            "customer_account_count": customer_account_count,
            "customer_count": BankAccount.objects.values("owner_name")
            .distinct()
            .count(),
            "total_balance": BankAccount.objects.aggregate(
                total=Sum("balance")
            )["total"]
            or Decimal("0.00"),
            "transactions": transactions,
            "active_filter": active_filter,
            "search_query": search_query,
        },
    )


@require_GET
def account_lookup(request):
    try:
        account_number = normalize_account_number(
            request.GET.get("account_number", "")
        )
    except ValueError as error:
        return JsonResponse({"found": False, "message": str(error)}, status=400)

    account = BankAccount.objects.filter(account_number=account_number).only(
        "owner_name"
    ).first()
    if account is None:
        return JsonResponse(
            {"found": False, "message": "Account not found."},
            status=404,
        )
    return JsonResponse({"found": True, "owner_name": account.owner_name})
