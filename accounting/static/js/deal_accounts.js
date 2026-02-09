/**
 * صفحه دفتر حساب معامله: مودال جزئیات معامله، تراکنش‌های حساب، رسید، ثبت تراکنش.
 * تنظیمات از window.DEAL_ACCOUNTS_CONFIG خوانده می‌شود: paymentsByAccount, paymentUrl
 */
(function () {
  "use strict";

  var config = window.DEAL_ACCOUNTS_CONFIG || {};
  var paymentsByAccount = config.paymentsByAccount || {};
  var paymentUrl = config.paymentUrl || "";
  var dealId = config.dealId;
  var canApprovePending = config.canApprovePending;
  var approvePendingUrlTemplate = config.approvePendingUrlTemplate || "";
  var rejectPendingUrlTemplate = config.rejectPendingUrlTemplate || "";

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function setModalOpen(overlay, open) {
    if (!overlay) return;
    overlay.style.display = open ? "flex" : "none";
    overlay.setAttribute("aria-hidden", open ? "false" : "true");
    document.body.style.overflow = open ? "hidden" : "";
  }

  function formatAmount(value) {
    if (value == null) return "\u06F0";
    try {
      return Number(value).toLocaleString("fa-IR");
    } catch (e) {
      return String(value);
    }
  }

  function initDealDetailModal() {
    var overlay = document.getElementById("dealDetailModal");
    var openBtn = document.getElementById("openDealDetailModal");
    var closeBtn = document.getElementById("dealDetailModalClose");
    if (openBtn && overlay) openBtn.addEventListener("click", function () { setModalOpen(overlay, true); });
    if (closeBtn && overlay) closeBtn.addEventListener("click", function () { setModalOpen(overlay, false); });
    if (overlay) overlay.addEventListener("click", function (e) { if (e.target && e.target.id === "dealDetailModal") setModalOpen(overlay, false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setModalOpen(overlay, false); });
  }

  function initPaymentsModal() {
    var overlay = document.getElementById("paymentsModal");
    var closeBtn = document.getElementById("paymentsModalClose");
    var bodyEl = document.getElementById("paymentsModalBody");
    var titleEl = document.getElementById("paymentsModalTitle");
    if (!overlay || !bodyEl) return;

    var receiptModalBlobUrl = null;
    function openReceiptModal(url) {
      var receiptOverlay = document.getElementById("receiptModal");
      var loading = document.getElementById("receiptModalLoading");
      var img = document.getElementById("receiptModalImage");
      var fallback = document.getElementById("receiptModalFallback");
      var openNewLink = document.getElementById("receiptModalOpenNew");
      if (!receiptOverlay || !url) return;
      if (receiptModalBlobUrl) { URL.revokeObjectURL(receiptModalBlobUrl); receiptModalBlobUrl = null; }
      loading.style.display = "block";
      if (img) { img.style.display = "none"; img.removeAttribute("src"); }
      if (fallback) fallback.style.display = "none";
      receiptOverlay.style.display = "flex";
      receiptOverlay.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
      fetch(url, { credentials: "include" })
        .then(function (r) {
          if (!r.ok) throw new Error("خطا در بارگذاری");
          var ct = (r.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
          return r.blob().then(function (blob) { return { blob: blob, contentType: ct }; });
        })
        .then(function (res) {
          if (res.contentType.indexOf("image/") === 0 && img) {
            receiptModalBlobUrl = URL.createObjectURL(res.blob);
            img.src = receiptModalBlobUrl;
            img.style.display = "block";
          } else {
            if (openNewLink) { openNewLink.href = url; openNewLink.textContent = "باز کردن رسید در تب جدید"; }
            if (fallback) fallback.style.display = "block";
          }
          loading.style.display = "none";
        })
        .catch(function () {
          if (openNewLink) { openNewLink.href = url; openNewLink.textContent = "باز کردن رسید در تب جدید"; }
          if (fallback) fallback.style.display = "block";
          loading.style.display = "none";
        });
    }
    function closeReceiptModal() {
      var receiptOverlay = document.getElementById("receiptModal");
      var img = document.getElementById("receiptModalImage");
      var fallback = document.getElementById("receiptModalFallback");
      var loading = document.getElementById("receiptModalLoading");
      if (receiptOverlay) { receiptOverlay.style.display = "none"; receiptOverlay.setAttribute("aria-hidden", "true"); document.body.style.overflow = ""; }
      if (receiptModalBlobUrl) { URL.revokeObjectURL(receiptModalBlobUrl); receiptModalBlobUrl = null; }
      if (img) { img.removeAttribute("src"); img.style.display = "none"; }
      if (fallback) fallback.style.display = "none";
      if (loading) loading.style.display = "block";
    }
    document.getElementById("receiptModalClose") && document.getElementById("receiptModalClose").addEventListener("click", closeReceiptModal);
    if (document.getElementById("receiptModal")) document.getElementById("receiptModal").addEventListener("click", function (ev) { if (ev.target && ev.target.id === "receiptModal") closeReceiptModal(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && document.getElementById("receiptModal") && document.getElementById("receiptModal").getAttribute("aria-hidden") === "false") closeReceiptModal();
    });

    function openPaymentsModal(accountCode, accountName) {
      var items = paymentsByAccount[accountCode] || [];
      titleEl.textContent = "تراکنش\u200Cهای حساب " + (accountName || accountCode);
      if (!items.length) {
        bodyEl.innerHTML = '<div class="empty-accounts-state"><div class="icon">\uD83D\uDCC4</div><p>هیچ تراکنشی برای این حساب ثبت نشده است.</p></div>';
      } else {
        bodyEl.innerHTML = '<div class="ledger-table-wrapper"><table class="ledger-table"><thead><tr><th>تاریخ</th><th>نوع</th><th>مبلغ (ریال)</th><th>روش</th><th>توضیحات</th><th>ثبت‌کننده</th><th>رسید</th></tr></thead><tbody>' +
          items.map(function (p) {
            var receiptBtn = p.receipt_url ? '<button type="button" class="payments-badge receipt-open-btn" data-receipt-url="' + (p.receipt_url || "").replace(/"/g, "&quot;") + '">مشاهده رسید</button>' : "—";
            var creator = (p.created_by_name && p.created_by_name.trim()) ? p.created_by_name : "—";
            return "<tr><td>" + (p.date || "—") + "</td><td>" + (p.direction || "—") + "</td><td class=\"col-credit\">" + formatAmount(p.amount) + "</td><td>" + (p.method || "—") + "</td><td>" + (p.description || "—") + "</td><td>" + creator + "</td><td>" + receiptBtn + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      }
      setModalOpen(overlay, true);
    }
    bodyEl.addEventListener("click", function (e) {
      var btn = e.target && e.target.closest && e.target.closest(".receipt-open-btn");
      if (btn && btn.getAttribute("data-receipt-url")) { e.preventDefault(); openReceiptModal(btn.getAttribute("data-receipt-url")); }
    });
    document.addEventListener("click", function (e) {
      var btn = e.target && e.target.closest && e.target.closest(".payments-badge[data-account-code]");
      if (!btn) return;
      e.preventDefault();
      var code = btn.getAttribute("data-account-code");
      var row = btn.closest("tr");
      var nameCell = row ? row.querySelector(".col-account") : null;
      openPaymentsModal(code, nameCell ? nameCell.textContent.trim() : "");
    });
    if (closeBtn) closeBtn.addEventListener("click", function () { setModalOpen(overlay, false); });
    overlay.addEventListener("click", function (e) { if (e.target && e.target.id === "paymentsModal") setModalOpen(overlay, false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setModalOpen(overlay, false); });
  }

  function initRegisterPaymentModal() {
    var overlay = document.getElementById("registerPaymentModal");
    var openBtn = document.getElementById("openRegisterPaymentModal");
    var closeBtn = document.getElementById("registerPaymentModalClose");
    var form = document.getElementById("registerPaymentForm");
    var messageEl = document.getElementById("registerPaymentMessage");
    var submitBtn = document.getElementById("registerPaymentSubmit");
    var amountInput = document.getElementById("paymentAmount");
    if (!overlay || !form) return;

    function setOpen(open) {
      setModalOpen(overlay, open);
      if (!open && messageEl) { messageEl.textContent = ""; messageEl.className = "form-message"; }
    }
    if (openBtn) openBtn.addEventListener("click", function () { setOpen(true); });
    if (closeBtn) closeBtn.addEventListener("click", function () { setOpen(false); });
    overlay.addEventListener("click", function (e) { if (e.target && e.target.id === "registerPaymentModal") setOpen(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && overlay.getAttribute("aria-hidden") === "false") setOpen(false); });

    if (amountInput) {
      var fa = "\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9";
      function toEnDigits(str) {
        var out = "";
        for (var i = 0; i < (str || "").length; i++) { var idx = fa.indexOf(str[i]); out += idx >= 0 ? idx : str[i]; }
        return out;
      }
      function formatAmountInput() {
        var v = (amountInput.value || "").replace(/,|\u066C|\u060C/g, "");
        var en = toEnDigits(v).replace(/\D/g, "");
        if (!en) { amountInput.value = ""; amountInput.setAttribute("data-raw", ""); return; }
        var n = parseInt(en, 10);
        if (isNaN(n)) { amountInput.setAttribute("data-raw", ""); return; }
        amountInput.setAttribute("data-raw", String(n));
        amountInput.value = n.toLocaleString("fa-IR");
      }
      amountInput.addEventListener("blur", formatAmountInput);
      amountInput.addEventListener("keydown", function (e) {
        if (e.key !== "Backspace" && e.key !== "Tab" && e.key !== "Enter" && !e.ctrlKey && !e.metaKey && !/[0-9\u06F0-\u06F9]/.test(e.key)) e.preventDefault();
      });
      amountInput.addEventListener("input", formatAmountInput);
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!paymentUrl) { messageEl.textContent = "آدرس ثبت تراکنش یافت نشد."; messageEl.className = "form-message error"; return; }
      var fd = new FormData(form);
      var rawAmount = amountInput ? (amountInput.getAttribute("data-raw") || amountInput.value) : fd.get("amount");
      if (typeof rawAmount === "string") rawAmount = rawAmount.replace(/,|\u066C|\u060C/g, "").replace(/[\u06F0-\u06F9]/g, function (c) { return "\u06F0\u06F1\u06F2\u06F3\u06F4\u06F5\u06F6\u06F7\u06F8\u06F9".indexOf(c); }).replace(/\D/g, "");
      if (!rawAmount || parseInt(rawAmount, 10) <= 0) { messageEl.textContent = "مبلغ را به درستی وارد کنید."; messageEl.className = "form-message error"; return; }
      fd.set("amount", rawAmount);
      var csrf = fd.get("csrfmiddlewaretoken") || "";
      messageEl.textContent = "در حال ثبت...";
      messageEl.className = "form-message";
      submitBtn.disabled = true;
      fetch(paymentUrl, { method: "POST", headers: { "X-CSRFToken": csrf, "Accept": "application/json" }, body: fd })
        .then(function (res) { return res.json().then(function (data) {
          if (res.ok && data.success) {
            messageEl.textContent = data.message || "ثبت شد.";
            messageEl.className = "form-message success";
            setTimeout(function () { window.location.reload(); }, 800);
          } else {
            messageEl.textContent = data.message || "خطا در ثبت تراکنش.";
            messageEl.className = "form-message error";
            submitBtn.disabled = false;
          }
        }); })
        .catch(function () { messageEl.textContent = "خطا در ارتباط با سرور."; messageEl.className = "form-message error"; submitBtn.disabled = false; });
    });
  }

  function initPendingApprovalButtons() {
    if (!canApprovePending || !approvePendingUrlTemplate || !rejectPendingUrlTemplate) return;
    document.addEventListener("click", function (e) {
      var approveBtn = e.target && e.target.classList && e.target.classList.contains("btn-approve-pending");
      var rejectBtn = e.target && e.target.classList && e.target.classList.contains("btn-reject-pending");
      var id = (approveBtn ? e.target : (rejectBtn ? e.target : null)) && (e.target.getAttribute("data-pending-id") || "");
      if (!id) return;
      e.preventDefault();
      var approveUrl = approvePendingUrlTemplate.replace("/pending/0/", "/pending/" + id + "/");
      var rejectUrl = rejectPendingUrlTemplate.replace("/pending/0/", "/pending/" + id + "/");
      if (approveBtn) {
        if (!confirm("آیا از تایید این تراکنش و اعمال آن در دفتر مطمئن هستید؟")) return;
        e.target.disabled = true;
        fetch(approveUrl, {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken(), "Content-Type": "application/json" },
          credentials: "include",
        })
          .then(function (r) { return r.json().catch(function () { return {}; }); })
          .then(function (data) {
            if (data.success) { window.location.reload(); } else { alert(data.message || "خطا در تایید"); e.target.disabled = false; }
          })
          .catch(function () { alert("خطا در ارتباط با سرور."); e.target.disabled = false; });
      } else if (rejectBtn) {
        var reason = prompt("علت رد (اختیاری):", "");
        if (reason === null) return;
        e.target.disabled = true;
        fetch(rejectUrl, {
          method: "POST",
          headers: { "X-CSRFToken": getCsrfToken(), "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ rejection_reason: (reason || "").trim() }),
        })
          .then(function (r) { return r.json().catch(function () { return {}; }); })
          .then(function (data) {
            if (data.success) { window.location.reload(); } else { alert(data.message || "خطا در رد"); e.target.disabled = false; }
          })
          .catch(function () { alert("خطا در ارتباط با سرور."); e.target.disabled = false; });
      }
    });
  }

  function init() {
    initDealDetailModal();
    initPaymentsModal();
    initRegisterPaymentModal();
    initPendingApprovalButtons();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
