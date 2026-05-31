/**
 * Универсальное копирование записей справочников между шаблонами и организациями.
 */
(function (global) {
  function escapeHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const r = await fetch('/api' + path, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = data.detail;
      const msg = typeof detail === 'object' ? (detail.message || detail.code || JSON.stringify(detail)) : (detail || r.statusText);
      throw new Error(msg || 'Ошибка запроса');
    }
    return data;
  }

  async function loadTemplates() {
    const data = await api('GET', '/enterprise-templates');
    return (Array.isArray(data) ? data : (data.items || [])).filter((t) => t.is_active !== false);
  }

  function resolveLocalToGlobalTargetTpl(cfg, templates, sourceTpl) {
    const preferred = cfg.targetTemplateCode || cfg.clientTemplateCode;
    if (preferred && templates.some((t) => t.code === preferred)) return preferred;
    if (sourceTpl && templates.some((t) => t.code === sourceTpl)) return sourceTpl;
    return templates[0]?.code || preferred || 'default';
  }

  let modalEl = null;

  function ensureModal() {
    if (modalEl) return modalEl;
    modalEl = document.createElement('div');
    modalEl.id = 'catalogCopyModal';
    modalEl.className = 'modal';
    modalEl.innerHTML =
      '<div class="modal-content" style="max-width:520px;">' +
        '<h3 id="catalogCopyTitle">Копировать запись</h3>' +
        '<p class="meta" id="catalogCopyHint" style="margin-top:0;"></p>' +
        '<div class="err hidden" id="catalogCopyErr" style="color:var(--error);margin:0.5rem 0;"></div>' +
        '<div id="catalogCopyFields"></div>' +
        '<div class="modal-actions">' +
          '<button type="button" class="btn btn-primary" id="catalogCopyDo">Копировать</button>' +
          '<button type="button" class="btn btn-secondary" id="catalogCopyCancel">Отмена</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(modalEl);
    modalEl.querySelector('#catalogCopyCancel').onclick = () => modalEl.classList.remove('show');
    return modalEl;
  }

  function showErr(el, msg) {
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      el.classList.remove('hidden');
    } else {
      el.textContent = '';
      el.classList.add('hidden');
    }
  }

  /**
   * @param {object} cfg
   * @param {'regulation'|'position'|'kpi'|'skills'|'skill'|'orgUnit'|'templateOrgUnit'} cfg.entity
   * @param {'global_to_global'|'global_to_local'|'local_to_global'} cfg.mode
   * @param {string} [cfg.sourceTemplateCode]
   * @param {string} [cfg.sourceCode] - regulation_code / position_code / kpi_code
   * @param {string} [cfg.sourceClientRegulationId]
   * @param {string} [cfg.clientId]
   * @param {string} [cfg.orgUnitId]
   * @param {function} [cfg.onSuccess]
   */
  async function open(cfg) {
    const modal = ensureModal();
    const title = modal.querySelector('#catalogCopyTitle');
    const hint = modal.querySelector('#catalogCopyHint');
    const fields = modal.querySelector('#catalogCopyFields');
    const errEl = modal.querySelector('#catalogCopyErr');
    showErr(errEl, '');

    const entity = cfg.entity;
    const mode = cfg.mode;
    const sourceTpl = cfg.sourceTemplateCode || (global.GlobalTemplateContext && global.GlobalTemplateContext.getGlobalEditTemplateCode()) || 'default';

    title.textContent = entity === 'skills'
      ? 'Скопировать типовые навыки в организацию'
      : entity === 'templateOrgUnit'
        ? 'Копировать узел в другой шаблон'
      : entity === 'orgUnit'
        ? 'Копировать подразделение в глобальный шаблон'
      : entity === 'skill'
        ? (mode === 'local_to_global'
          ? 'Копировать навык в глобальный шаблон'
          : 'Копировать навык в другой шаблон')
        : entity === 'kpi' && mode === 'local_to_global'
          ? 'Копировать KPI в глобальный шаблон'
        : entity === 'position' && mode === 'local_to_global'
          ? 'Копировать должность в глобальный шаблон'
        : 'Копировать ' + ({ regulation: 'регламент', position: 'должность', kpi: 'KPI' }[entity] || 'запись');

    hint.textContent = mode === 'local_to_global'
      ? 'Запись будет добавлена в глобальный справочник шаблона, из которого создана организация (можно выбрать другой целевой шаблон).'
      : entity === 'skill'
      ? 'Строка матрицы будет добавлена в целевой шаблон (дубликаты по должности/отделению/рангу пропускаются).'
      : mode === 'global_to_global'
      ? 'Копия будет создана в другом шаблоне типовой инфраструктуры.'
      : mode === 'global_to_local'
        ? 'Копия будет создана в справочнике выбранной организации.'
        : 'Локальная карточка будет перенесена в глобальный шаблон.';

    fields.innerHTML = '';
    const templates = await loadTemplates();
    const templateOptions = templates
      .map((t) => '<option value="' + escapeHtml(t.code) + '">' + escapeHtml(t.code + ' — ' + t.name) + '</option>')
      .join('');
    let targetTplHtml = '';
    if (mode === 'global_to_global' || mode === 'local_to_global') {
      targetTplHtml =
        '<label>Целевой шаблон</label>' +
        '<select id="catalogCopyTargetTpl" style="width:100%;max-width:none;">' +
        templateOptions +
        '</select>';
    }
    fields.innerHTML =
      (mode !== 'local_to_global'
        ? '<label>Исходный шаблон</label><select id="catalogCopySourceTpl" style="width:100%;max-width:none;">' +
          templateOptions +
          '</select>'
        : '') +
      targetTplHtml +
      (entity === 'orgUnit' && mode === 'local_to_global'
        ? '<p class="meta" style="margin:0.5rem 0 0 0;line-height:1.45;">' +
          '<strong>Код узла:</strong> <code>' + escapeHtml(cfg.orgUnitCode || '') + '</code> · ' +
          '<strong>тип:</strong> ' + escapeHtml(cfg.orgUnitType || '') +
          '</p>'
        : '') +
      (entity === 'templateOrgUnit'
        ? '<p class="meta" style="margin:0.5rem 0 0 0;line-height:1.45;">' +
          '<strong>Узел:</strong> <code>' + escapeHtml(cfg.orgUnitCode || '') + '</code>' +
          (cfg.orgUnitName ? ' — ' + escapeHtml(cfg.orgUnitName) : '') +
          (cfg.orgUnitType ? ' · <strong>тип:</strong> ' + escapeHtml(cfg.orgUnitType) : '') +
          '</p>'
        : '') +
      (entity === 'position' && mode === 'local_to_global'
        ? '<p class="meta" style="margin:0.5rem 0 0 0;line-height:1.45;">' +
          '<strong>Должность:</strong> <code>' + escapeHtml(cfg.sourceCode || '') + '</code>' +
          (cfg.sourceName ? ' — ' + escapeHtml(cfg.sourceName) : '') +
          '</p>'
        : '') +
      (entity === 'kpi' && mode === 'local_to_global'
        ? '<p class="meta" style="margin:0.5rem 0 0 0;line-height:1.45;">' +
          '<strong>KPI:</strong> <code>' + escapeHtml(cfg.sourceCode || '') + '</code>' +
          '</p>'
        : '') +
      (entity !== 'skills' && entity !== 'skill' && entity !== 'orgUnit' && mode !== 'local_to_global'
        ? '<label>Код записи</label><input type="text" id="catalogCopySourceCode" style="width:100%;max-width:none;" value="' + escapeHtml(cfg.sourceCode || '') + '">'
        : '') +
      (entity === 'skill' && mode !== 'local_to_global'
        ? '<label>Код должности</label><input type="text" id="catalogCopySkillPosition" style="width:100%;max-width:none;" value="' + escapeHtml(cfg.positionCode || '') + '">' +
          '<label>Тип подразделения</label><input type="text" id="catalogCopySkillDept" style="width:100%;max-width:none;" value="' + escapeHtml(cfg.departmentCode || '') + '">' +
          '<label>Ранг навыка</label><input type="number" id="catalogCopySkillRank" min="1" max="99" style="width:100%;max-width:none;" value="' + escapeHtml(String(cfg.skillRank ?? 1)) + '">'
        : entity === 'skill' && mode === 'local_to_global'
          ? '<p class="meta" style="margin:0.5rem 0 0 0;line-height:1.45;">' +
            '<strong>Должность:</strong> <code>' + escapeHtml(cfg.positionCode || '') + '</code> · ' +
            '<strong>подразделение:</strong> <code>' + escapeHtml(cfg.departmentCode || '') + '</code> · ' +
            '<strong>ранг:</strong> ' + escapeHtml(String(cfg.skillRank ?? 1)) +
            '</p>'
        : '') +
      (mode === 'global_to_local' && entity === 'position'
        ? '<label>Подразделение организации</label><select id="catalogCopyOrgUnit" style="width:100%;max-width:none;"></select>'
        : '') +
      (entity !== 'skills' && entity !== 'skill'
        ? '<label>Код копии (необязательно)</label><input type="text" id="catalogCopyTargetCode" placeholder="По умолчанию — как у источника" style="width:100%;max-width:none;">'
        : '');

    const sourceSel = fields.querySelector('#catalogCopySourceTpl');
    if (sourceSel) {
      sourceSel.value = templates.some((t) => t.code === sourceTpl) ? sourceTpl : (templates[0]?.code || sourceTpl);
    }

    function pickOtherTemplate(code) {
      const other = templates.find((t) => t.code !== code);
      return other ? other.code : code;
    }

    if (mode === 'global_to_global' || mode === 'local_to_global') {
      const sel = fields.querySelector('#catalogCopyTargetTpl');
      const effectiveSource = sourceSel ? sourceSel.value : sourceTpl;
      if (sel) {
        sel.value = mode === 'local_to_global'
          ? resolveLocalToGlobalTargetTpl(cfg, templates, effectiveSource)
          : pickOtherTemplate(effectiveSource);
      }
      if (sourceSel && sel && mode === 'global_to_global') {
        sourceSel.onchange = () => {
          if (sel.value === sourceSel.value) sel.value = pickOtherTemplate(sourceSel.value);
        };
      }
    }

    if (fields.querySelector('#catalogCopyOrgUnit') && cfg.clientId) {
      const ouData = await api('GET', '/org-units?client_id=' + encodeURIComponent(cfg.clientId) + '&limit=500');
      const sel = fields.querySelector('#catalogCopyOrgUnit');
      sel.innerHTML = (ouData.items || []).map((u) =>
        '<option value="' + escapeHtml(u.id) + '">' + escapeHtml(u.code + ' — ' + u.name) + '</option>'
      ).join('');
      if (cfg.orgUnitId) sel.value = cfg.orgUnitId;
    }

    modal.classList.add('show');
    modal.querySelector('#catalogCopyDo').onclick = async () => {
      showErr(errEl, '');
      const effectiveSourceTpl = fields.querySelector('#catalogCopySourceTpl')?.value || sourceTpl;
      try {
        let response = null;
        if (entity === 'skills') {
          response = await api('POST', '/catalog-copy/skills-matrix', {
            client_id: cfg.clientId,
            source_template_code: effectiveSourceTpl,
          });
        } else if (entity === 'regulation') {
          const payload = { mode, source_template_code: effectiveSourceTpl };
          const targetTpl = fields.querySelector('#catalogCopyTargetTpl');
          if (targetTpl) payload.target_template_code = targetTpl.value;
          if (mode === 'local_to_global') {
            payload.source_client_regulation_id = cfg.sourceClientRegulationId;
          } else {
            payload.source_regulation_code = (fields.querySelector('#catalogCopySourceCode')?.value || cfg.sourceCode || '').trim();
          }
          if (mode === 'global_to_local') payload.client_id = cfg.clientId;
          const targetCode = fields.querySelector('#catalogCopyTargetCode')?.value.trim();
          if (targetCode) payload.target_regulation_code = targetCode;
          response = await api('POST', '/catalog-copy/regulation', payload);
        } else if (entity === 'templateOrgUnit') {
          const targetTpl = fields.querySelector('#catalogCopyTargetTpl');
          response = await api('POST', '/catalog-copy/org-unit', {
            mode: 'global_to_global',
            source_template_code: effectiveSourceTpl,
            target_template_code: targetTpl?.value,
            source_org_unit_id: cfg.sourceOrgUnitId,
            target_code: fields.querySelector('#catalogCopyTargetCode')?.value.trim() || null,
          });
        } else if (entity === 'orgUnit') {
          const targetTpl = fields.querySelector('#catalogCopyTargetTpl');
          response = await api('POST', '/catalog-copy/org-unit', {
            client_id: cfg.clientId,
            source_org_unit_id: cfg.sourceOrgUnitId,
            target_template_code: targetTpl?.value,
            target_code: fields.querySelector('#catalogCopyTargetCode')?.value.trim() || null,
          });
        } else if (entity === 'position') {
          const payload = { mode, source_template_code: effectiveSourceTpl };
          const targetTpl = fields.querySelector('#catalogCopyTargetTpl');
          if (targetTpl) payload.target_template_code = targetTpl.value;
          if (mode === 'local_to_global') {
            payload.client_id = cfg.clientId;
            payload.source_position_id = cfg.sourcePositionId;
          } else {
            payload.source_position_code = (fields.querySelector('#catalogCopySourceCode')?.value || cfg.sourceCode || '').trim();
          }
          if (mode === 'global_to_local') {
            payload.client_id = cfg.clientId;
            payload.org_unit_id = fields.querySelector('#catalogCopyOrgUnit')?.value;
          }
          const targetCode = fields.querySelector('#catalogCopyTargetCode')?.value.trim();
          if (targetCode) payload.target_position_code = targetCode;
          response = await api('POST', '/catalog-copy/position', payload);
        } else if (entity === 'skill') {
          const targetTpl = fields.querySelector('#catalogCopyTargetTpl');
          const payload = {
            mode: mode === 'local_to_global' ? 'local_to_global' : 'global_to_global',
            target_template_code: targetTpl?.value || cfg.targetTemplateCode,
            position_code: (fields.querySelector('#catalogCopySkillPosition')?.value || cfg.positionCode || '').trim(),
            department_code: (fields.querySelector('#catalogCopySkillDept')?.value || cfg.departmentCode || '').trim(),
            skill_rank: parseInt(fields.querySelector('#catalogCopySkillRank')?.value || cfg.skillRank || '1', 10) || 1,
          };
          if (mode === 'local_to_global') {
            payload.client_id = cfg.clientId;
            payload.source_matrix_row_id = cfg.sourceMatrixRowId;
          } else {
            payload.source_template_code = effectiveSourceTpl;
          }
          response = await api('POST', '/catalog-copy/skill', payload);
        } else if (entity === 'kpi') {
          const targetTpl = fields.querySelector('#catalogCopyTargetTpl');
          if (mode === 'local_to_global') {
            response = await api('POST', '/catalog-copy/kpi', {
              mode: 'local_to_global',
              client_id: cfg.clientId,
              target_template_code: targetTpl?.value,
              source_client_regulation_kpi_id: cfg.sourceClientRegulationKpiId || null,
              source_client_standalone_kpi_id: cfg.sourceClientStandaloneKpiId || null,
              target_kpi_code: fields.querySelector('#catalogCopyTargetCode')?.value.trim() || null,
            });
          } else {
            response = await api('POST', '/catalog-copy/kpi', {
              mode: 'global_to_global',
              source_template_code: effectiveSourceTpl,
              target_template_code: targetTpl?.value,
              source_kpi_code: (fields.querySelector('#catalogCopySourceCode')?.value || cfg.sourceCode || '').trim(),
              target_kpi_code: fields.querySelector('#catalogCopyTargetCode')?.value.trim() || null,
            });
          }
        }
        modal.classList.remove('show');
        if (typeof cfg.onSuccess === 'function') cfg.onSuccess(response);
      } catch (e) {
        showErr(errEl, e.message);
      }
    };
  }

  global.CatalogCopy = { open, api, loadTemplates };
})(window);
