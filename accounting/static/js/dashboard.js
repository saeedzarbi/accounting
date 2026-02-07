/**
 * Dashboard — لیست معاملات، پagination، مودال جزئیات و عملیات تایید/رد/حذف
 * وابسته به: window.DASHBOARD_CONFIG (از قالب Django)
 */
(function () {
  "use strict";

  const config = window.DASHBOARD_CONFIG || {};
  const dealsApiUrl = config.dealsApiUrl || "";
  const dealDetailUrlTemplate = config.dealDetailUrlTemplate || "";
  const deleteDealUrlTemplate = config.deleteDealUrlTemplate || "";
  const editDealUrlTemplate = config.editDealUrlTemplate || "";
  const approveDealUrlTemplate = config.approveDealUrlTemplate || "";
  const rejectDealUrlTemplate = config.rejectDealUrlTemplate || "";
  const contractPdfUrlTemplate = config.contractPdfUrlTemplate || "";
  const generateContractUrlTemplate = config.generateContractUrlTemplate || "";
  const dealAccountsUrlTemplate = config.dealAccountsUrlTemplate || "";
  const isOfficeManager = Boolean(config.isOfficeManager);

  const PAGE_SIZE = 9;
  const STATUS_MAP = {
    init: "تعریف اولیه",
    pending: "در انتظار تایید مدیر",
    pendding: "در انتظار تایید مدیر",
    approved: "تایید شده",
    rejected: "رد شده",
  };

  let currentPage = 1;
  let totalCount = 0;

  function dealDetailUrl(id) {
    return dealDetailUrlTemplate.replace("0", String(id));
  }

  function approveDealUrl(id) {
    return approveDealUrlTemplate.replace("0", String(id));
  }

  function rejectDealUrl(id) {
    return rejectDealUrlTemplate.replace("0", String(id));
  }

  function deleteDealUrl(id) {
    return deleteDealUrlTemplate.replace("0", String(id));
  }

  function editDealUrl(id) {
    return editDealUrlTemplate + id;
  }

  function contractPdfUrl(contractId) {
    return contractPdfUrlTemplate.replace("0", String(contractId));
  }

  function generateContractUrl(dealId) {
    return generateContractUrlTemplate.replace("0", String(dealId));
  }

  function dealAccountsUrl(dealId) {
    return dealAccountsUrlTemplate.replace("deal/0/", "deal/" + dealId + "/");
  }

  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function asText(v, fallback) {
    fallback = fallback === undefined ? "ثبت نشده" : fallback;
    if (v === null || v === undefined) return fallback;
    if (typeof v === "string" && v.trim() === "") return fallback;
    return String(v);
  }

  function escapeHtml(s) {
    if (s == null) return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function formatMoney(value) {
    if (value === null || value === undefined || value === "") return "ثبت نشده";
    const n = Number(value);
    if (Number.isNaN(n)) return String(value);
    try {
      return n.toLocaleString("fa-IR");
    } catch (e) {
      return String(value);
    }
  }

  function splitRoleLabel(role) {
    if (role == null) return "نقش";
    const r = String(role).toLowerCase();
    if (r === "office") return "دفتر";
    if (r === "manager") return "مدیر";
    if (r === "consultant") return "مشاور";
    return asText(role, "نقش");
  }

  function formatCreatedDate(value) {
    if (!value) return "—";
    try {
      const d = new Date(value);
      if (isNaN(d.getTime())) return value;
      return d.toLocaleDateString("fa-IR", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return value;
    }
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function updateCount() {
    const el = getEl("deals-count");
    if (el) el.textContent = "تعداد کل: " + totalCount;
  }

  function renderEmpty(message) {
    message = message || "هیچ معامله‌ای برای دفتر شما ثبت نشده است.";
    const container = getEl("deals-container");
    const pagination = getEl("deals-pagination");
    if (container) container.innerHTML = '<div class="empty-state">' + escapeHtml(message) + "</div>";
    if (pagination) pagination.innerHTML = "";
  }

  function renderLoading() {
    const container = getEl("deals-container");
    if (container) container.innerHTML = '<div class="loading">در حال دریافت اطلاعات...</div>';
  }

  function closeDropdowns(container) {
    if (!container) return;
    container.querySelectorAll(".deal-card-dropdown").forEach(function (d) {
      d.classList.remove("is-open");
    });
  }

  function renderCards(items) {
    const container = getEl("deals-container");
    if (!container) return;

    if (!items.length) {
      renderEmpty();
      return;
    }

    const html = items
      .map(function (item) {
        const statusCls = item.status ? " " + item.status : "";
        const canEdit = item.status !== "approved";
        const hasMabia = item.latest_contract_id != null;
        const mabiaBadge = hasMabia
          ? '<span class="deal-mabia-badge has" title="مبایعه‌نامه دارد">✓</span>'
          : "";
        const mabiaMenuItem = hasMabia
          ? '<a href="' +
            contractPdfUrl(item.latest_contract_id) +
            '" target="_blank" rel="noopener" onclick="event.stopPropagation();">مشاهده مبایعه‌نامه</a>'
          : '<a href="' + generateContractUrl(item.id) + '" onclick="event.stopPropagation();">ثبت مبایعه‌نامه</a>';
        const editMenuItem = canEdit
          ? '<a href="' + editDealUrl(item.id) + '" onclick="event.stopPropagation();">ویرایش معامله</a>'
          : '<a href="#" class="disabled" onclick="event.preventDefault(); event.stopPropagation();">ویرایش (غیرفعال برای تایید شده)</a>';
        const createdStr = formatCreatedDate(item.created_at);
        const creatorStr = item.creator ? escapeHtml(item.creator) : "—";
        const typeName = (item.type && item.type.name) || "نامشخص";
        const statusText = STATUS_MAP[item.status] || item.status || "نامشخص";

        return (
          '<div class="deal-card' +
          statusCls +
          '" role="button" tabindex="0" data-id="' +
          item.id +
          '">' +
          '<div class="deal-card-header">' +
          '<div class="deal-card-menu" onclick="event.stopPropagation()">' +
          '<button type="button" class="deal-card-menu-btn" aria-label="منو" title="منو" data-deal-id="' +
          item.id +
          '">' +
          '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="6" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="12" cy="18" r="1.5" /></svg>' +
          "</button>" +
          '<div class="deal-card-dropdown" data-deal-menu="' +
          item.id +
          '">' +
          '<a href="' +
          dealAccountsUrl(item.id) +
          '" onclick="event.stopPropagation()">حساب‌ها</a>' +
          mabiaMenuItem +
          editMenuItem +
          "</div>" +
          "</div>" +
          '<div class="deal-title">' +
          escapeHtml(item.title || "بدون عنوان") +
          "</div>" +
          "</div>" +
          '<div class="deal-card-meta">' +
          "<span>تاریخ ساخت: " +
          createdStr +
          "</span>" +
          "<span>توسط: " +
          creatorStr +
          "</span>" +
          "</div>" +
          '<div class="deal-card-footer">' +
          '<div class="deal-footer-badges">' +
          '<span class="deal-type">' +
          escapeHtml(typeName) +
          "</span>" +
          '<span class="deal-status ' +
          (item.status || "") +
          '">' +
          escapeHtml(statusText) +
          "</span>" +
          "</div>" +
          mabiaBadge +
          "</div>" +
          "</div>"
        );
      })
      .join("");

    container.innerHTML = html;

    container.querySelectorAll(".deal-card").forEach(function (card) {
      const id = Number(card.getAttribute("data-id"));
      card.addEventListener("click", function () {
        openDealModal(id);
      });
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openDealModal(id);
        }
      });
    });

    container.querySelectorAll(".deal-card-menu-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        const menu = this.closest(".deal-card-menu");
        const dropdown = menu ? menu.querySelector(".deal-card-dropdown") : null;
        closeDropdowns(container);
        if (dropdown) dropdown.classList.toggle("is-open");
      });
    });
  }

  function bindDropdownClose() {
    document.addEventListener("click", function () {
      const container = getEl("deals-container");
      closeDropdowns(container);
    });
  }

  function renderPagination(totalPages) {
    const pagination = getEl("deals-pagination");
    if (!pagination) return;
    if (totalPages <= 1) {
      pagination.innerHTML = "";
      return;
    }

    const pages = [];
    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, currentPage + 2);
    for (let i = start; i <= end; i += 1) pages.push(i);

    const pagesHtml = pages
      .map(function (page) {
        const active = page === currentPage ? " active" : "";
        return '<button class="page-btn' + active + '" data-page="' + page + '">' + page + "</button>";
      })
      .join("");

    pagination.innerHTML =
      '<div class="pagination-info">صفحه ' +
      currentPage +
      " از " +
      totalPages +
      "</div>" +
      '<div class="pagination-controls">' +
      '<button class="page-btn" ' +
      (currentPage === 1 ? "disabled" : "") +
      ' data-page="' +
      (currentPage - 1) +
      '">قبلی</button>' +
      pagesHtml +
      '<button class="page-btn" ' +
      (currentPage === totalPages ? "disabled" : "") +
      ' data-page="' +
      (currentPage + 1) +
      '">بعدی</button>' +
      "</div>";

    pagination.querySelectorAll(".page-btn").forEach(function (btn) {
      if (btn.disabled) return;
      btn.addEventListener("click", function () {
        const page = Number(btn.getAttribute("data-page"));
        if (!Number.isNaN(page)) loadDeals(page);
      });
    });
  }

  function loadDeals(page) {
    page = page === undefined ? 1 : page;
    currentPage = page;
    renderLoading();
    const url = dealsApiUrl + "?page=" + page + "&size=" + PAGE_SIZE;
    fetch(url, { credentials: "include" })
      .then(function (response) {
        if (!response.ok) throw new Error("Failed to fetch deals");
        return response.json();
      })
      .then(function (data) {
        totalCount = data.count || 0;
        updateCount();
        renderCards(data.results || []);
        var totalPages = Math.ceil(totalCount / PAGE_SIZE) || 1;
        renderPagination(totalPages);
      })
      .catch(function () {
        renderEmpty("خطا در دریافت اطلاعات معاملات. لطفاً دوباره تلاش کنید.");
        var countEl = getEl("deals-count");
        if (countEl) countEl.textContent = "خطا در دریافت اطلاعات";
      });
  }

  function setModalOpen(open) {
    const overlay = getEl("dealModalOverlay");
    if (!overlay) return;
    overlay.style.display = open ? "flex" : "none";
    overlay.setAttribute("aria-hidden", open ? "false" : "true");
    document.body.style.overflow = open ? "hidden" : "";
  }

  function closeDealModal() {
    setModalOpen(false);
  }

  function openDealModal(id) {
    const body = getEl("dealModalBody");
    const titleEl = getEl("dealModalTitle");
    if (!body) return;

    setModalOpen(true);
    if (titleEl) titleEl.textContent = "جزئیات معامله #" + id;
    body.innerHTML = '<div class="loading">در حال دریافت جزئیات...</div>';

    fetch(dealDetailUrl(id), { credentials: "include" })
      .then(function (response) {
        if (!response.ok) throw new Error("Failed to fetch deal detail");
        return response.json();
      })
      .then(function (detail) {
        renderDealDetail(detail);
      })
      .catch(function () {
        body.innerHTML =
          '<div class="empty-state">خطا در دریافت جزئیات. لطفاً دوباره تلاش کنید.</div>';
      });
  }

  function renderDealDetail(detail) {
    const title = (detail && detail.title) ? detail.title : "جزئیات معامله";
    const titleEl = getEl("dealModalTitle");
    const bodyEl = getEl("dealModalBody");
    if (titleEl) titleEl.textContent = "جزئیات معامله";
    if (!bodyEl) return;

    const buyers = Array.isArray(detail.buyers)
      ? detail.buyers
          .map(function (b) {
            return b.national_id ? b.name + " — کد ملی: " + b.national_id : b.name;
          })
          .filter(Boolean)
      : [];
    const sellers = Array.isArray(detail.sellers)
      ? detail.sellers
          .map(function (s) {
            return s.national_id ? s.name + " — کد ملی: " + s.national_id : s.name;
          })
          .filter(Boolean)
      : [];
    const consultants = Array.isArray(detail.consultants)
      ? detail.consultants
          .map(function (c) {
            return c && c.name != null ? c.name : String(c);
          })
          .filter(Boolean)
      : [];
    const splits = Array.isArray(detail.splits) ? detail.splits : [];
    const contracts = Array.isArray(detail.contracts) ? detail.contracts : [];

    const splitsHtml =
      splits.length > 0
        ? '<div class="taglist">' +
          splits
            .map(function (s) {
              return '<span class="tag">' + splitRoleLabel(s.role) + " · " + formatMoney(s.amount) + "</span>";
            })
            .join("") +
          "</div>"
        : '<div class="text-muted text-xs">ثبت نشده</div>';

    const contractsHtml =
      contracts.length > 0
        ? '<div class="taglist">' +
          contracts
            .map(function (c) {
              return (
                '<span class="tag">' +
                asText(c.template_title, "قالب") +
                " · " +
                (c.is_finalized ? "نهایی" : "پیش‌نویس") +
                "</span>"
              );
            })
            .join("") +
          "</div>"
        : '<div class="text-muted text-xs">ثبت نشده</div>';

    const statusCode = detail.status_code || detail.status || "";
    const statusText = detail.status || "";

    let rejectWrapHtml = "";
    if (detail.status_code === "pending" && isOfficeManager) {
      rejectWrapHtml =
        '<div class="reject-reason-wrap" id="rejectReasonWrap" style="display:none; margin-top:12px; padding:12px; background: color-mix(in srgb, var(--color-surface-alt) 80%, transparent); border-radius:12px; border:1px solid rgba(248,113,113,0.4);">' +
        '<label class="reject-reason-label">علت رد معامله</label>' +
        '<textarea id="rejectReasonInput" class="reject-reason-textarea" rows="3" placeholder="دلیل رد را وارد کنید..."></textarea>' +
        '<div class="reject-reason-actions">' +
        '<button type="button" class="detail-btn-reject-submit" id="rejectSubmitBtn">ثبت رد</button>' +
        '<button type="button" class="detail-btn-reject-cancel" id="rejectCancelBtn">انصراف</button>' +
        "</div>" +
        "</div>";
    }

    let actionsHtml =
      (contracts.length
        ? '<a href="' +
          contractPdfUrl(contracts[contracts.length - 1].id) +
          '" target="_blank" rel="noopener" class="detail-btn-pdf">دریافت PDF</a>'
        : "") +
      (detail.status_code === "pending" && isOfficeManager
        ? '<a href="#" class="detail-btn-approve" id="dealApproveBtn">تایید معامله</a><a href="#" class="detail-btn-reject" id="dealRejectBtn">رد معامله</a>'
        : "") +
      (detail.status_code !== "approved" && detail.status_code !== "rejected"
        ? '<a href="' + editDealUrl(detail.id) + '" class="detail-btn-edit">ویرایش مبایعه</a>'
        : detail.status_code === "approved"
          ? '<a href="#" class="detail-btn-edit disabled">ویرایش (غیرفعال برای معاملات تایید شده)</a>'
          : "") +
      (detail.status_code === "init"
        ? '<a href="#" class="detail-btn-delete" id="dealDeleteBtn">حذف معامله</a>'
        : "");

    const rejectionRow =
      detail.status_code === "rejected" && detail.rejection_reason
        ? '<b>علت رد</b><span>' + escapeHtml(detail.rejection_reason) + "</span>"
        : "";
    const descriptionBlock = detail.description
      ? '<div class="detail-card" style="margin-top:10px;"><h3>توضیحات</h3><div class="kv"><b>شرح</b><span>' +
        asText(detail.description) +
        "</span></div></div>"
      : "";

    bodyEl.innerHTML =
      '<div class="deal-detail-summary">' +
      '<div class="detail-summary-main">' +
      '<div class="detail-summary-title">' +
      escapeHtml(title || "بدون عنوان") +
      "</div>" +
      '<div class="detail-summary-meta">' +
      (statusText ? '<span class="detail-badge status-' + statusCode + '">' + escapeHtml(statusText) + "</span>" : "") +
      (detail.type && detail.type.name
        ? '<span class="detail-badge type">' + escapeHtml(detail.type.name) + "</span>"
        : "") +
      '<span class="detail-badge id">کد: ' +
      asText(detail.id) +
      "</span>" +
      "</div>" +
      "</div>" +
      '<div class="detail-summary-extra">' +
      "<span>تاریخ ثبت: " +
      formatCreatedDate(detail.created_at) +
      "</span>" +
      (detail.office_date ? "<span>تاریخ دفترخانه: " + asText(detail.office_date) + "</span>" : "") +
      (detail.amount != null ? "<span>مبلغ معامله: " + formatMoney(detail.amount) + "</span>" : "") +
      "</div>" +
      "</div>" +
      '<div class="detail-grid">' +
      '<div class="detail-card"><h3>اطلاعات پایه</h3><div class="kv">' +
      "<b>کد معامله</b><span>" +
      asText(detail.id) +
      "</span>" +
      "<b>وضعیت</b><span>" +
      asText(detail.status) +
      "</span>" +
      "<b>نوع</b><span>" +
      asText(detail.type && detail.type.name) +
      "</span>" +
      "<b>سازنده</b><span>" +
      asText(detail.creator) +
      "</span>" +
      "<b>تاریخ ثبت</b><span>" +
      formatCreatedDate(detail.created_at) +
      "</span>" +
      rejectionRow +
      "</div></div>" +
      '<div class="detail-card"><h3>تاریخ‌ها</h3><div class="kv">' +
      "<b>تاریخ مبایعه</b><span>" +
      asText(detail.agreement_date) +
      "</span>" +
      "<b>تاریخ دفترخانه</b><span>" +
      asText(detail.office_date) +
      "</span>" +
      "<b>تاریخ</b><span>" +
      asText(detail.date) +
      "</span></div></div>" +
      '<div class="detail-card"><h3>مبالغ</h3><div class="kv">' +
      "<b>مبلغ معامله</b><span>" +
      formatMoney(detail.amount) +
      "</span>" +
      "<b>قیمت پایه</b><span>" +
      formatMoney(detail.base_price) +
      "</span>" +
      "<b>خیر</b><span>" +
      formatMoney(detail.overpayment) +
      "</span></div></div>" +
      '<div class="detail-card"><h3>طرفین</h3><div class="kv">' +
      "<b>خریداران</b><span>" +
      (buyers.length ? buyers.join("، ") : "ثبت نشده") +
      "</span>" +
      "<b>فروشندگان</b><span>" +
      (sellers.length ? sellers.join("، ") : "ثبت نشده") +
      "</span>" +
      "<b>مشاوران</b><span>" +
      (consultants.length ? consultants.join("، ") : "ثبت نشده") +
      "</span></div></div>" +
      '<div class="detail-card"><h3>کمیسیون‌ها</h3>' +
      splitsHtml +
      "</div>" +
      '<div class="detail-card"><h3>قراردادها</h3>' +
      contractsHtml +
      "</div>" +
      "</div>" +
      descriptionBlock +
      rejectWrapHtml +
      '<div class="detail-actions-bar">' +
      actionsHtml +
      "</div>";

    const deleteBtn = getEl("dealDeleteBtn");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", function (event) {
        event.preventDefault();
        if (!confirm("آیا از حذف این معامله مطمئن هستید؟")) return;
        fetch(deleteDealUrl(detail.id), {
          method: "DELETE",
          headers: { "X-CSRFToken": getCsrfToken() },
          credentials: "include",
        })
          .then(function (response) {
            if (!response.ok) throw new Error("حذف معامله انجام نشد.");
            closeDealModal();
            loadDeals(currentPage);
          })
          .catch(function (err) {
            alert(err.message || "خطا در حذف معامله");
          });
      });
    }

    const approveBtn = getEl("dealApproveBtn");
    if (approveBtn) {
      approveBtn.addEventListener("click", function (event) {
        event.preventDefault();
        if (!confirm("آیا از تایید این معامله مطمئن هستید؟")) return;
        fetch(approveDealUrl(detail.id), {
          method: "PATCH",
          headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/json",
          },
          credentials: "include",
        })
          .then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
              if (!response.ok) throw new Error(data.message || "تایید معامله انجام نشد.");
              closeDealModal();
              loadDeals(currentPage);
            });
          })
          .catch(function (err) {
            alert(err.message || "خطا در تایید معامله");
          });
      });
    }

    const rejectBtn = getEl("dealRejectBtn");
    const rejectWrap = getEl("rejectReasonWrap");
    const rejectInput = getEl("rejectReasonInput");
    const rejectSubmitBtn = getEl("rejectSubmitBtn");
    const rejectCancelBtn = getEl("rejectCancelBtn");
    if (rejectBtn && rejectWrap) {
      rejectBtn.addEventListener("click", function (event) {
        event.preventDefault();
        rejectWrap.style.display = "block";
        if (rejectInput) rejectInput.value = "";
        if (rejectInput) rejectInput.focus();
      });
    }
    if (rejectCancelBtn && rejectWrap) {
      rejectCancelBtn.addEventListener("click", function () {
        rejectWrap.style.display = "none";
      });
    }
    if (rejectSubmitBtn && rejectWrap && rejectInput) {
      rejectSubmitBtn.addEventListener("click", function () {
        const reason = rejectInput.value.trim();
        fetch(rejectDealUrl(detail.id), {
          method: "POST",
          headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({ rejection_reason: reason }),
        })
          .then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
              if (!response.ok) throw new Error(data.message || "رد معامله انجام نشد.");
              closeDealModal();
              loadDeals(currentPage);
            });
          })
          .catch(function (err) {
            alert(err.message || "خطا در رد معامله");
          });
      });
    }
  }

  function bindModalEvents() {
    const closeBtn = getEl("dealModalClose");
    const overlay = getEl("dealModalOverlay");
    if (closeBtn) closeBtn.addEventListener("click", closeDealModal);
    if (overlay) {
      overlay.addEventListener("click", function (e) {
        if (e.target && e.target.id === "dealModalOverlay") closeDealModal();
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDealModal();
    });
  }

  function init() {
    bindDropdownClose();
    bindModalEvents();
    loadDeals();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
