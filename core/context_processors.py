from saved.models import SavedContract


def saved_ids(request):
    """IDs of the contracts this user saved, so any page can show a filled Save button."""
    if not request.user.is_authenticated:
        return {"saved_ids": set()}
    return {"saved_ids": set(SavedContract.objects.filter(user=request.user).values_list("contract_id", flat=True))}
