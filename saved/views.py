from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import DeleteView, ListView, UpdateView

from contracts.models import Contract

from .forms import SavedContractForm
from .models import SavedContract


def go_back(request, fallback):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(fallback)


@login_required
@require_POST
def toggle_save(request, notice_id):
    contract = get_object_or_404(Contract, notice_id=notice_id)
    saved = SavedContract.objects.filter(user=request.user, contract=contract)
    if saved.exists():
        saved.delete()
        now_saved = False
    else:
        SavedContract.objects.create(user=request.user, contract=contract)
        now_saved = True
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"saved": now_saved})
    messages.success(request, "Saved." if now_saved else "Removed from saved jobs.")
    return go_back(request, contract.get_absolute_url())


class MySavedMixin(LoginRequiredMixin):
    """Users can only see and change their own saved jobs."""

    def get_queryset(self):
        return SavedContract.objects.filter(user=self.request.user).select_related("contract", "contract__agency")


class SavedListView(MySavedMixin, ListView):
    template_name = "saved/saved_list.html"
    context_object_name = "saved"


class SavedUpdateView(MySavedMixin, UpdateView):
    form_class = SavedContractForm
    template_name = "saved/saved_form.html"
    success_url = reverse_lazy("saved:list")

    def form_valid(self, form):
        messages.success(self.request, "Your changes are saved.")
        return super().form_valid(form)


class SavedDeleteView(MySavedMixin, DeleteView):
    template_name = "saved/saved_confirm_delete.html"
    success_url = reverse_lazy("saved:list")

    def form_valid(self, form):
        messages.success(self.request, "Removed from your saved jobs.")
        return super().form_valid(form)
