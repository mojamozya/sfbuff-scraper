(function () {
  // 1. ページ判定
  function isMatchupPage() {
    return window.location.href.includes('matchup_chart');
  }

  let sortKey = 4;
  let isAsc = false;
  let isCombined = true;
  let originalRawData = [];

  // --- (既存の extractData, getProcessedData, render 関数はそのまま) ---
  // ※スペース省略のため構造だけ記載しますが、中身は前回と同じものを使ってください

  function extractData() {
    const rows = document.querySelectorAll('table tbody tr');
    const data = [];
    rows.forEach(row => {
      const cols = Array.from(row.querySelectorAll('td'));
      if (cols.length < 8) return;
      const charName = cols[0].innerText.trim();
      if (charName === '合計' || charName === 'Σ' || charName === 'Random')
        return;
      data.push({
        name: charName,
        inputType: cols[1].innerText.trim(),
        total: parseInt(cols[2].innerText.replace(/,/g, '')) || 0,
        wins: parseInt(cols[3].innerText.replace(/,/g, '')) || 0,
        losses: parseInt(cols[4].innerText.replace(/,/g, '')) || 0,
        draws: parseInt(cols[5].innerText.replace(/,/g, '')) || 0,
        diff: parseInt(cols[6].innerText.replace(/,/g, '')) || 0,
        ratio: parseFloat(cols[7].innerText.replace(/,/g, '')) || 0,
        chartHtml: cols[8]?.innerHTML || '',
      });
    });
    return data;
  }

  function getProcessedData() {
    let items = [];
    if (isCombined) {
      const map = {};
      originalRawData.forEach(d => {
        const baseName = d.name.replace(/\[[CM]\]/g, '').trim();
        if (!map[baseName]) {
          map[baseName] = {
            ...d,
            name: baseName,
            total: 0,
            wins: 0,
            losses: 0,
            draws: 0,
            diff: 0,
          };
        }
        map[baseName].total += d.total;
        map[baseName].wins += d.wins;
        map[baseName].losses += d.losses;
        map[baseName].draws += d.draws;
        map[baseName].diff += d.diff;
        map[baseName].ratio =
          map[baseName].total > 0
            ? parseFloat(
                ((map[baseName].wins / map[baseName].total) * 100).toFixed(2)
              )
            : 0;
      });
      items = Object.values(map);
    } else {
      items = originalRawData.map(d => ({ ...d }));
    }
    const keys = [
      'name',
      'inputType',
      'total',
      'wins',
      'losses',
      'draws',
      'diff',
      'ratio',
    ];
    items.sort((a, b) => {
      let vA = a[keys[sortKey]];
      let vB = b[keys[sortKey]];
      if (typeof vA === 'string')
        return isAsc ? vA.localeCompare(vB) : vB.localeCompare(vA);
      return isAsc ? vA - vB : vB - vA;
    });
    return items;
  }

  function render() {
    const table = document.querySelector('table');
    if (!table) return;
    const tbody = table.querySelector('tbody');
    const ths = table.querySelectorAll('thead td');

    if (originalRawData.length === 0) originalRawData = extractData();
    const displayData = getProcessedData();

    ths.forEach((th, idx) => {
      if (!th.dataset.initialized) {
        th.style.cursor = 'pointer';
        th.style.backgroundColor = '#444';
        th.onclick = () => {
          if (sortKey === idx) isAsc = !isAsc;
          else {
            sortKey = idx;
            isAsc = false;
          }
          render();
        };
        th.dataset.initialized = 'true';
      }
      const baseText = th.innerText.replace(/[▲▼]/g, '').trim();
      th.innerText = baseText + (sortKey === idx ? (isAsc ? '▲' : '▼') : '');
    });

    tbody.innerHTML = '';
    displayData.forEach(d => {
      const tr = document.createElement('tr');
      const values = [
        d.name,
        isCombined ? '-' : d.inputType,
        d.total,
        d.wins,
        d.losses,
        d.draws,
        d.diff,
        d.ratio.toFixed(2) + '%',
        d.chartHtml,
      ];
      values.forEach((val, i) => {
        const td = document.createElement('td');
        td.style.padding = '8px';
        if (i === 8) td.innerHTML = val;
        else td.innerText = val;
        if (i === 6) {
          if (d.diff > 0) td.style.color = '#36a2eb';
          else if (d.diff < 0) td.style.color = '#ff6384';
        }
        if (i === 7) {
          if (d.ratio > 50) td.style.color = '#36a2eb';
          else if (d.ratio < 50) td.style.color = '#ff6384';
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  function setupUI() {
    if (!isMatchupPage() || document.getElementById('analysis-ctrl')) return;
    const table = document.querySelector('table');
    if (!table) return;

    const ctrl = document.createElement('div');
    ctrl.id = 'analysis-ctrl';
    ctrl.style =
      'margin-bottom: 15px; color: #fff; background: #333; padding: 12px; border-radius: 6px; border: 1px solid #444;';
    ctrl.innerHTML = `<label style="cursor:pointer"><input type="checkbox" id="combine-check" ${
      isCombined ? 'checked' : ''
    }> 操作タイプ(C/M)を合算して表示</label>`;
    table.parentNode.insertBefore(ctrl, table);

    document.getElementById('combine-check').onchange = e => {
      isCombined = e.target.checked;
      render();
    };
  }

  // --- (ここが解決の肝：初期化と監視) ---
  function init() {
    if (!isMatchupPage()) return;

    originalRawData = []; // 遷移のたびにデータリセット
    let retry = 0;
    const timer = setInterval(() => {
      if (document.querySelector('table tbody tr')) {
        clearInterval(timer);
        setupUI();
        render();
      } else if (retry > 10) {
        clearInterval(timer);
      }
      retry++;
    }, 500);
  }

  // 1. 初回読み込み時
  init();

  // 2. SPA遷移（Turbo）への対応
  // sfbuffが使っているTurboフレームワークの遷移イベントをキャッチ
  document.addEventListener('turbo:load', init);
  // もしイベントが違う場合のための保険
  window.addEventListener('popstate', init);
})();
