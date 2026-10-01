(function () {
  const $ = (sel, root = document) => root.querySelector(sel);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function api(url, options = {}) {
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }
    return { ok: res.ok, status: res.status, data };
  }

  function setText(selector, value) {
    document.querySelectorAll(selector).forEach((n) => { n.textContent = value; });
  }

  // ---- live counts, refreshed every 10 seconds ----
  async function refreshStats() {
    try {
      const { ok, data } = await api('/api/stats');
      if (!ok) return;
      setText('[data-stat="available"]', data.available);
      setText('[data-stat="busy"]', data.busy);
      setText('[data-stat="total"]', data.total);
      Object.entries(data.stands).forEach(([key, v]) => {
        setText('[data-stand-available="' + key + '"]', v.available);
        setText('[data-stand-busy="' + key + '"]', v.busy);
      });
    } catch (e) { /* offline: keep the last numbers */ }
  }
  refreshStats();
  setInterval(refreshStats, 10000);

  function telHref(phone) {
    return 'tel:' + phone.replace(/[^\d+]/g, '');
  }

  // ---- booking ----
  const bookForm = $('#book');
  const bookOut = $('#book-result');

  if (bookForm) {
    bookForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = bookForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Finding your auto...';
      const { ok, status, data } = await api('/api/book', {
        method: 'POST',
        body: JSON.stringify(Object.fromEntries(new FormData(bookForm))),
      });
      btn.disabled = false;
      btn.textContent = 'Find my auto';
      bookOut.replaceChildren();

      if (ok) {
        const box = el('div', 'result ok');
        box.append(
          el('h3', '', 'Auto assigned'),
          el('p', '', 'Meet ' + data.driver.driver_name + ' at ' + data.pickup + '. He will take you to ' + data.destination + '.')
        );
        const row = el('div', 'row');
        row.append(el('span', 'plate', data.driver.auto_number));
        const call = el('a', 'call', 'Call ' + data.driver.phone_number);
        call.href = telHref(data.driver.phone_number);
        row.append(call);
        box.append(row);
        bookOut.append(box);
        bookForm.reset();
        refreshStats();
      } else if (status === 409) {
        const box = el('div', 'result warn');
        box.append(el('h3', '', data.error));
        if (data.alternatives && data.alternatives.length) {
          box.append(el('p', '', 'Autos are free at another stand:'));
          const row = el('div', 'row');
          data.alternatives.forEach((alt) => {
            const chip = el('button', 'chip', alt.name + ' (' + alt.available + ')');
            chip.type = 'button';
            chip.addEventListener('click', () => {
              bookForm.pickup.value = alt.name;
              bookOut.replaceChildren();
            });
            row.append(chip);
          });
          box.append(row);
        } else {
          box.append(el('p', '', 'Every auto is on a trip. Please try again in a few minutes.'));
        }
        bookOut.append(box);
      } else {
        bookOut.append(el('div', 'result bad', data.error || 'Something went wrong. Please try again.'));
      }
    });
  }

  // "Book from here" buttons on the stand cards
  document.querySelectorAll('[data-pickup]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!bookForm) return;
      bookForm.pickup.value = btn.dataset.pickup;
      bookForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => bookForm.customer_name.focus({ preventScroll: true }), 400);
    });
  });

  // ---- driver registration ----
  const joinForm = $('#join-form');
  const joinOut = $('#join-result');

  if (joinForm) {
    joinForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = joinForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      const { ok, data } = await api('/api/drivers', {
        method: 'POST',
        body: JSON.stringify(Object.fromEntries(new FormData(joinForm))),
      });
      btn.disabled = false;
      joinOut.replaceChildren();

      if (ok) {
        const box = el('div', 'result ok');
        box.append(el('h3', '', 'You are registered'));
        const row = el('div', 'row');
        row.append(el('span', 'plate', data.auto_number), el('span', '', 'now listed at ' + data.stand_location));
        box.append(row);
        joinOut.append(box);
        joinForm.reset();
        refreshStats();
      } else {
        joinOut.append(el('div', 'result bad', data.error || 'Something went wrong. Please try again.'));
      }
    });
  }

  // ---- fleet desk actions ----
  document.querySelectorAll('.js-toggle').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      await api('/api/drivers/' + btn.dataset.id + '/status', { method: 'POST' });
      location.reload();
    });
  });

  document.querySelectorAll('.js-remove').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm('Remove ' + btn.dataset.name + ' from the fleet?')) return;
      await api('/api/drivers/' + btn.dataset.id, { method: 'DELETE' });
      location.reload();
    });
  });
})();